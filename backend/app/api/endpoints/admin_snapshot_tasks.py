from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.endpoints.admin_presenters import admin_alert_outbox_write_response
from app.core.config import get_settings
from app.db.session import get_db
from app.models import KnowledgeSnapshotRun, User
from app.schemas.admin import (
    AdminAlertOutboxWriteResponse,
    AdminKnowledgeSnapshotRunAlertCandidate,
    AdminKnowledgeSnapshotRunAlertOutboxRequest,
    AdminKnowledgeSnapshotRunAlertReport,
    AdminKnowledgeSnapshotRunHealthItem,
    AdminKnowledgeSnapshotRunHealthReport,
    AdminKnowledgeSnapshotRunPage,
    AdminKnowledgeSnapshotRunQueueItem,
    AdminKnowledgeSnapshotRunQueueReport,
    AdminKnowledgeSnapshotRunRead,
    AdminKnowledgeSnapshotRunRequeueRequest,
    AdminKnowledgeSnapshotRunStatusBucket,
)
from app.services.admin_alert_outbox import (
    admin_alert_outbox_write_snapshot,
    enqueue_knowledge_snapshot_alert_outbox,
)
from app.services.admin_common import naive_utc, next_offset, require_admin, statement_count
from app.services.audit import record_audit_log
from app.services.knowledge_snapshot_leases import (
    knowledge_snapshot_lease_has_any_field,
    knowledge_snapshot_lease_is_complete,
    knowledge_snapshot_lease_is_expired,
    knowledge_snapshot_lease_missing_fields,
)
from app.services.knowledge_snapshot_runs import (
    cancel_knowledge_snapshot_run,
    requeue_knowledge_snapshot_run,
    snapshot_run_key,
    snapshot_window,
)
from app.services.knowledge_snapshot_scheduler import (
    SnapshotScheduleConfig,
    SnapshotScheduleJob,
    due_snapshot_jobs,
    should_run_snapshot_job,
)


router = APIRouter()


@router.get("/knowledge-snapshot-runs", response_model=AdminKnowledgeSnapshotRunPage)
def list_knowledge_snapshot_runs(
    granularity: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunPage:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(KnowledgeSnapshotRun).order_by(
        KnowledgeSnapshotRun.started_at.desc(),
        KnowledgeSnapshotRun.id.desc(),
    )
    if granularity is not None:
        statement = statement.where(KnowledgeSnapshotRun.granularity == granularity.strip().lower())
    if status_filter is not None:
        statement = statement.where(KnowledgeSnapshotRun.status == status_filter.strip().lower())
    if trigger_source is not None:
        statement = statement.where(KnowledgeSnapshotRun.trigger_source == trigger_source.strip().lower())
    if from_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at >= from_at)
    if to_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at <= to_at)
    total = statement_count(db, statement)
    runs = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminKnowledgeSnapshotRunPage(
        items=[_admin_knowledge_snapshot_run_read(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(runs)),
    )


@router.get("/knowledge-snapshot-runs/health", response_model=AdminKnowledgeSnapshotRunHealthReport)
def read_knowledge_snapshot_run_health(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    problem_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunHealthReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=problem_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.health_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_health_snapshot(report),
    )
    db.commit()
    return report


@router.get("/knowledge-snapshot-runs/queue", response_model=AdminKnowledgeSnapshotRunQueueReport)
def read_knowledge_snapshot_run_queue(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunQueueReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters["now"] = now_at.isoformat() if now_at is not None else None
    report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=item_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.queue_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_queue_snapshot(report),
    )
    db.commit()
    return report


@router.get("/knowledge-snapshot-runs/alerts", response_model=AdminKnowledgeSnapshotRunAlertReport)
def read_knowledge_snapshot_run_alerts(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    candidate_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunAlertReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters["now"] = now_at.isoformat() if now_at is not None else None
    health_report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=100,
        generated_at=generated_at,
    )
    queue_report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=100,
        generated_at=generated_at,
    )
    report = _knowledge_snapshot_run_alert_report(
        health_report=health_report,
        queue_report=queue_report,
        candidate_limit=candidate_limit,
        generated_at=generated_at,
        filters=filters,
        lease_expiring_seconds=lease_expiring_seconds,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.alert_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_alert_snapshot(report),
    )
    db.commit()
    return report


@router.post("/knowledge-snapshot-runs/alerts/outbox", response_model=AdminAlertOutboxWriteResponse)
def enqueue_knowledge_snapshot_run_alert_outbox(
    request_body: AdminKnowledgeSnapshotRunAlertOutboxRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxWriteResponse:
    require_admin(current_user)
    if not request_body.confirm_observe_only:
        raise HTTPException(status_code=422, detail="confirm_observe_only must be true")
    if (
        request_body.from_at is not None
        and request_body.to_at is not None
        and request_body.from_at > request_body.to_at
    ):
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    settings = get_settings()
    generated_at = request_body.now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=request_body.granularity,
        trigger_source=request_body.trigger_source,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=request_body.granularity,
        trigger_source=request_body.trigger_source,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
    )
    filters["now"] = request_body.now_at.isoformat() if request_body.now_at is not None else None
    health_report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=request_body.lease_expiring_seconds,
        problem_limit=100,
        generated_at=generated_at,
    )
    queue_report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=100,
        generated_at=generated_at,
    )
    alert_report = _knowledge_snapshot_run_alert_report(
        health_report=health_report,
        queue_report=queue_report,
        candidate_limit=request_body.candidate_limit,
        generated_at=generated_at,
        filters=filters,
        lease_expiring_seconds=request_body.lease_expiring_seconds,
    )
    write_result = enqueue_knowledge_snapshot_alert_outbox(
        db,
        report=alert_report,
        actor=current_user,
        status=request_body.status,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.knowledge_snapshot_run.enqueue",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=admin_alert_outbox_write_snapshot(write_result),
    )
    db.commit()
    for entry in write_result.entries:
        db.refresh(entry)
    return admin_alert_outbox_write_response(write_result)


@router.post("/knowledge-snapshot-runs/{run_id}/cancel", response_model=AdminKnowledgeSnapshotRunRead)
def cancel_admin_knowledge_snapshot_run(
    run_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunRead:
    require_admin(current_user)
    run = db.get(KnowledgeSnapshotRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Knowledge snapshot run not found")
    previous_status = run.status
    try:
        cancel_knowledge_snapshot_run(run, cancelled_by_user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=409, detail="Knowledge snapshot run cannot be cancelled")
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.cancel",
        resource_type="knowledge_snapshot_run",
        resource_id=run.id,
        event_result="success",
        request=request,
        snapshot={
            "run_id": run.id,
            "run_key": run.run_key,
            "granularity": run.granularity,
            "trigger_source": run.trigger_source,
            "previous_status": previous_status,
            "status": run.status,
            "cleared_lease": True,
        },
    )
    db.commit()
    db.refresh(run)
    return _admin_knowledge_snapshot_run_read(run)


@router.post("/knowledge-snapshot-runs/{run_id}/requeue", response_model=AdminKnowledgeSnapshotRunRead)
def requeue_admin_knowledge_snapshot_run(
    run_id: int,
    payload: AdminKnowledgeSnapshotRunRequeueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunRead:
    require_admin(current_user)
    run = db.get(KnowledgeSnapshotRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Knowledge snapshot run not found")
    previous_status = run.status
    had_scheduler_lease = any(
        (
            run.scheduler_lease_owner,
            run.scheduler_lease_token,
            run.scheduler_lease_expires_at,
            run.scheduler_heartbeat_at,
        )
    )
    settings = get_settings()
    try:
        requeue_knowledge_snapshot_run(
            run,
            requeued_by_user_id=current_user.id,
            lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
            reason=payload.reason,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Knowledge snapshot run cannot be requeued")
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.requeue",
        resource_type="knowledge_snapshot_run",
        resource_id=run.id,
        event_result="success",
        request=request,
        snapshot={
            "run_id": run.id,
            "run_key": run.run_key,
            "granularity": run.granularity,
            "trigger_source": run.trigger_source,
            "previous_status": previous_status,
            "status": run.status,
            "attempt_count": run.attempt_count,
            "cleared_lease": previous_status != "pending" and had_scheduler_lease,
            "reason_provided": bool(payload.reason and payload.reason.strip()),
        },
    )
    db.commit()
    db.refresh(run)
    return _admin_knowledge_snapshot_run_read(run)




def _knowledge_snapshot_run_statement(
    *,
    granularity: str | None,
    trigger_source: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
    statement = select(KnowledgeSnapshotRun)
    if granularity is not None:
        statement = statement.where(KnowledgeSnapshotRun.granularity == granularity.strip().lower())
    if trigger_source is not None:
        statement = statement.where(KnowledgeSnapshotRun.trigger_source == trigger_source.strip().lower())
    if from_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at >= from_at)
    if to_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at <= to_at)
    return statement


def _knowledge_snapshot_run_filters(
    *,
    granularity: str | None,
    trigger_source: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    return {
        "granularity": granularity.strip().lower() if granularity is not None else None,
        "trigger_source": trigger_source.strip().lower() if trigger_source is not None else None,
        "from": from_at.isoformat() if from_at is not None else None,
        "to": to_at.isoformat() if to_at is not None else None,
    }


def _knowledge_snapshot_run_health_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    retry_attempts: int,
    lease_seconds: int,
    lease_expiring_seconds: int,
    problem_limit: int,
    generated_at: datetime,
) -> AdminKnowledgeSnapshotRunHealthReport:
    runs = list(db.scalars(statement).all())
    generated_at_naive = naive_utc(generated_at)
    lease_expiring_cutoff = generated_at_naive + timedelta(seconds=lease_expiring_seconds)
    status_counts: dict[str | None, int] = {}
    running_count = 0
    active_running_count = 0
    stale_running_count = 0
    lease_expiring_count = 0
    legacy_running_without_lease_count = 0
    partial_running_lease_count = 0
    pending_count = 0
    success_count = 0
    failed_count = 0
    retryable_failed_count = 0
    exhausted_failed_count = 0
    cancelled_count = 0
    claimable_count = 0
    problem_runs: list[AdminKnowledgeSnapshotRunHealthItem] = []
    latest_success_by_granularity: dict[str, datetime | None] = {}
    oldest_running_started_at: datetime | None = None
    next_lease_expires_at: datetime | None = None
    newest_finished_at: datetime | None = None

    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        if run.finished_at is not None and (
            newest_finished_at is None or naive_utc(run.finished_at) > naive_utc(newest_finished_at)
        ):
            newest_finished_at = run.finished_at
        health_flags: list[str] = []
        retryable = False
        claimable = False
        lease_seconds_remaining: int | None = None
        if run.status == "running":
            running_count += 1
            if oldest_running_started_at is None or naive_utc(run.started_at) < naive_utc(oldest_running_started_at):
                oldest_running_started_at = run.started_at
            has_any_lease = knowledge_snapshot_lease_has_any_field(run)
            has_complete_lease = knowledge_snapshot_lease_is_complete(run)
            if not has_any_lease:
                legacy_running_without_lease_count += 1
                health_flags.append("legacy_running_without_lease")
            elif not has_complete_lease:
                partial_running_lease_count += 1
                health_flags.append("partial_scheduler_lease")
                health_flags.extend(_knowledge_snapshot_missing_lease_flags(knowledge_snapshot_lease_missing_fields(run)))
            lease_expires_at = naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > generated_at_naive:
                lease_seconds_remaining = int((lease_expires_at - generated_at_naive).total_seconds())
                if next_lease_expires_at is None or lease_expires_at < naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
                if lease_expires_at <= lease_expiring_cutoff:
                    lease_expiring_count += 1
                    health_flags.append("lease_expiring")
            if _knowledge_snapshot_run_lease_expired(run, generated_at_naive, lease_seconds):
                stale_running_count += 1
                claimable = True
                claimable_count += 1
                health_flags.append("stale_running")
            elif has_complete_lease:
                active_running_count += 1
        elif run.status == "pending":
            pending_count += 1
            claimable = True
            claimable_count += 1
            health_flags.append("pending")
        elif run.status == "success":
            success_count += 1
            latest_success_at = run.finished_at or run.started_at
            current_latest = latest_success_by_granularity.get(run.granularity)
            if current_latest is None or naive_utc(latest_success_at) > naive_utc(current_latest):
                latest_success_by_granularity[run.granularity] = latest_success_at
        elif run.status == "failed":
            failed_count += 1
            if run.attempt_count < retry_attempts:
                retryable_failed_count += 1
                retryable = True
                claimable = True
                claimable_count += 1
                health_flags.append("retryable_failed")
            else:
                exhausted_failed_count += 1
                health_flags.append("exhausted_failed")
        elif run.status == "cancelled":
            cancelled_count += 1
        if health_flags:
            problem_runs.append(
                AdminKnowledgeSnapshotRunHealthItem(
                    id=run.id,
                    run_key=run.run_key,
                    granularity=run.granularity,
                    period_start=run.period_start,
                    period_end=run.period_end,
                    trigger_source=run.trigger_source,
                    status=run.status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    scheduler_lease_owner=run.scheduler_lease_owner,
                    scheduler_lease_expires_at=run.scheduler_lease_expires_at,
                    scheduler_heartbeat_at=run.scheduler_heartbeat_at,
                    attempt_count=run.attempt_count,
                    user_snapshot_count=run.user_snapshot_count,
                    class_snapshot_count=run.class_snapshot_count,
                    error_message=run.error_message,
                    health_flags=health_flags,
                    retryable=retryable,
                    claimable=claimable,
                    cancellable=run.status == "pending"
                    or (run.status == "running" and run.scheduler_lease_token is not None),
                    lease_seconds_remaining=lease_seconds_remaining,
                )
            )

    needs_attention_count = stale_running_count + pending_count + failed_count + partial_running_lease_count
    if needs_attention_count > 0:
        health_status: Literal["ok", "warning", "attention"] = "attention"
    elif lease_expiring_count > 0:
        health_status = "warning"
    else:
        health_status = "ok"
    return AdminKnowledgeSnapshotRunHealthReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": retry_attempts,
            "lease_seconds": lease_seconds,
            "lease_expiring_seconds": lease_expiring_seconds,
            "problem_limit": problem_limit,
        },
        health_status=health_status,
        total=len(runs),
        by_status=[
            AdminKnowledgeSnapshotRunStatusBucket(status=status, total=total)
            for status, total in sorted(status_counts.items(), key=lambda item: str(item[0] or ""))
        ],
        running_count=running_count,
        active_running_count=active_running_count,
        stale_running_count=stale_running_count,
        lease_expiring_count=lease_expiring_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        partial_running_lease_count=partial_running_lease_count,
        claimable_count=claimable_count,
        pending_count=pending_count,
        success_count=success_count,
        failed_count=failed_count,
        retryable_failed_count=retryable_failed_count,
        exhausted_failed_count=exhausted_failed_count,
        cancelled_count=cancelled_count,
        needs_attention_count=needs_attention_count,
        problem_count=len(problem_runs),
        problem_runs=_sort_knowledge_snapshot_problem_runs(problem_runs)[:problem_limit],
        latest_success_by_granularity=latest_success_by_granularity,
        oldest_running_started_at=oldest_running_started_at,
        next_lease_expires_at=next_lease_expires_at,
        newest_finished_at=newest_finished_at,
    )


def _knowledge_snapshot_run_health_snapshot(report: AdminKnowledgeSnapshotRunHealthReport) -> dict[str, Any]:
    return {
        "format": "health",
        "filters": report.filters,
        "policy": report.policy,
        "health_status": report.health_status,
        "total": report.total,
        "by_status": [bucket.model_dump() for bucket in report.by_status],
        "running_count": report.running_count,
        "stale_running_count": report.stale_running_count,
        "lease_expiring_count": report.lease_expiring_count,
        "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        "partial_running_lease_count": report.partial_running_lease_count,
        "claimable_count": report.claimable_count,
        "pending_count": report.pending_count,
        "failed_count": report.failed_count,
        "retryable_failed_count": report.retryable_failed_count,
        "exhausted_failed_count": report.exhausted_failed_count,
        "needs_attention_count": report.needs_attention_count,
        "problem_count": report.problem_count,
    }


def _knowledge_snapshot_run_queue_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    schedule_config: SnapshotScheduleConfig,
    retry_attempts: int,
    lease_seconds: int,
    item_limit: int,
    generated_at: datetime,
) -> AdminKnowledgeSnapshotRunQueueReport:
    runs = list(db.scalars(statement).all())
    generated_at_naive = naive_utc(generated_at)
    due_jobs = due_snapshot_jobs(generated_at_naive, schedule_config)
    if filters["granularity"] is not None:
        due_jobs = [job for job in due_jobs if job.granularity == filters["granularity"]]

    ready_jobs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    manual_requeue_runs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    blocked_runs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    next_due_jobs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    ready_keys: set[tuple[str, date]] = set()
    next_lease_expires_at: datetime | None = None

    for job in due_jobs:
        item = _knowledge_snapshot_due_queue_item(db, job, retry_attempts, lease_seconds, generated_at_naive)
        if item is None:
            continue
        if _knowledge_snapshot_queue_item_matches_filters(item, filters):
            next_due_jobs.append(item)
            if item.ready:
                ready_jobs.append(item)
                ready_keys.add((item.granularity, item.reference_date))

    retryable_failed_count = 0
    exhausted_failed_count = 0
    cancelled_count = 0
    stale_running_count = 0
    active_running_count = 0
    legacy_running_without_lease_count = 0
    pending_count = 0
    claimable_by_lease_rule_count = 0

    for run in runs:
        key = (run.granularity, run.period_start.date())
        if run.status == "pending":
            pending_count += 1
            claimable_by_lease_rule_count += 1
            if key not in ready_keys:
                item = _knowledge_snapshot_run_queue_item(
                    run,
                    source="pending",
                    reason="pending_run_waiting_for_scheduler",
                    ready=True,
                    claimable=True,
                )
                ready_jobs.append(item)
                ready_keys.add(key)
        elif run.status == "failed":
            retryable = run.attempt_count < retry_attempts
            if retryable:
                retryable_failed_count += 1
                claimable_by_lease_rule_count += 1
                source = "retryable_failed"
                reason = "manual_requeue_available_retryable_failed"
            else:
                exhausted_failed_count += 1
                source = "exhausted_failed"
                reason = "manual_requeue_available_exhausted_failed"
            manual_requeue_runs.append(
                _knowledge_snapshot_run_queue_item(
                    run,
                    source=source,
                    reason=reason,
                    ready=False,
                    claimable=retryable,
                )
            )
        elif run.status == "cancelled":
            cancelled_count += 1
            manual_requeue_runs.append(
                _knowledge_snapshot_run_queue_item(
                    run,
                    source="cancelled",
                    reason="manual_requeue_available_cancelled",
                    ready=False,
                    claimable=False,
                )
            )
        elif run.status == "running":
            lease_expired = _knowledge_snapshot_run_lease_expired(run, generated_at_naive, lease_seconds)
            if run.scheduler_lease_token is None:
                legacy_running_without_lease_count += 1
            lease_expires_at = naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > generated_at_naive:
                if next_lease_expires_at is None or lease_expires_at < naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
            if lease_expired and run.scheduler_lease_token is not None:
                stale_running_count += 1
                claimable_by_lease_rule_count += 1
                if key not in ready_keys:
                    manual_requeue_runs.append(
                        _knowledge_snapshot_run_queue_item(
                            run,
                            source="stale_running",
                            reason="manual_requeue_available_stale_running",
                            ready=False,
                            claimable=True,
                        )
                    )
            elif lease_expired:
                stale_running_count += 1
                claimable_by_lease_rule_count += 1
                blocked_runs.append(
                    _knowledge_snapshot_run_queue_item(
                        run,
                        source="legacy_running",
                        reason="legacy_running_without_scheduler_lease",
                        ready=False,
                        claimable=False,
                    )
                )
            else:
                active_running_count += 1
                blocked_runs.append(
                    _knowledge_snapshot_run_queue_item(
                        run,
                        source="active_running" if run.scheduler_lease_token is not None else "legacy_running",
                        reason="active_running_lease_not_expired"
                        if run.scheduler_lease_token is not None
                        else "legacy_running_without_scheduler_lease",
                        ready=False,
                        claimable=False,
                    )
                )

    ready_jobs = _sort_knowledge_snapshot_queue_items(ready_jobs)
    manual_requeue_runs = _sort_knowledge_snapshot_queue_items(manual_requeue_runs)
    blocked_runs = _sort_knowledge_snapshot_queue_items(blocked_runs)
    next_due_jobs = _sort_knowledge_snapshot_queue_items(next_due_jobs)
    ready_count = len(ready_jobs)
    manual_requeue_count = len(manual_requeue_runs)
    blocked_count = len(blocked_runs)
    backlog_count = ready_count + manual_requeue_count + blocked_count
    if ready_count > 0:
        queue_status: Literal["empty", "ready", "backlog"] = "ready"
    elif backlog_count > 0:
        queue_status = "backlog"
    else:
        queue_status = "empty"

    by_granularity: dict[str, int] = {}
    for item in ready_jobs + manual_requeue_runs + blocked_runs:
        by_granularity[item.granularity] = by_granularity.get(item.granularity, 0) + 1

    return AdminKnowledgeSnapshotRunQueueReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": retry_attempts,
            "lease_seconds": lease_seconds,
            "item_limit": item_limit,
            "daily_enabled": schedule_config.daily_enabled,
            "daily_hour": schedule_config.daily_hour,
            "weekly_enabled": schedule_config.weekly_enabled,
            "weekly_weekday": schedule_config.weekly_weekday,
            "weekly_hour": schedule_config.weekly_hour,
        },
        queue_status=queue_status,
        backlog_count=backlog_count,
        ready_count=ready_count,
        dispatchable_now_count=ready_count,
        claimable_by_lease_rule_count=claimable_by_lease_rule_count,
        due_count=sum(1 for item in ready_jobs if item.source == "due"),
        pending_count=pending_count,
        manual_requeue_count=manual_requeue_count,
        blocked_count=blocked_count,
        retryable_failed_count=retryable_failed_count,
        exhausted_failed_count=exhausted_failed_count,
        cancelled_count=cancelled_count,
        stale_running_count=stale_running_count,
        active_running_count=active_running_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        by_granularity=by_granularity,
        ready_jobs=ready_jobs[:item_limit],
        manual_requeue_runs=manual_requeue_runs[:item_limit],
        blocked_runs=blocked_runs[:item_limit],
        next_due_jobs=next_due_jobs[:item_limit],
        oldest_ready_at=_oldest_queue_item_started_at(ready_jobs),
        oldest_manual_requeue_at=_oldest_queue_item_started_at(manual_requeue_runs),
        next_lease_expires_at=next_lease_expires_at,
    )


def _knowledge_snapshot_due_queue_item(
    db: Session,
    job: SnapshotScheduleJob,
    retry_attempts: int,
    lease_seconds: int,
    now: datetime,
) -> AdminKnowledgeSnapshotRunQueueItem | None:
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    should_run = should_run_snapshot_job(
        db,
        job,
        retry_attempts=retry_attempts,
        lease_seconds=lease_seconds,
        now=now,
    )
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if not should_run and run is None:
        return None
    if run is None:
        return AdminKnowledgeSnapshotRunQueueItem(
            source="due",
            reason="due_window_missing_run",
            ready=True,
            claimable=True,
            run_key=run_key,
            granularity=job.granularity,
            reference_date=job.reference_date,
            period_start=period_start,
            period_end=period_end,
            status="missing",
        )
    if not should_run:
        return _knowledge_snapshot_run_queue_item(
            run,
            source="due",
            reason=f"due_window_{run.status}_not_ready",
            ready=False,
            claimable=False,
        )
    if run.status == "pending":
        reason = "due_window_pending"
    elif run.status == "failed":
        reason = "due_window_retryable_failed" if run.attempt_count < retry_attempts else "due_window_failed"
    elif run.status == "running":
        reason = "due_window_stale_running"
    else:
        reason = "due_window_ready"
    return _knowledge_snapshot_run_queue_item(
        run,
        source="due",
        reason=reason,
        ready=True,
        claimable=True,
    )


def _knowledge_snapshot_run_queue_item(
    run: KnowledgeSnapshotRun,
    *,
    source: Literal[
        "due",
        "pending",
        "retryable_failed",
        "exhausted_failed",
        "cancelled",
        "stale_running",
        "active_running",
        "legacy_running",
    ],
    reason: str,
    ready: bool,
    claimable: bool,
) -> AdminKnowledgeSnapshotRunQueueItem:
    return AdminKnowledgeSnapshotRunQueueItem(
        source=source,
        reason=reason,
        ready=ready,
        claimable=claimable,
        run_id=run.id,
        run_key=run.run_key,
        granularity=run.granularity,
        reference_date=run.period_start.date(),
        period_start=run.period_start,
        period_end=run.period_end,
        status=run.status,
        trigger_source=run.trigger_source,
        started_at=run.started_at,
        finished_at=run.finished_at,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        attempt_count=run.attempt_count,
    )


def _knowledge_snapshot_queue_item_matches_filters(
    item: AdminKnowledgeSnapshotRunQueueItem,
    filters: dict[str, Any],
) -> bool:
    if filters["granularity"] is not None and item.granularity != filters["granularity"]:
        return False
    if filters["trigger_source"] is not None and item.trigger_source != filters["trigger_source"]:
        return False
    if filters["from"] is not None:
        if item.started_at is None or naive_utc(item.started_at) < naive_utc(datetime.fromisoformat(filters["from"])):
            return False
    if filters["to"] is not None:
        if item.started_at is None or naive_utc(item.started_at) > naive_utc(datetime.fromisoformat(filters["to"])):
            return False
    return True


def _sort_knowledge_snapshot_queue_items(
    items: list[AdminKnowledgeSnapshotRunQueueItem],
) -> list[AdminKnowledgeSnapshotRunQueueItem]:
    source_order = {
        "due": 0,
        "pending": 1,
        "stale_running": 2,
        "retryable_failed": 3,
        "exhausted_failed": 4,
        "cancelled": 5,
        "active_running": 6,
        "legacy_running": 7,
    }

    def sort_key(item: AdminKnowledgeSnapshotRunQueueItem) -> tuple[int, datetime, str, int]:
        base_time = item.started_at or item.period_start
        return (source_order.get(item.source, 99), naive_utc(base_time), item.run_key, item.run_id or 0)

    return sorted(items, key=sort_key)


def _oldest_queue_item_started_at(items: list[AdminKnowledgeSnapshotRunQueueItem]) -> datetime | None:
    started_values = [item.started_at for item in items if item.started_at is not None]
    if not started_values:
        return None
    return min(started_values, key=naive_utc)


def _knowledge_snapshot_run_queue_snapshot(report: AdminKnowledgeSnapshotRunQueueReport) -> dict[str, Any]:
    return {
        "format": "queue",
        "filters": report.filters,
        "policy": report.policy,
        "queue_status": report.queue_status,
        "backlog_count": report.backlog_count,
        "ready_count": report.ready_count,
        "dispatchable_now_count": report.dispatchable_now_count,
        "claimable_by_lease_rule_count": report.claimable_by_lease_rule_count,
        "due_count": report.due_count,
        "pending_count": report.pending_count,
        "manual_requeue_count": report.manual_requeue_count,
        "blocked_count": report.blocked_count,
        "retryable_failed_count": report.retryable_failed_count,
        "exhausted_failed_count": report.exhausted_failed_count,
        "cancelled_count": report.cancelled_count,
        "stale_running_count": report.stale_running_count,
        "active_running_count": report.active_running_count,
        "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        "by_granularity": report.by_granularity,
    }


def _knowledge_snapshot_run_alert_report(
    *,
    health_report: AdminKnowledgeSnapshotRunHealthReport,
    queue_report: AdminKnowledgeSnapshotRunQueueReport,
    candidate_limit: int,
    generated_at: datetime,
    filters: dict[str, Any],
    lease_expiring_seconds: int,
) -> AdminKnowledgeSnapshotRunAlertReport:
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate] = []
    for item in health_report.problem_runs:
        candidates.extend(_knowledge_snapshot_health_alert_candidates(item))
    for item in queue_report.ready_jobs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"queue_{item.source}",
                severity="warning",
                action_hint="dispatch",
            )
        )
    for item in queue_report.manual_requeue_runs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"manual_{item.source}",
                severity="critical" if item.source in {"stale_running", "exhausted_failed"} else "warning",
                action_hint="requeue" if item.claimable else "investigate",
            )
        )
    for item in queue_report.blocked_runs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"blocked_{item.source}",
                severity="critical" if item.source == "legacy_running" else "info",
                action_hint="investigate" if item.source == "legacy_running" else "monitor",
            )
        )

    sorted_candidates = _sort_knowledge_snapshot_alert_candidates(candidates)
    critical_count = sum(1 for item in sorted_candidates if item.severity == "critical")
    warning_count = sum(1 for item in sorted_candidates if item.severity == "warning")
    info_count = sum(1 for item in sorted_candidates if item.severity == "info")
    if critical_count > 0:
        alert_status: Literal["ok", "warning", "critical"] = "critical"
    elif warning_count > 0:
        alert_status = "warning"
    else:
        alert_status = "ok"
    return AdminKnowledgeSnapshotRunAlertReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": health_report.policy.get("retry_attempts"),
            "lease_seconds": health_report.policy.get("lease_seconds"),
            "lease_expiring_seconds": lease_expiring_seconds,
            "candidate_limit": candidate_limit,
            "source": "health_queue_derived",
        },
        alert_status=alert_status,
        health_status=health_report.health_status,
        queue_status=queue_report.queue_status,
        candidate_count=len(sorted_candidates),
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        needs_attention_count=health_report.needs_attention_count,
        lease_expiring_count=health_report.lease_expiring_count,
        dispatchable_now_count=queue_report.dispatchable_now_count,
        manual_requeue_count=queue_report.manual_requeue_count,
        blocked_count=queue_report.blocked_count,
        candidates=sorted_candidates[:candidate_limit],
    )


def _knowledge_snapshot_health_alert_candidates(
    item: AdminKnowledgeSnapshotRunHealthItem,
) -> list[AdminKnowledgeSnapshotRunAlertCandidate]:
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate] = []
    for flag in item.health_flags:
        if flag == "stale_running":
            severity: Literal["critical", "warning", "info"] = "critical"
            action_hint: Literal["requeue", "dispatch", "investigate", "monitor"] = (
                "requeue" if item.claimable else "investigate"
            )
        elif flag in {
            "partial_scheduler_lease",
            "running_missing_lease_owner",
            "running_missing_lease_token",
            "running_missing_lease_expiry",
            "running_missing_heartbeat",
        }:
            severity = "critical"
            action_hint = "investigate"
        elif flag in {"retryable_failed", "pending"}:
            severity = "warning"
            action_hint = "requeue" if flag == "retryable_failed" else "dispatch"
        elif flag in {"exhausted_failed", "legacy_running_without_lease"}:
            severity = "critical"
            action_hint = "investigate"
        elif flag == "lease_expiring":
            severity = "warning"
            action_hint = "monitor"
        else:
            severity = "info"
            action_hint = "monitor"
        candidates.append(
            AdminKnowledgeSnapshotRunAlertCandidate(
                severity=severity,
                code=flag,
                source="health",
                action_hint=action_hint,
                run_id=item.id,
                run_key=item.run_key,
                granularity=item.granularity,
                status=item.status,
                trigger_source=item.trigger_source,
                started_at=item.started_at,
                finished_at=item.finished_at,
                scheduler_lease_owner=item.scheduler_lease_owner,
                scheduler_lease_expires_at=item.scheduler_lease_expires_at,
                scheduler_heartbeat_at=item.scheduler_heartbeat_at,
                attempt_count=item.attempt_count,
                health_flags=[flag],
                retryable=item.retryable,
                claimable=item.claimable,
                cancellable=item.cancellable,
            )
        )
    return candidates


def _knowledge_snapshot_queue_alert_candidate(
    item: AdminKnowledgeSnapshotRunQueueItem,
    *,
    code: str,
    severity: Literal["critical", "warning", "info"],
    action_hint: Literal["requeue", "dispatch", "investigate", "monitor"],
) -> AdminKnowledgeSnapshotRunAlertCandidate:
    return AdminKnowledgeSnapshotRunAlertCandidate(
        severity=severity,
        code=code,
        source="queue",
        action_hint=action_hint,
        run_id=item.run_id,
        run_key=item.run_key,
        granularity=item.granularity,
        status=item.status,
        trigger_source=item.trigger_source,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
        queue_reason=item.reason,
        claimable=item.claimable,
        ready=item.ready,
    )


def _sort_knowledge_snapshot_alert_candidates(
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate],
) -> list[AdminKnowledgeSnapshotRunAlertCandidate]:
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    action_order = {"requeue": 0, "dispatch": 1, "investigate": 2, "monitor": 3}

    def sort_key(item: AdminKnowledgeSnapshotRunAlertCandidate) -> tuple[int, int, datetime, str, int]:
        base_time = item.started_at or item.finished_at or datetime.max
        return (
            severity_order.get(item.severity, 99),
            action_order.get(item.action_hint, 99),
            naive_utc(base_time),
            item.run_key,
            item.run_id or 0,
        )

    return sorted(candidates, key=sort_key)


def _knowledge_snapshot_run_alert_snapshot(report: AdminKnowledgeSnapshotRunAlertReport) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for item in report.candidates:
        by_code[item.code] = by_code.get(item.code, 0) + 1
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
    return {
        "format": "alert_candidates",
        "filters": report.filters,
        "policy": report.policy,
        "alert_status": report.alert_status,
        "health_status": report.health_status,
        "queue_status": report.queue_status,
        "candidate_count": report.candidate_count,
        "critical_count": report.critical_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "needs_attention_count": report.needs_attention_count,
        "lease_expiring_count": report.lease_expiring_count,
        "dispatchable_now_count": report.dispatchable_now_count,
        "manual_requeue_count": report.manual_requeue_count,
        "blocked_count": report.blocked_count,
        "candidate_codes": by_code,
        "candidate_severities": by_severity,
    }


def _knowledge_snapshot_schedule_config(settings: Any) -> SnapshotScheduleConfig:
    return SnapshotScheduleConfig(
        daily_enabled=settings.knowledge_snapshot_daily_enabled,
        daily_hour=settings.knowledge_snapshot_daily_hour,
        weekly_enabled=settings.knowledge_snapshot_weekly_enabled,
        weekly_weekday=settings.knowledge_snapshot_weekly_weekday,
        weekly_hour=settings.knowledge_snapshot_weekly_hour,
    )


def _sort_knowledge_snapshot_problem_runs(
    runs: list[AdminKnowledgeSnapshotRunHealthItem],
) -> list[AdminKnowledgeSnapshotRunHealthItem]:
    severity_order = {
        "stale_running": 0,
        "partial_scheduler_lease": 1,
        "running_missing_lease_owner": 2,
        "running_missing_lease_token": 3,
        "running_missing_lease_expiry": 4,
        "running_missing_heartbeat": 5,
        "retryable_failed": 6,
        "exhausted_failed": 7,
        "pending": 8,
        "lease_expiring": 9,
        "legacy_running_without_lease": 10,
    }

    def sort_key(run: AdminKnowledgeSnapshotRunHealthItem) -> tuple[int, datetime, int]:
        severity = min((severity_order.get(flag, 99) for flag in run.health_flags), default=99)
        return (severity, naive_utc(run.started_at), run.id)

    return sorted(runs, key=sort_key)


def _knowledge_snapshot_run_lease_expired(run: KnowledgeSnapshotRun, now: datetime, lease_seconds: int) -> bool:
    return knowledge_snapshot_lease_is_expired(run, now, lease_seconds)


def _knowledge_snapshot_run_metadata_summary(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    if not metadata:
        return {}, False
    summary: dict[str, Any] = {}
    directly_allowed = {
        "trigger_source",
        "previous_status",
        "previous_attempt_count",
        "cleared_lease",
        "cancelled_at",
        "requeued_at",
    }
    for key in directly_allowed:
        if key in metadata:
            summary[key] = metadata[key]
    if "requeue_reason" in metadata:
        summary["requeue_reason_present"] = bool(str(metadata.get("requeue_reason") or "").strip())
    if "cancelled_by_user_id" in metadata or "requeued_by_user_id" in metadata:
        summary["admin_actor_present"] = True
    redacted_keys = set(metadata) - directly_allowed
    return summary, bool(redacted_keys)


def _knowledge_snapshot_missing_lease_flags(missing_fields: list[str]) -> list[str]:
    flag_by_field = {
        "scheduler_lease_owner": "running_missing_lease_owner",
        "scheduler_lease_token": "running_missing_lease_token",
        "scheduler_lease_expires_at": "running_missing_lease_expiry",
        "scheduler_heartbeat_at": "running_missing_heartbeat",
    }
    return [flag_by_field[field] for field in missing_fields if field in flag_by_field]




def _admin_knowledge_snapshot_run_read(run: KnowledgeSnapshotRun) -> AdminKnowledgeSnapshotRunRead:
    metadata_summary, metadata_redacted = _knowledge_snapshot_run_metadata_summary(run.metadata_json)
    return AdminKnowledgeSnapshotRunRead(
        id=run.id,
        run_key=run.run_key,
        granularity=run.granularity,
        period_start=run.period_start,
        period_end=run.period_end,
        trigger_source=run.trigger_source,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        attempt_count=run.attempt_count,
        user_snapshot_count=run.user_snapshot_count,
        class_snapshot_count=run.class_snapshot_count,
        error_message=run.error_message,
        metadata_summary=metadata_summary,
        metadata_redacted=metadata_redacted,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
