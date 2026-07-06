from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import KnowledgeSnapshotRun
from app.models.base import utc_now
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


class KnowledgeSnapshotScheduler:
    def __init__(
        self,
        *,
        database_url: str,
        schedule_config: SnapshotScheduleConfig,
        retry_attempts: int,
        interval_seconds: int,
        run_on_start: bool = False,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.database_url = database_url
        self.schedule_config = schedule_config
        self.retry_attempts = retry_attempts
        self.interval_seconds = interval_seconds
        self.run_on_start = run_on_start
        self.clock = clock
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
                if not should_run_snapshot_job(db, job, retry_attempts=self.retry_attempts):
                    return {
                        "granularity": job.granularity,
                        "reference_date": job.reference_date.isoformat(),
                        "status": "skipped",
                    }
                run = rebuild_periodic_knowledge_snapshots(
                    db,
                    granularity=job.granularity,
                    reference_date=job.reference_date,
                    trigger_source="scheduler",
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


def should_run_snapshot_job(db: Session, job: SnapshotScheduleJob, *, retry_attempts: int) -> bool:
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if run is None:
        return True
    if run.status in {"running", "success"}:
        return False
    if run.status == "failed":
        return run.attempt_count < retry_attempts
    return False


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
        run_on_start=settings.knowledge_snapshot_scheduler_run_on_start,
    )


def _hour_reached(now: datetime, hour: int) -> bool:
    return now.time() >= time(hour=hour)
