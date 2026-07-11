import json
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AdminAlertOutboxDispatchPlan, BackgroundTask, BackgroundTaskAttempt, User
from app.schemas.admin import (
    AdminBackgroundTaskActionRequest,
    AdminBackgroundTaskAttemptRead,
    AdminBackgroundTaskEnqueueRequest,
    AdminBackgroundTaskPage,
    AdminBackgroundTaskQueueReport,
    AdminBackgroundTaskRead,
    AdminContentScriptScanTaskEnqueueRequest,
    AdminKnowledgeSnapshotTaskEnqueueRequest,
)
from app.services.admin_common import naive_utc, next_offset, oldest_datetime, require_admin, statement_count
from app.services.audit import record_audit_log
from app.services.background_tasks import cancel_background_task, enqueue_background_task, retry_background_task


router = APIRouter()


@router.post(
    "/background-tasks/alert-dispatch-plans/{plan_id}",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_alert_dispatch_plan_background_task(
    plan_id: int,
    request_body: AdminBackgroundTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    if plan.plan_status != "created":
        raise HTTPException(status_code=409, detail="Only created alert dispatch plans can be enqueued")
    result = enqueue_background_task(
        db,
        task_type="alert_outbox_dispatch_plan",
        idempotency_key=f"alert-dispatch-plan:{plan.id}:{plan.plan_key}",
        source_type="admin_alert_outbox_dispatch_plan",
        source_id=plan.id,
        payload={"plan_id": plan.id},
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "source_type": result.task.source_type,
            "source_id": result.task.source_id,
            "created": result.created,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/knowledge-snapshots",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_knowledge_snapshot_background_task(
    request_body: AdminKnowledgeSnapshotTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    result = enqueue_background_task(
        db,
        task_type="knowledge_snapshot_rebuild",
        idempotency_key=(
            f"knowledge-snapshot:{request_body.granularity}:{request_body.reference_date.isoformat()}"
        ),
        source_type="knowledge_snapshot_window",
        source_id=None,
        payload={
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
        },
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/content-script-scans",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_content_script_scan_background_task(
    request_body: AdminContentScriptScanTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    payload = {
        "slug": request_body.slug.strip("/") if request_body.slug and request_body.slug.strip("/") else None,
        "source_host": request_body.source_host.strip().lower()
        if request_body.source_host and request_body.source_host.strip()
        else None,
        "scan_limit": request_body.scan_limit,
        "scan_offset": request_body.scan_offset,
    }
    scope_hash = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    result = enqueue_background_task(
        db,
        task_type="content_script_asset_scan",
        idempotency_key=f"content-script-scan:{request_body.request_key.strip()}:{scope_hash}",
        source_type="content_script_asset_scan_request",
        source_id=None,
        payload=payload,
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "filters": payload,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.get("/background-tasks", response_model=AdminBackgroundTaskPage)
def list_background_tasks(
    task_type: str | None = Query(default=None, max_length=80),
    task_status: str | None = Query(default=None, alias="status", max_length=32),
    source_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskPage:
    require_admin(current_user)
    statement = select(BackgroundTask).order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
    if task_type:
        statement = statement.where(BackgroundTask.task_type == task_type.strip())
    if task_status:
        statement = statement.where(BackgroundTask.status == task_status.strip())
    if source_type:
        statement = statement.where(BackgroundTask.source_type == source_type.strip())
    total = statement_count(db, statement)
    tasks = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminBackgroundTaskPage(
        items=[_admin_background_task_read(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(tasks)),
    )


@router.get("/background-tasks/queue", response_model=AdminBackgroundTaskQueueReport)
def get_background_task_queue(
    now_at: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskQueueReport:
    require_admin(current_user)
    generated_at = now_at or datetime.now(UTC)
    generated_at_value = naive_utc(generated_at)
    by_status = {
        str(task_status): int(count)
        for task_status, count in db.execute(
            select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(BackgroundTask.status)
        ).all()
    }
    by_task_type = {
        str(task_type): int(count)
        for task_type, count in db.execute(
            select(BackgroundTask.task_type, func.count(BackgroundTask.id)).group_by(BackgroundTask.task_type)
        ).all()
    }
    ready_condition = and_(
        BackgroundTask.status.in_(["pending", "retry_wait"]),
        BackgroundTask.available_at <= generated_at_value,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    stale_condition = and_(
        BackgroundTask.status == "leased",
        BackgroundTask.lease_expires_at.is_not(None),
        BackgroundTask.lease_expires_at <= generated_at_value,
    )
    stale_claimable_condition = and_(
        stale_condition,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    ready_count = int(db.scalar(select(func.count()).select_from(BackgroundTask).where(ready_condition)) or 0)
    stale_lease_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_condition)) or 0
    )
    stale_claimable_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_claimable_condition)) or 0
    )
    oldest_pending_ready = db.scalar(select(func.min(BackgroundTask.available_at)).where(ready_condition))
    oldest_stale_ready = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(stale_claimable_condition)
    )
    next_available_at = db.scalar(
        select(func.min(BackgroundTask.available_at)).where(
            BackgroundTask.status.in_(["pending", "retry_wait"]),
            BackgroundTask.available_at > generated_at_value,
        )
    )
    next_lease_expires_at = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(
            BackgroundTask.status == "leased",
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at > generated_at_value,
        )
    )
    settings = get_settings()
    return AdminBackgroundTaskQueueReport(
        generated_at=generated_at,
        total_count=sum(by_status.values()),
        ready_count=ready_count + stale_claimable_count,
        leased_count=by_status.get("leased", 0),
        retry_wait_count=by_status.get("retry_wait", 0),
        succeeded_count=by_status.get("succeeded", 0),
        dead_letter_count=by_status.get("dead_letter", 0),
        cancelled_count=by_status.get("cancelled", 0),
        stale_lease_count=stale_lease_count,
        by_task_type=by_task_type,
        by_status=by_status,
        oldest_ready_at=oldest_datetime([oldest_pending_ready, oldest_stale_ready]),
        next_available_at=next_available_at,
        next_lease_expires_at=next_lease_expires_at,
        policy={
            "queue_backend": "database",
            "execution_mode": "hybrid_domain_ledgers",
            "worker_enabled": settings.background_task_worker_enabled,
            "lease_seconds": settings.background_task_worker_lease_seconds,
            "batch_size": settings.background_task_worker_batch_size,
            "payload_redacted": True,
            "lease_token_returned": False,
        },
    )


@router.get("/background-tasks/{task_id}", response_model=AdminBackgroundTaskRead)
def get_background_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    return _admin_background_task_read(task)


@router.get("/background-tasks/{task_id}/attempts", response_model=list[AdminBackgroundTaskAttemptRead])
def list_background_task_attempts(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdminBackgroundTaskAttemptRead]:
    require_admin(current_user)
    if db.get(BackgroundTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    attempts = list(
        db.scalars(
            select(BackgroundTaskAttempt)
            .where(BackgroundTaskAttempt.task_id == task_id)
            .order_by(BackgroundTaskAttempt.attempt_number.desc())
        ).all()
    )
    return [_admin_background_task_attempt_read(attempt) for attempt in attempts]


@router.post("/background-tasks/{task_id}/retry", response_model=AdminBackgroundTaskRead)
def retry_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = retry_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.retry",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
            "attempt_count": task.attempt_count,
            "max_attempts": task.max_attempts,
        },
    )
    db.commit()
    return _admin_background_task_read(task)


@router.post("/background-tasks/{task_id}/cancel", response_model=AdminBackgroundTaskRead)
def cancel_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = cancel_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.cancel",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
        },
    )
    db.commit()
    return _admin_background_task_read(task)




def _admin_background_task_read(task: BackgroundTask) -> AdminBackgroundTaskRead:
    now_at = datetime.now(UTC)
    lease_active = (
        task.status == "leased"
        and task.lease_expires_at is not None
        and naive_utc(task.lease_expires_at) > naive_utc(now_at)
    )
    return AdminBackgroundTaskRead(
        id=task.id,
        task_type=task.task_type,
        source_type=task.source_type,
        source_id=task.source_id,
        status=task.status,
        priority=task.priority,
        idempotency_key_prefix=task.idempotency_key[:12],
        payload_redacted=True,
        result_summary=dict(task.result_summary_json or {}),
        available_at=task.available_at,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        last_error_code=task.last_error_code,
        lease_owner=task.lease_owner,
        lease_active=lease_active,
        lease_expires_at=task.lease_expires_at,
        heartbeat_at=task.heartbeat_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_by_user_id=task.created_by_user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _admin_background_task_attempt_read(
    attempt: BackgroundTaskAttempt,
) -> AdminBackgroundTaskAttemptRead:
    return AdminBackgroundTaskAttemptRead(
        id=attempt.id,
        task_id=attempt.task_id,
        attempt_number=attempt.attempt_number,
        worker_id=attempt.worker_id,
        status=attempt.status,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_code=attempt.error_code,
        retryable=attempt.retryable,
        result_summary=dict(attempt.result_summary_json or {}),
    )
