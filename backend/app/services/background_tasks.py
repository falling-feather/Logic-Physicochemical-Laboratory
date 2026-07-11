from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BackgroundTask, BackgroundTaskAttempt
from app.models.base import utc_now


TASK_STATUS_PENDING = "pending"
TASK_STATUS_LEASED = "leased"
TASK_STATUS_RETRY_WAIT = "retry_wait"
TASK_STATUS_SUCCEEDED = "succeeded"
TASK_STATUS_DEAD_LETTER = "dead_letter"
TASK_STATUS_CANCELLED = "cancelled"
TASK_TERMINAL_STATUSES = {TASK_STATUS_SUCCEEDED, TASK_STATUS_DEAD_LETTER, TASK_STATUS_CANCELLED}


@dataclass(frozen=True)
class BackgroundTaskEnqueueResult:
    task: BackgroundTask
    created: bool


@dataclass(frozen=True)
class BackgroundTaskLease:
    task_id: int
    task_type: str
    source_type: str
    source_id: int | None
    payload: dict[str, Any]
    attempt_number: int
    max_attempts: int
    worker_id: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class BackgroundTaskFailureResult:
    task_id: int
    status: str
    attempt_count: int
    max_attempts: int
    next_available_at: datetime | None


def enqueue_background_task(
    db: Session,
    *,
    task_type: str,
    idempotency_key: str,
    source_type: str,
    source_id: int | None,
    payload: dict[str, Any],
    priority: int = 0,
    available_at: datetime | None = None,
    max_attempts: int = 3,
    created_by_user_id: int | None = None,
) -> BackgroundTaskEnqueueResult:
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 160:
        raise ValueError("background task idempotency key is invalid")
    existing = db.scalar(select(BackgroundTask).where(BackgroundTask.idempotency_key == normalized_key))
    if existing is not None:
        return BackgroundTaskEnqueueResult(task=existing, created=False)
    task = BackgroundTask(
        task_type=task_type.strip(),
        idempotency_key=normalized_key,
        source_type=source_type.strip(),
        source_id=source_id,
        status=TASK_STATUS_PENDING,
        priority=priority,
        payload_json=payload,
        result_summary_json={},
        available_at=available_at or utc_now(),
        attempt_count=0,
        max_attempts=max_attempts,
        created_by_user_id=created_by_user_id,
    )
    try:
        with db.begin_nested():
            db.add(task)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(BackgroundTask).where(BackgroundTask.idempotency_key == normalized_key))
        if existing is None:
            raise
        return BackgroundTaskEnqueueResult(task=existing, created=False)
    return BackgroundTaskEnqueueResult(task=task, created=True)


def claim_next_background_task(
    db: Session,
    *,
    worker_id: str,
    lease_seconds: int,
    task_types: set[str] | None = None,
    now: datetime | None = None,
    candidate_limit: int = 50,
) -> BackgroundTaskLease | None:
    now_value = now or utc_now()
    _move_exhausted_tasks_to_dead_letter(db, now_value)
    eligible = _claim_eligible_expression(now_value)
    statement = (
        select(BackgroundTask.id)
        .where(eligible, BackgroundTask.attempt_count < BackgroundTask.max_attempts)
        .order_by(
            BackgroundTask.priority.desc(),
            BackgroundTask.available_at.asc(),
            BackgroundTask.id.asc(),
        )
        .limit(candidate_limit)
    )
    if task_types is not None:
        statement = statement.where(BackgroundTask.task_type.in_(task_types))
    candidate_ids = list(db.scalars(statement).all())
    for task_id in candidate_ids:
        lease_token = uuid4().hex
        lease_expires_at = now_value + timedelta(seconds=lease_seconds)
        claimed = db.execute(
            update(BackgroundTask)
            .where(
                BackgroundTask.id == task_id,
                _claim_eligible_expression(now_value),
                BackgroundTask.attempt_count < BackgroundTask.max_attempts,
            )
            .values(
                status=TASK_STATUS_LEASED,
                lease_owner=worker_id,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                heartbeat_at=now_value,
                attempt_count=BackgroundTask.attempt_count + 1,
                started_at=now_value,
                finished_at=None,
                last_error_code=None,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            db.rollback()
            continue
        db.expire_all()
        task = db.get(BackgroundTask, task_id)
        if task is None:
            db.rollback()
            continue
        db.execute(
            update(BackgroundTaskAttempt)
            .where(
                BackgroundTaskAttempt.task_id == task.id,
                BackgroundTaskAttempt.status == "running",
            )
            .values(
                status="lease_lost",
                finished_at=now_value,
                error_code="lease_expired",
                retryable=True,
            )
        )
        db.add(
            BackgroundTaskAttempt(
                task_id=task.id,
                attempt_number=task.attempt_count,
                worker_id=worker_id,
                status="running",
                started_at=now_value,
                result_summary_json={},
            )
        )
        db.commit()
        return BackgroundTaskLease(
            task_id=task.id,
            task_type=task.task_type,
            source_type=task.source_type,
            source_id=task.source_id,
            payload=dict(task.payload_json or {}),
            attempt_number=task.attempt_count,
            max_attempts=task.max_attempts,
            worker_id=worker_id,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
        )
    db.commit()
    return None


def heartbeat_background_task(
    db: Session,
    lease: BackgroundTaskLease,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    now_value = now or utc_now()
    result = db.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.id == lease.task_id,
            BackgroundTask.status == TASK_STATUS_LEASED,
            BackgroundTask.lease_owner == lease.worker_id,
            BackgroundTask.lease_token == lease.lease_token,
            BackgroundTask.lease_expires_at > now_value,
        )
        .values(
            heartbeat_at=now_value,
            lease_expires_at=now_value + timedelta(seconds=lease_seconds),
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def complete_background_task(
    db: Session,
    lease: BackgroundTaskLease,
    *,
    result_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    now_value = now or utc_now()
    summary = result_summary or {}
    result = db.execute(
        update(BackgroundTask)
        .where(*_active_lease_conditions(lease, now_value))
        .values(
            status=TASK_STATUS_SUCCEEDED,
            result_summary_json=summary,
            last_error_code=None,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            heartbeat_at=None,
            finished_at=now_value,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    _finish_attempt(
        db,
        lease,
        status="succeeded",
        finished_at=now_value,
        result_summary=summary,
    )
    db.commit()
    return True


def fail_background_task(
    db: Session,
    lease: BackgroundTaskLease,
    *,
    error_code: str,
    retryable: bool,
    base_backoff_seconds: int,
    max_backoff_seconds: int,
    result_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> BackgroundTaskFailureResult | None:
    now_value = now or utc_now()
    task = db.scalar(select(BackgroundTask).where(*_active_lease_conditions(lease, now_value)))
    if task is None:
        db.rollback()
        return None
    should_retry = retryable and task.attempt_count < task.max_attempts
    if should_retry:
        delay = min(base_backoff_seconds * (2 ** max(task.attempt_count - 1, 0)), max_backoff_seconds)
        next_available_at = now_value + timedelta(seconds=delay)
        next_status = TASK_STATUS_RETRY_WAIT
    else:
        next_available_at = None
        next_status = TASK_STATUS_DEAD_LETTER
    summary = result_summary or {}
    task.status = next_status
    task.available_at = next_available_at or now_value
    task.result_summary_json = summary
    task.last_error_code = error_code[:80]
    task.lease_owner = None
    task.lease_token = None
    task.lease_expires_at = None
    task.heartbeat_at = None
    task.finished_at = now_value if next_status == TASK_STATUS_DEAD_LETTER else None
    _finish_attempt(
        db,
        lease,
        status="failed",
        finished_at=now_value,
        error_code=error_code[:80],
        retryable=retryable,
        result_summary=summary,
    )
    db.commit()
    return BackgroundTaskFailureResult(
        task_id=task.id,
        status=next_status,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        next_available_at=next_available_at,
    )


def cancel_background_task(db: Session, task_id: int, *, now: datetime | None = None) -> tuple[BackgroundTask, bool]:
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise LookupError("background task not found")
    if task.status in TASK_TERMINAL_STATUSES:
        return task, False
    now_value = now or utc_now()
    task.status = TASK_STATUS_CANCELLED
    task.lease_owner = None
    task.lease_token = None
    task.lease_expires_at = None
    task.heartbeat_at = None
    task.finished_at = now_value
    db.execute(
        update(BackgroundTaskAttempt)
        .where(BackgroundTaskAttempt.task_id == task.id, BackgroundTaskAttempt.status == "running")
        .values(status="cancelled", finished_at=now_value, error_code="cancelled_by_admin", retryable=False)
    )
    db.commit()
    db.refresh(task)
    return task, True


def retry_background_task(db: Session, task_id: int, *, now: datetime | None = None) -> tuple[BackgroundTask, bool]:
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise LookupError("background task not found")
    if task.status not in {TASK_STATUS_DEAD_LETTER, TASK_STATUS_CANCELLED}:
        return task, False
    task.status = TASK_STATUS_PENDING
    task.available_at = now or utc_now()
    task.max_attempts = max(task.max_attempts, task.attempt_count + 1)
    task.last_error_code = None
    task.result_summary_json = {}
    task.finished_at = None
    task.lease_owner = None
    task.lease_token = None
    task.lease_expires_at = None
    task.heartbeat_at = None
    db.commit()
    db.refresh(task)
    return task, True


def _claim_eligible_expression(now: datetime):
    return or_(
        and_(
            BackgroundTask.status.in_([TASK_STATUS_PENDING, TASK_STATUS_RETRY_WAIT]),
            BackgroundTask.available_at <= now,
        ),
        and_(
            BackgroundTask.status == TASK_STATUS_LEASED,
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at <= now,
        ),
    )


def _active_lease_conditions(lease: BackgroundTaskLease, now: datetime) -> tuple:
    return (
        BackgroundTask.id == lease.task_id,
        BackgroundTask.status == TASK_STATUS_LEASED,
        BackgroundTask.lease_owner == lease.worker_id,
        BackgroundTask.lease_token == lease.lease_token,
        BackgroundTask.lease_expires_at > now,
    )


def _finish_attempt(
    db: Session,
    lease: BackgroundTaskLease,
    *,
    status: str,
    finished_at: datetime,
    error_code: str | None = None,
    retryable: bool | None = None,
    result_summary: dict[str, Any] | None = None,
) -> None:
    db.execute(
        update(BackgroundTaskAttempt)
        .where(
            BackgroundTaskAttempt.task_id == lease.task_id,
            BackgroundTaskAttempt.attempt_number == lease.attempt_number,
            BackgroundTaskAttempt.worker_id == lease.worker_id,
            BackgroundTaskAttempt.status == "running",
        )
        .values(
            status=status,
            finished_at=finished_at,
            error_code=error_code,
            retryable=retryable,
            result_summary_json=result_summary or {},
        )
    )


def _move_exhausted_tasks_to_dead_letter(db: Session, now: datetime) -> None:
    exhausted = or_(
        and_(
            BackgroundTask.status.in_([TASK_STATUS_PENDING, TASK_STATUS_RETRY_WAIT]),
            BackgroundTask.attempt_count >= BackgroundTask.max_attempts,
        ),
        and_(
            BackgroundTask.status == TASK_STATUS_LEASED,
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at <= now,
            BackgroundTask.attempt_count >= BackgroundTask.max_attempts,
        ),
    )
    task_ids = list(db.scalars(select(BackgroundTask.id).where(exhausted)).all())
    if not task_ids:
        return
    db.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id.in_(task_ids), exhausted)
        .values(
            status=TASK_STATUS_DEAD_LETTER,
            last_error_code="max_attempts_exhausted",
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
            heartbeat_at=None,
            finished_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.execute(
        update(BackgroundTaskAttempt)
        .where(
            BackgroundTaskAttempt.task_id.in_(task_ids),
            BackgroundTaskAttempt.status == "running",
        )
        .values(
            status="lease_lost",
            finished_at=now,
            error_code="max_attempts_exhausted",
            retryable=False,
        )
        .execution_options(synchronize_session=False)
    )
