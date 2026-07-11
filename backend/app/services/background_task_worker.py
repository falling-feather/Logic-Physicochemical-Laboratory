from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import logging
import os
from pathlib import Path
import socket
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session_factory
from app.models import BackgroundTask, ContentScriptAssetScanRun, KnowledgeSnapshotRun, User
from app.models.base import utc_now
from app.services.alert_delivery import AlertDeliveryAdapter, build_alert_delivery_adapter
from app.services.alert_dispatch_tasks import AlertDispatchTaskError, dispatch_alert_plan_from_background_task
from app.services.audit import record_audit_log
from app.services.audit_anchor_delivery import AuditAnchorAdapter, build_audit_anchor_adapter
from app.services.audit_archive_anchors import AuditArchiveAnchorError, execute_audit_archive_anchor
from app.services.background_tasks import (
    BackgroundTaskLease,
    claim_next_background_task,
    complete_background_task,
    enqueue_background_task,
    fail_background_task,
    heartbeat_background_task,
)
from app.services.content_script_asset_scan_runs import (
    acquire_content_script_asset_scan_job_lease,
    content_script_asset_remote_drift_scan_filters,
    finish_content_script_asset_scan_run_failure,
    finish_content_script_asset_scan_run_success,
    scheduled_content_script_remote_drift_run_key,
)
from app.services.content_script_assets import scan_current_content_script_asset_remote_drift
from app.services.knowledge_snapshot_runs import (
    rebuild_periodic_knowledge_snapshots,
    snapshot_run_key,
    snapshot_window,
)
from app.services.knowledge_snapshot_scheduler import (
    SnapshotScheduleConfig,
    SnapshotScheduleJob,
    acquire_snapshot_job_lease,
    due_snapshot_jobs,
    heartbeat_snapshot_job_lease,
)


BACKGROUND_TASK_TYPES = {
    "alert_outbox_dispatch_plan",
    "knowledge_snapshot_rebuild",
    "content_script_asset_scan",
    "audit_archive_anchor",
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackgroundTaskWorkerReport:
    worker_id: str
    scheduled_enqueue_count: int
    claimed_count: int
    succeeded_count: int
    retry_wait_count: int
    dead_letter_count: int
    lease_lost_count: int
    task_ids: list[int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.dead_letter_count == 0 and self.lease_lost_count == 0,
            "status": "completed",
            "worker_id": self.worker_id,
            "scheduled_enqueue_count": self.scheduled_enqueue_count,
            "claimed_count": self.claimed_count,
            "succeeded_count": self.succeeded_count,
            "retry_wait_count": self.retry_wait_count,
            "dead_letter_count": self.dead_letter_count,
            "lease_lost_count": self.lease_lost_count,
            "task_ids": self.task_ids,
            "payload_returned": False,
            "lease_token_returned": False,
        }


class BackgroundTaskExecutionError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool, summary: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.summary = summary or {}


class BackgroundTaskWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        worker_id: str | None = None,
        adapter_factory: Callable[[Settings], AlertDeliveryAdapter] = build_alert_delivery_adapter,
        audit_anchor_adapter_factory: Callable[[Settings], AuditAnchorAdapter] = build_audit_anchor_adapter,
        task_type_allowlist: set[str] | None = None,
    ) -> None:
        self.settings = settings
        self.worker_id = worker_id or _default_worker_id()
        self.adapter_factory = adapter_factory
        self.audit_anchor_adapter_factory = audit_anchor_adapter_factory
        self.task_type_allowlist = set(task_type_allowlist) if task_type_allowlist is not None else None
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._serve(), name="background-task-worker")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None
        self._stop_event = None

    async def run_once(self) -> dict[str, Any]:
        report = await asyncio.to_thread(self.run_once_sync)
        return report.as_dict()

    def run_once_sync(self) -> BackgroundTaskWorkerReport:
        scheduled_enqueue_count = self._enqueue_scheduled_tasks()
        counts = {
            "claimed": 0,
            "succeeded": 0,
            "retry_wait": 0,
            "dead_letter": 0,
            "lease_lost": 0,
        }
        task_ids: list[int] = []
        for _ in range(self.settings.background_task_worker_batch_size):
            outcome = self._process_next()
            if outcome is None:
                break
            task_id, status = outcome
            counts["claimed"] += 1
            counts[status] += 1
            task_ids.append(task_id)
        return BackgroundTaskWorkerReport(
            worker_id=self.worker_id,
            scheduled_enqueue_count=scheduled_enqueue_count,
            claimed_count=counts["claimed"],
            succeeded_count=counts["succeeded"],
            retry_wait_count=counts["retry_wait"],
            dead_letter_count=counts["dead_letter"],
            lease_lost_count=counts["lease_lost"],
            task_ids=task_ids,
        )

    def _enqueue_scheduled_tasks(self) -> int:
        if not (
            self.settings.knowledge_snapshot_scheduler_enabled
            or self.settings.content_script_remote_drift_scheduler_enabled
        ):
            return 0
        session_factory = get_session_factory(self.settings.database_url)
        created_count = 0
        now_at = utc_now()
        with session_factory() as db:
            if self.settings.knowledge_snapshot_scheduler_enabled:
                due_jobs = due_snapshot_jobs(
                    now_at,
                    SnapshotScheduleConfig(
                        daily_enabled=self.settings.knowledge_snapshot_daily_enabled,
                        daily_hour=self.settings.knowledge_snapshot_daily_hour,
                        weekly_enabled=self.settings.knowledge_snapshot_weekly_enabled,
                        weekly_weekday=self.settings.knowledge_snapshot_weekly_weekday,
                        weekly_hour=self.settings.knowledge_snapshot_weekly_hour,
                    ),
                )
                seen_jobs: set[tuple[str, date]] = set()
                pending_runs = list(
                    db.scalars(
                        select(KnowledgeSnapshotRun)
                        .where(KnowledgeSnapshotRun.status == "pending")
                        .order_by(KnowledgeSnapshotRun.started_at.asc(), KnowledgeSnapshotRun.id.asc())
                        .limit(self.settings.knowledge_snapshot_scheduler_pending_limit)
                    ).all()
                )
                for pending_run in pending_runs:
                    if pending_run.granularity not in {"day", "week"}:
                        continue
                    job = SnapshotScheduleJob(
                        granularity=pending_run.granularity,
                        reference_date=pending_run.period_start.date(),
                    )
                    key = (job.granularity, job.reference_date)
                    seen_jobs.add(key)
                    result = enqueue_background_task(
                        db,
                        task_type="knowledge_snapshot_rebuild",
                        idempotency_key=(
                            f"scheduled:knowledge-pending:{pending_run.id}:"
                            f"{pending_run.updated_at.isoformat()}"
                        ),
                        source_type="knowledge_snapshot_run",
                        source_id=pending_run.id,
                        payload={
                            "granularity": job.granularity,
                            "reference_date": job.reference_date.isoformat(),
                        },
                        max_attempts=max(1, self.settings.knowledge_snapshot_retry_attempts),
                    )
                    created_count += int(result.created)
                for job in due_jobs:
                    key = (job.granularity, job.reference_date)
                    if key in seen_jobs:
                        continue
                    result = enqueue_background_task(
                        db,
                        task_type="knowledge_snapshot_rebuild",
                        idempotency_key=(
                            f"scheduled:knowledge-snapshot:{job.granularity}:{job.reference_date.isoformat()}"
                        ),
                        source_type="knowledge_snapshot_schedule",
                        source_id=None,
                        payload={
                            "granularity": job.granularity,
                            "reference_date": job.reference_date.isoformat(),
                        },
                        max_attempts=max(1, self.settings.knowledge_snapshot_retry_attempts),
                    )
                    created_count += int(result.created)
            if self.settings.content_script_remote_drift_scheduler_enabled:
                filters = content_script_asset_remote_drift_scan_filters(
                    slug=self.settings.content_script_remote_drift_scheduler_slug,
                    source_host=self.settings.content_script_remote_drift_scheduler_source_host,
                    scan_limit=self.settings.content_script_remote_drift_scheduler_scan_limit,
                    scan_offset=0,
                    confirm_external_network=True,
                )
                schedule_key = scheduled_content_script_remote_drift_run_key(
                    scheduled_for=now_at,
                    filters=filters,
                    interval_seconds=self.settings.content_script_remote_drift_scheduler_interval_seconds,
                )
                configured_actor_id = self.settings.content_script_remote_drift_scheduler_actor_user_id
                configured_actor = db.get(User, configured_actor_id) if configured_actor_id is not None else None
                active_actor_id = (
                    configured_actor.id
                    if configured_actor is not None
                    and configured_actor.status == "active"
                    and configured_actor.role == "admin"
                    else None
                )
                if active_actor_id is None:
                    db.commit()
                    return created_count
                result = enqueue_background_task(
                    db,
                    task_type="content_script_asset_scan",
                    idempotency_key=f"scheduled:{schedule_key}",
                    source_type="content_script_asset_scan_schedule",
                    source_id=None,
                    payload={
                        "slug": filters.get("slug"),
                        "source_host": filters.get("source_host"),
                        "scan_limit": int(filters.get("limit", 25)),
                        "scan_offset": int(filters.get("offset", 0)),
                        "actor_user_id": configured_actor_id,
                    },
                    max_attempts=3,
                    created_by_user_id=active_actor_id,
                )
                created_count += int(result.created)
            db.commit()
        return created_count

    async def _serve(self) -> None:
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception as exc:
                logger.error("Background task worker cycle failed: %s", exc.__class__.__name__)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.background_task_worker_interval_seconds,
                )
            except TimeoutError:
                continue

    def _process_next(self) -> tuple[int, str] | None:
        session_factory = get_session_factory(self.settings.database_url)
        with session_factory() as db:
            lease = claim_next_background_task(
                db,
                worker_id=self.worker_id,
                lease_seconds=self.settings.background_task_worker_lease_seconds,
                task_types=self._enabled_task_types(),
            )
            if lease is None:
                return None
            task = db.get(BackgroundTask, lease.task_id)
            actor = db.get(User, task.created_by_user_id) if task and task.created_by_user_id else None
            try:
                self._require_live_task_actor(lease, actor)
                summary = self._execute(db, lease, actor)
            except BackgroundTaskExecutionError as exc:
                db.rollback()
                record_audit_log(
                    db,
                    actor=actor,
                    action="admin.background_task.execute",
                    resource_type="background_task",
                    resource_id=lease.task_id,
                    event_result="failure",
                    failure_reason=exc.code,
                    snapshot={
                        "task_id": lease.task_id,
                        "task_type": lease.task_type,
                        "attempt_number": lease.attempt_number,
                        "worker_id": self.worker_id,
                        "retryable": exc.retryable,
                        "result_summary": exc.summary,
                    },
                )
                failure = fail_background_task(
                    db,
                    lease,
                    error_code=exc.code,
                    retryable=exc.retryable,
                    base_backoff_seconds=self.settings.background_task_worker_base_backoff_seconds,
                    max_backoff_seconds=self.settings.background_task_worker_max_backoff_seconds,
                    result_summary=exc.summary,
                )
                return lease.task_id, failure.status if failure is not None else "lease_lost"
            except Exception as exc:
                db.rollback()
                code = f"unhandled_{exc.__class__.__name__}"[:80]
                record_audit_log(
                    db,
                    actor=actor,
                    action="admin.background_task.execute",
                    resource_type="background_task",
                    resource_id=lease.task_id,
                    event_result="failure",
                    failure_reason=code,
                    snapshot={
                        "task_id": lease.task_id,
                        "task_type": lease.task_type,
                        "attempt_number": lease.attempt_number,
                        "worker_id": self.worker_id,
                        "retryable": True,
                    },
                )
                failure = fail_background_task(
                    db,
                    lease,
                    error_code=code,
                    retryable=True,
                    base_backoff_seconds=self.settings.background_task_worker_base_backoff_seconds,
                    max_backoff_seconds=self.settings.background_task_worker_max_backoff_seconds,
                )
                return lease.task_id, failure.status if failure is not None else "lease_lost"

            record_audit_log(
                db,
                actor=actor,
                action="admin.background_task.execute",
                resource_type="background_task",
                resource_id=lease.task_id,
                event_result="success",
                snapshot={
                    "task_id": lease.task_id,
                    "task_type": lease.task_type,
                    "attempt_number": lease.attempt_number,
                    "worker_id": self.worker_id,
                    "result_summary": summary,
                },
            )
            completed = complete_background_task(db, lease, result_summary=summary)
            return lease.task_id, "succeeded" if completed else "lease_lost"

    def _execute(self, db: Session, lease: BackgroundTaskLease, actor: User | None) -> dict[str, Any]:
        if lease.task_type == "alert_outbox_dispatch_plan":
            return self._execute_alert_plan(db, lease, actor)
        if lease.task_type == "knowledge_snapshot_rebuild":
            return self._execute_knowledge_snapshot(db, lease)
        if lease.task_type == "content_script_asset_scan":
            return self._execute_content_script_scan(db, lease, actor)
        if lease.task_type == "audit_archive_anchor":
            return self._execute_audit_archive_anchor(db, lease)
        raise BackgroundTaskExecutionError("unsupported_task_type", retryable=False)

    def _require_live_task_actor(self, lease: BackgroundTaskLease, actor: User | None) -> None:
        if lease.task_type not in {
            "alert_outbox_dispatch_plan",
            "content_script_asset_scan",
            "audit_archive_anchor",
        }:
            return
        if actor is None or actor.status != "active" or actor.role != "admin":
            raise BackgroundTaskExecutionError("privileged_task_actor_unauthorized", retryable=False)

    def _actor_is_live_admin(self, actor: User | None) -> bool:
        if actor is None:
            return False
        session_factory = get_session_factory(self.settings.database_url)
        with session_factory() as authorization_db:
            current = authorization_db.get(User, actor.id)
            return current is not None and current.status == "active" and current.role == "admin"

    def _execute_alert_plan(
        self,
        db: Session,
        lease: BackgroundTaskLease,
        actor: User | None,
    ) -> dict[str, Any]:
        plan_id = _positive_int(lease.payload.get("plan_id"), "invalid_alert_plan_payload")
        try:
            result = dispatch_alert_plan_from_background_task(
                db,
                plan_id=plan_id,
                settings=self.settings,
                actor=actor,
                heartbeat=lambda: self._actor_is_live_admin(actor) and self._heartbeat(lease),
                adapter_factory=self.adapter_factory,
            )
        except AlertDispatchTaskError as exc:
            raise BackgroundTaskExecutionError(exc.code, retryable=exc.retryable) from None
        return {
            "plan_id": result.plan_id,
            "plan_status": result.plan_status,
            "attempted_count": result.attempted_count,
            "delivered_count": result.delivered_count,
            "failed_count": result.failed_count,
            "recovered_terminal_plan": result.recovered_terminal_plan,
        }

    def _execute_knowledge_snapshot(self, db: Session, lease: BackgroundTaskLease) -> dict[str, Any]:
        granularity = str(lease.payload.get("granularity") or "")
        if granularity not in {"day", "week"}:
            raise BackgroundTaskExecutionError("invalid_knowledge_snapshot_payload", retryable=False)
        try:
            reference_date = date.fromisoformat(str(lease.payload.get("reference_date") or ""))
        except ValueError:
            raise BackgroundTaskExecutionError("invalid_knowledge_snapshot_payload", retryable=False) from None
        job = SnapshotScheduleJob(granularity=granularity, reference_date=reference_date)
        domain_lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=max(lease.max_attempts, self.settings.knowledge_snapshot_retry_attempts),
            lease_owner=self.worker_id,
            lease_seconds=self.settings.background_task_worker_lease_seconds,
            trigger_source="background_worker",
        )
        period_start, period_end = snapshot_window(granularity, reference_date)
        run_key = snapshot_run_key(granularity, period_start, period_end)
        if domain_lease is None:
            run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
            if run is not None and run.status == "success":
                return {
                    "run_id": run.id,
                    "run_key": run.run_key,
                    "status": run.status,
                    "recovered_existing_run": True,
                }
            raise BackgroundTaskExecutionError("knowledge_snapshot_domain_lease_unavailable", retryable=True)

        def heartbeat() -> bool:
            session_factory = get_session_factory(self.settings.database_url)
            with session_factory() as heartbeat_db:
                domain_ok = heartbeat_snapshot_job_lease(
                    heartbeat_db,
                    domain_lease,
                    lease_seconds=self.settings.background_task_worker_lease_seconds,
                )
            return domain_ok and self._heartbeat(lease)

        run = rebuild_periodic_knowledge_snapshots(
            db,
            granularity=granularity,
            reference_date=reference_date,
            trigger_source="background_worker",
            scheduler_lease_owner=domain_lease.lease_owner,
            scheduler_lease_token=domain_lease.lease_token,
            scheduler_lease_heartbeat=heartbeat,
            scheduler_heartbeat_seconds=max(30, self.settings.background_task_worker_lease_seconds // 3),
        )
        return {
            "run_id": run.id,
            "run_key": run.run_key,
            "status": run.status,
            "attempt_count": run.attempt_count,
            "user_snapshot_count": run.user_snapshot_count,
            "class_snapshot_count": run.class_snapshot_count,
            "recovered_existing_run": False,
        }

    def _execute_content_script_scan(
        self,
        db: Session,
        lease: BackgroundTaskLease,
        actor: User | None,
    ) -> dict[str, Any]:
        scan_limit = _bounded_int(lease.payload.get("scan_limit"), 1, 200, "invalid_content_scan_payload")
        scan_offset = _bounded_int(lease.payload.get("scan_offset"), 0, 100000, "invalid_content_scan_payload")
        requested_actor_id = lease.payload.get("actor_user_id")
        if requested_actor_id is not None:
            actor_id = _positive_int(requested_actor_id, "invalid_content_scan_payload")
            if actor is None or actor.id != actor_id or actor.status != "active" or actor.role != "admin":
                raise BackgroundTaskExecutionError("content_scan_actor_unavailable", retryable=False)
        slug = _optional_string(lease.payload.get("slug"))
        source_host = _optional_string(lease.payload.get("source_host"))
        filters = content_script_asset_remote_drift_scan_filters(
            slug=slug,
            source_host=source_host,
            scan_limit=scan_limit,
            scan_offset=scan_offset,
            confirm_external_network=True,
        )
        run_key = f"content-script-remote-drift:background-task:{lease.task_id}"
        domain_lease = acquire_content_script_asset_scan_job_lease(
            db,
            run_key=run_key,
            trigger_source="background_worker",
            request_filters=filters,
            lease_owner=self.worker_id,
            lease_seconds=self.settings.background_task_worker_lease_seconds,
            created_by_user_id=actor.id if actor is not None else None,
        )
        if domain_lease is None:
            run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
            if run is not None and run.status == "success":
                return {
                    "run_id": run.id,
                    "run_key": run.run_key,
                    "status": run.status,
                    "alert_status": run.alert_status,
                    "recovered_existing_run": True,
                }
            raise BackgroundTaskExecutionError("content_scan_domain_lease_unavailable", retryable=True)
        if not self._heartbeat(lease):
            raise BackgroundTaskExecutionError("background_task_lease_lost", retryable=True)
        run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
        if run is None:
            raise BackgroundTaskExecutionError("content_scan_run_missing", retryable=True)
        try:
            report = scan_current_content_script_asset_remote_drift(
                db,
                slug=slug,
                source_host=source_host,
                scan_limit=scan_limit,
                scan_offset=scan_offset,
            )
            run = finish_content_script_asset_scan_run_success(
                db,
                domain_lease,
                report=report,
                finished_at=utc_now(),
            )
            if run is None:
                raise BackgroundTaskExecutionError("content_scan_domain_lease_lost", retryable=True)
            db.commit()
        except BackgroundTaskExecutionError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            failed_run = finish_content_script_asset_scan_run_failure(db, domain_lease, error=exc)
            if failed_run is not None:
                db.commit()
            raise BackgroundTaskExecutionError(
                f"content_scan_{exc.__class__.__name__}"[:80],
                retryable=True,
            ) from None
        return {
            "run_id": run.id,
            "run_key": run.run_key,
            "status": run.status,
            "alert_status": run.alert_status,
            "total_issues": report.total_issues,
            "total_scanned_references": report.total_scanned_references,
            "total_remote_fetches": report.total_remote_fetches,
            "recovered_existing_run": False,
        }

    def _heartbeat(self, lease: BackgroundTaskLease) -> bool:
        session_factory = get_session_factory(self.settings.database_url)
        with session_factory() as heartbeat_db:
            return heartbeat_background_task(
                heartbeat_db,
                lease,
                lease_seconds=self.settings.background_task_worker_lease_seconds,
            )

    def _execute_audit_archive_anchor(
        self,
        db: Session,
        lease: BackgroundTaskLease,
    ) -> dict[str, Any]:
        anchor_id = _positive_int(lease.payload.get("anchor_id"), "invalid_audit_anchor_payload")
        if lease.source_id is not None and lease.source_id != anchor_id:
            raise BackgroundTaskExecutionError("invalid_audit_anchor_payload", retryable=False)
        manifest_path_value = _optional_string(lease.payload.get("manifest_path"))
        if manifest_path_value is None:
            raise BackgroundTaskExecutionError("invalid_audit_anchor_payload", retryable=False)
        if not self._heartbeat(lease):
            raise BackgroundTaskExecutionError("background_task_lease_lost", retryable=True)
        try:
            return execute_audit_archive_anchor(
                db,
                anchor_id=anchor_id,
                manifest_path=Path(manifest_path_value),
                settings=self.settings,
                adapter_factory=self.audit_anchor_adapter_factory,
            )
        except AuditArchiveAnchorError as exc:
            raise BackgroundTaskExecutionError(exc.code, retryable=exc.retryable) from None

    def _enabled_task_types(self) -> set[str]:
        task_types = set(BACKGROUND_TASK_TYPES)
        if not self.settings.background_task_worker_content_scan_enabled:
            task_types.remove("content_script_asset_scan")
        if not self.settings.background_task_worker_audit_anchor_enabled:
            task_types.remove("audit_archive_anchor")
        if self.task_type_allowlist is not None:
            task_types.intersection_update(self.task_type_allowlist)
        return task_types


def worker_from_settings(settings: Settings) -> BackgroundTaskWorker:
    return BackgroundTaskWorker(settings=settings)


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"


def _positive_int(value: Any, error_code: str) -> int:
    if isinstance(value, bool):
        raise BackgroundTaskExecutionError(error_code, retryable=False)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise BackgroundTaskExecutionError(error_code, retryable=False) from None
    if parsed < 1:
        raise BackgroundTaskExecutionError(error_code, retryable=False)
    return parsed


def _bounded_int(value: Any, minimum: int, maximum: int, error_code: str) -> int:
    if isinstance(value, bool):
        raise BackgroundTaskExecutionError(error_code, retryable=False)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise BackgroundTaskExecutionError(error_code, retryable=False) from None
    if parsed < minimum or parsed > maximum:
        raise BackgroundTaskExecutionError(error_code, retryable=False)
    return parsed


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
