from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import os
import socket
from typing import Callable
import uuid

from sqlalchemy import and_, not_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import KnowledgeSnapshotRun
from app.models.base import utc_now
from app.services.knowledge_snapshot_leases import knowledge_snapshot_lease_is_expired
from app.services.knowledge_snapshot_runs import (
    SnapshotGranularity,
    rebuild_periodic_knowledge_snapshots,
    snapshot_run_key,
    snapshot_window,
)


@dataclass(frozen=True)
class SnapshotScheduleConfig:
    daily_enabled: bool = True
    daily_hour: int = 3
    weekly_enabled: bool = True
    weekly_weekday: int = 0
    weekly_hour: int = 4


@dataclass(frozen=True)
class SnapshotScheduleJob:
    granularity: SnapshotGranularity
    reference_date: date


@dataclass(frozen=True)
class SnapshotJobLease:
    run_key: str
    lease_owner: str
    lease_token: str
    lease_expires_at: datetime


class KnowledgeSnapshotScheduler:
    def __init__(
        self,
        *,
        database_url: str,
        schedule_config: SnapshotScheduleConfig,
        retry_attempts: int,
        interval_seconds: int,
        lease_seconds: int,
        heartbeat_seconds: int,
        pending_limit: int = 50,
        run_on_start: bool = False,
        clock: Callable[[], datetime] = utc_now,
        instance_id: str | None = None,
    ) -> None:
        self.database_url = database_url
        self.schedule_config = schedule_config
        self.retry_attempts = retry_attempts
        self.interval_seconds = interval_seconds
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.pending_limit = pending_limit
        self.run_on_start = run_on_start
        self.clock = clock
        self.instance_id = instance_id or _default_scheduler_instance_id()
        self._lock = asyncio.Lock()
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._serve(), name="knowledge-snapshot-scheduler")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None
        self._stop_event = None

    async def run_once(self, now: datetime | None = None) -> list[dict]:
        async with self._lock:
            jobs = due_snapshot_jobs(now or self.clock(), self.schedule_config)
            pending_jobs = await asyncio.to_thread(self._pending_jobs)
            seen_jobs = {(job.granularity, job.reference_date) for job in jobs}
            for job in pending_jobs:
                key = (job.granularity, job.reference_date)
                if key not in seen_jobs:
                    jobs.append(job)
                    seen_jobs.add(key)
            results: list[dict] = []
            for job in jobs:
                result = await asyncio.to_thread(self._run_job_if_needed, job)
                results.append(result)
            return results

    async def _serve(self) -> None:
        if self.run_on_start:
            await self.run_once()
        while self._stop_event is not None:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                break
            except TimeoutError:
                await self.run_once()

    def _run_job_if_needed(self, job: SnapshotScheduleJob) -> dict:
        session_factory = get_session_factory(self.database_url)
        with session_factory() as db:
            try:
                lease = acquire_snapshot_job_lease(
                    db,
                    job,
                    retry_attempts=self.retry_attempts,
                    lease_owner=self.instance_id,
                    lease_seconds=self.lease_seconds,
                    now=self.clock(),
                )
                if lease is None:
                    return {
                        "granularity": job.granularity,
                        "reference_date": job.reference_date.isoformat(),
                        "status": "skipped",
                        "reason": "lease_unavailable",
                    }
                lease_heartbeat = _lease_heartbeat_callback(
                    self.database_url,
                    lease,
                    lease_seconds=self.lease_seconds,
                )
                run = rebuild_periodic_knowledge_snapshots(
                    db,
                    granularity=job.granularity,
                    reference_date=job.reference_date,
                    trigger_source="scheduler",
                    scheduler_lease_owner=lease.lease_owner,
                    scheduler_lease_token=lease.lease_token,
                    scheduler_lease_heartbeat=lease_heartbeat,
                    scheduler_heartbeat_seconds=self.heartbeat_seconds,
                    clock=self.clock,
                )
            except Exception as exc:
                return {
                    "granularity": job.granularity,
                    "reference_date": job.reference_date.isoformat(),
                    "status": "failed",
                    "error": exc.__class__.__name__,
                }
            return {
                "granularity": job.granularity,
                "reference_date": job.reference_date.isoformat(),
                "status": run.status,
                "run_id": run.id,
                "attempt_count": run.attempt_count,
            }

    def _pending_jobs(self) -> list[SnapshotScheduleJob]:
        session_factory = get_session_factory(self.database_url)
        with session_factory() as db:
            return pending_snapshot_jobs(db, limit=self.pending_limit)


def due_snapshot_jobs(now: datetime, config: SnapshotScheduleConfig) -> list[SnapshotScheduleJob]:
    jobs: list[SnapshotScheduleJob] = []
    today = now.date()
    if config.daily_enabled and _hour_reached(now, config.daily_hour):
        jobs.append(SnapshotScheduleJob(granularity="day", reference_date=today - timedelta(days=1)))
    if (
        config.weekly_enabled
        and now.weekday() == config.weekly_weekday
        and _hour_reached(now, config.weekly_hour)
    ):
        jobs.append(SnapshotScheduleJob(granularity="week", reference_date=today - timedelta(days=7)))
    return jobs


def pending_snapshot_jobs(db: Session, *, limit: int | None = None) -> list[SnapshotScheduleJob]:
    statement = (
        select(KnowledgeSnapshotRun)
        .where(KnowledgeSnapshotRun.status == "pending")
        .order_by(KnowledgeSnapshotRun.started_at.asc(), KnowledgeSnapshotRun.id.asc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    runs = db.scalars(statement)
    return [
        SnapshotScheduleJob(granularity=run.granularity, reference_date=run.period_start.date())
        for run in runs
        if run.granularity in {"day", "week"}
    ]


def acquire_snapshot_job_lease(
    db: Session,
    job: SnapshotScheduleJob,
    *,
    retry_attempts: int,
    lease_owner: str,
    lease_seconds: int,
    trigger_source: str = "scheduler",
    now: datetime | None = None,
) -> SnapshotJobLease | None:
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    now_value = _as_naive_utc(now or utc_now())
    lease_expires_at = now_value + timedelta(seconds=lease_seconds)
    lease_token = uuid.uuid4().hex
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if run is None:
        run = KnowledgeSnapshotRun(
            run_key=run_key,
            granularity=job.granularity,
            period_start=period_start,
            period_end=period_end,
            trigger_source=trigger_source,
            status="running",
            started_at=now_value,
            scheduler_lease_owner=lease_owner,
            scheduler_lease_token=lease_token,
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now_value,
            attempt_count=0,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={"trigger_source": trigger_source, "scheduler_lease_owner": lease_owner},
        )
        db.add(run)
        try:
            db.commit()
            return SnapshotJobLease(
                run_key=run_key,
                lease_owner=lease_owner,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
            )
        except IntegrityError:
            db.rollback()
            return _claim_existing_snapshot_job_lease(
                db,
                run_key,
                retry_attempts=retry_attempts,
                lease_owner=lease_owner,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                now=now_value,
                lease_seconds=lease_seconds,
                trigger_source=trigger_source,
            )
    return _claim_existing_snapshot_job_lease(
        db,
        run_key,
        retry_attempts=retry_attempts,
        lease_owner=lease_owner,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
        now=now_value,
        lease_seconds=lease_seconds,
        trigger_source=trigger_source,
    )


def should_run_snapshot_job(
    db: Session,
    job: SnapshotScheduleJob,
    *,
    retry_attempts: int,
    lease_seconds: int | None = None,
    now: datetime | None = None,
) -> bool:
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if run is None:
        return True
    if run.status == "pending":
        return True
    if run.status in {"running", "success"}:
        if run.status == "running" and lease_seconds is not None:
            return _run_lease_expired(run, now or utc_now(), lease_seconds)
        return False
    if run.status == "failed":
        return run.attempt_count < retry_attempts
    return False


def _claim_existing_snapshot_job_lease(
    db: Session,
    run_key: str,
    *,
    retry_attempts: int,
    lease_owner: str,
    lease_token: str,
    lease_expires_at: datetime,
    now: datetime,
    lease_seconds: int,
    trigger_source: str,
) -> SnapshotJobLease | None:
    legacy_running_cutoff = now - timedelta(seconds=lease_seconds)
    lease_owner_present = KnowledgeSnapshotRun.scheduler_lease_owner.is_not(None)
    lease_token_present = KnowledgeSnapshotRun.scheduler_lease_token.is_not(None)
    lease_expires_present = KnowledgeSnapshotRun.scheduler_lease_expires_at.is_not(None)
    lease_heartbeat_present = KnowledgeSnapshotRun.scheduler_heartbeat_at.is_not(None)
    complete_lease = and_(
        lease_owner_present,
        lease_token_present,
        lease_expires_present,
        lease_heartbeat_present,
    )
    any_lease = or_(
        lease_owner_present,
        lease_token_present,
        lease_expires_present,
        lease_heartbeat_present,
    )
    no_lease = and_(
        KnowledgeSnapshotRun.scheduler_lease_owner.is_(None),
        KnowledgeSnapshotRun.scheduler_lease_token.is_(None),
        KnowledgeSnapshotRun.scheduler_lease_expires_at.is_(None),
        KnowledgeSnapshotRun.scheduler_heartbeat_at.is_(None),
    )
    partial_lease = and_(any_lease, not_(complete_lease))
    claimable = or_(
        KnowledgeSnapshotRun.status == "pending",
        and_(
            KnowledgeSnapshotRun.status == "failed",
            KnowledgeSnapshotRun.attempt_count < retry_attempts,
        ),
        and_(
            KnowledgeSnapshotRun.status == "running",
            or_(
                and_(complete_lease, KnowledgeSnapshotRun.scheduler_lease_expires_at <= now),
                and_(
                    partial_lease,
                    or_(
                        KnowledgeSnapshotRun.scheduler_lease_expires_at <= now,
                        KnowledgeSnapshotRun.scheduler_lease_expires_at.is_(None),
                        KnowledgeSnapshotRun.started_at <= legacy_running_cutoff,
                    ),
                ),
                and_(
                    no_lease,
                    KnowledgeSnapshotRun.started_at <= legacy_running_cutoff,
                ),
            ),
        ),
    )
    result = db.execute(
        update(KnowledgeSnapshotRun)
        .where(KnowledgeSnapshotRun.run_key == run_key, claimable)
        .values(
            status="running",
            trigger_source=trigger_source,
            started_at=now,
            finished_at=None,
            error_message=None,
            scheduler_lease_owner=lease_owner,
            scheduler_lease_token=lease_token,
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now,
            metadata_json={"trigger_source": trigger_source, "scheduler_lease_owner": lease_owner},
        )
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return SnapshotJobLease(
        run_key=run_key,
        lease_owner=lease_owner,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
    )


def heartbeat_snapshot_job_lease(
    db: Session,
    lease: SnapshotJobLease,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    now_value = _as_naive_utc(now or utc_now())
    lease_expires_at = now_value + timedelta(seconds=lease_seconds)
    result = db.execute(
        update(KnowledgeSnapshotRun)
        .where(
            KnowledgeSnapshotRun.run_key == lease.run_key,
            KnowledgeSnapshotRun.status == "running",
            KnowledgeSnapshotRun.scheduler_lease_owner == lease.lease_owner,
            KnowledgeSnapshotRun.scheduler_lease_token == lease.lease_token,
            KnowledgeSnapshotRun.scheduler_lease_expires_at.is_not(None),
            KnowledgeSnapshotRun.scheduler_lease_expires_at > now_value,
            KnowledgeSnapshotRun.scheduler_heartbeat_at.is_not(None),
        )
        .values(
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now_value,
        )
    )
    db.commit()
    return result.rowcount == 1


def scheduler_from_settings(settings) -> KnowledgeSnapshotScheduler:
    return KnowledgeSnapshotScheduler(
        database_url=settings.database_url,
        schedule_config=SnapshotScheduleConfig(
            daily_enabled=settings.knowledge_snapshot_daily_enabled,
            daily_hour=settings.knowledge_snapshot_daily_hour,
            weekly_enabled=settings.knowledge_snapshot_weekly_enabled,
            weekly_weekday=settings.knowledge_snapshot_weekly_weekday,
            weekly_hour=settings.knowledge_snapshot_weekly_hour,
        ),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        interval_seconds=settings.knowledge_snapshot_scheduler_interval_seconds,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        heartbeat_seconds=settings.knowledge_snapshot_scheduler_heartbeat_seconds,
        pending_limit=settings.knowledge_snapshot_scheduler_pending_limit,
        run_on_start=settings.knowledge_snapshot_scheduler_run_on_start,
    )


def _hour_reached(now: datetime, hour: int) -> bool:
    return now.time() >= time(hour=hour)


def _run_lease_expired(run: KnowledgeSnapshotRun, now: datetime, lease_seconds: int) -> bool:
    return knowledge_snapshot_lease_is_expired(run, now, lease_seconds)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _default_scheduler_instance_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"


def _lease_heartbeat_callback(
    database_url: str,
    lease: SnapshotJobLease,
    *,
    lease_seconds: int,
) -> Callable[[], bool]:
    def heartbeat() -> bool:
        session_factory = get_session_factory(database_url)
        with session_factory() as heartbeat_db:
            return heartbeat_snapshot_job_lease(heartbeat_db, lease, lease_seconds=lease_seconds)

    return heartbeat
