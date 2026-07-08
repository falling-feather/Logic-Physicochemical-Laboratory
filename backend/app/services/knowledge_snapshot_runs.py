from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable, Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.endpoints import knowledge as knowledge_endpoint
from app.models import ClassGroup, ClassMembership, Course, CourseClass, KnowledgeSnapshotRun, User
from app.models.base import utc_now
from app.services.knowledge_snapshot_leases import (
    knowledge_snapshot_lease_has_any_field,
    knowledge_snapshot_lease_is_expired,
)


SnapshotGranularity = Literal["day", "week"]
CANCELLABLE_SNAPSHOT_RUN_STATUSES = {"running", "pending"}
REQUEUEABLE_SNAPSHOT_RUN_STATUSES = {"failed", "cancelled", "running"}


class SnapshotRunLeaseLost(RuntimeError):
    pass


def cancel_knowledge_snapshot_run(
    run: KnowledgeSnapshotRun,
    *,
    cancelled_by_user_id: int,
    clock: Callable[[], datetime] = utc_now,
) -> KnowledgeSnapshotRun:
    if run.status not in CANCELLABLE_SNAPSHOT_RUN_STATUSES:
        raise ValueError("knowledge snapshot run cannot be cancelled")
    if run.status == "running" and not run.scheduler_lease_token:
        raise ValueError("running knowledge snapshot run cannot be cancelled without a scheduler lease")
    cancelled_at = clock()
    previous_status = run.status
    metadata = dict(run.metadata_json or {})
    metadata["cancelled_by_user_id"] = cancelled_by_user_id
    metadata["cancelled_at"] = cancelled_at.isoformat()
    metadata["previous_status"] = previous_status
    run.status = "cancelled"
    run.finished_at = cancelled_at
    run.error_message = "cancelled_by_admin"
    run.scheduler_lease_owner = None
    run.scheduler_lease_token = None
    run.scheduler_lease_expires_at = None
    run.scheduler_heartbeat_at = None
    run.metadata_json = metadata
    return run


def requeue_knowledge_snapshot_run(
    run: KnowledgeSnapshotRun,
    *,
    requeued_by_user_id: int,
    lease_seconds: int,
    reason: str | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> KnowledgeSnapshotRun:
    requeued_at = clock()
    if run.status == "pending":
        return run
    if run.status not in REQUEUEABLE_SNAPSHOT_RUN_STATUSES:
        raise ValueError("knowledge snapshot run cannot be requeued")
    if run.status == "running" and not run.scheduler_lease_token:
        raise ValueError("running knowledge snapshot run cannot be requeued without a scheduler lease")
    if run.status == "running" and not _snapshot_run_lease_expired(run, requeued_at, lease_seconds):
        raise ValueError("running knowledge snapshot run cannot be requeued before its scheduler lease expires")
    previous_status = run.status
    previous_attempt_count = run.attempt_count
    had_scheduler_lease = knowledge_snapshot_lease_has_any_field(run)
    metadata = {
        "trigger_source": "admin_requeue",
        "requeued_by_user_id": requeued_by_user_id,
        "requeued_at": requeued_at.isoformat(),
        "previous_status": previous_status,
        "previous_attempt_count": previous_attempt_count,
        "cleared_lease": had_scheduler_lease,
    }
    if reason is not None:
        stripped_reason = reason.strip()
        if stripped_reason:
            metadata["requeue_reason"] = stripped_reason
    run.status = "pending"
    run.trigger_source = "admin_requeue"
    run.started_at = requeued_at
    run.finished_at = None
    run.error_message = None
    run.scheduler_lease_owner = None
    run.scheduler_lease_token = None
    run.scheduler_lease_expires_at = None
    run.scheduler_heartbeat_at = None
    run.attempt_count = 0
    run.user_snapshot_count = 0
    run.class_snapshot_count = 0
    run.metadata_json = metadata
    return run


def snapshot_window(
    granularity: SnapshotGranularity,
    reference_date: date | datetime | None = None,
) -> tuple[datetime, datetime]:
    date_value = _date_value(reference_date)
    if granularity == "day":
        start_date = date_value
        days = 1
    elif granularity == "week":
        start_date = date_value - timedelta(days=date_value.weekday())
        days = 7
    else:
        raise ValueError("granularity must be day or week")
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(start_date + timedelta(days=days), time.min) - timedelta(microseconds=1)
    return start, end


def _snapshot_run_lease_expired(run: KnowledgeSnapshotRun, now: datetime, lease_seconds: int) -> bool:
    return knowledge_snapshot_lease_is_expired(run, now, lease_seconds)


def rebuild_periodic_knowledge_snapshots(
    db: Session,
    *,
    granularity: SnapshotGranularity,
    reference_date: date | datetime | None = None,
    trigger_source: str = "script",
    scheduler_lease_owner: str | None = None,
    scheduler_lease_token: str | None = None,
    scheduler_lease_heartbeat: Callable[[], bool] | None = None,
    scheduler_heartbeat_seconds: int | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> KnowledgeSnapshotRun:
    period_start, period_end = snapshot_window(granularity, reference_date)
    run_key = _run_key(granularity, period_start, period_end)
    run = _get_or_create_run(db, run_key, granularity, period_start, period_end, trigger_source)
    attempt_count = (run.attempt_count or 0) + 1
    run = _start_run(
        db,
        run,
        trigger_source=trigger_source,
        attempt_count=attempt_count,
        scheduler_lease_owner=scheduler_lease_owner,
        scheduler_lease_token=scheduler_lease_token,
        clock=clock,
    )
    try:
        heartbeat = _SnapshotRunHeartbeat(
            heartbeat=scheduler_lease_heartbeat,
            heartbeat_seconds=scheduler_heartbeat_seconds,
            clock=clock,
        )
        counts = _rebuild_window(db, granularity, period_start, period_end, heartbeat=heartbeat)
        success_metadata = {
            "trigger_source": trigger_source,
            "class_course_pairs": counts["class_course_pairs"],
        }
        _finish_run_success(
            db,
            run,
            user_snapshot_count=counts["user_snapshot_count"],
            class_snapshot_count=counts["class_snapshot_count"],
            metadata_json=success_metadata,
            scheduler_lease_owner=scheduler_lease_owner,
            scheduler_lease_token=scheduler_lease_token,
            clock=clock,
        )
        db.commit()
        db.refresh(run)
    except Exception as exc:
        db.rollback()
        if isinstance(exc, SnapshotRunLeaseLost):
            raise
        run = _get_or_create_run(db, run_key, granularity, period_start, period_end, trigger_source)
        _finish_run_failure(
            db,
            run,
            trigger_source=trigger_source,
            attempt_count=attempt_count,
            error_message=exc.__class__.__name__,
            scheduler_lease_owner=scheduler_lease_owner,
            scheduler_lease_token=scheduler_lease_token,
            clock=clock,
        )
        db.commit()
        raise
    return run


def snapshot_run_report(run: KnowledgeSnapshotRun) -> dict:
    return {
        "ok": run.status == "success",
        "id": run.id,
        "run_key": run.run_key,
        "granularity": run.granularity,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "trigger_source": run.trigger_source,
        "status": run.status,
        "attempt_count": run.attempt_count,
        "user_snapshot_count": run.user_snapshot_count,
        "class_snapshot_count": run.class_snapshot_count,
        "error_message": run.error_message,
        "metadata_present": bool(run.metadata_json),
        "metadata_redacted": bool(run.metadata_json),
        "sensitive_fields_returned": False,
    }


def _rebuild_window(
    db: Session,
    granularity: SnapshotGranularity,
    period_start: datetime,
    period_end: datetime,
    *,
    heartbeat: "_SnapshotRunHeartbeat | None" = None,
) -> dict[str, int]:
    user_snapshot_count = 0
    class_snapshot_count = 0
    class_course_pairs = 0
    if heartbeat is not None:
        heartbeat.maybe()
    for class_group, course in _active_class_courses(db):
        class_course_pairs += 1
        created_by_user_id = _class_snapshot_actor_id(db, class_group, course)
        class_aggregate = knowledge_endpoint._build_class_knowledge(  # noqa: SLF001
            db,
            class_group,
            course.id,
            period_start,
            period_end,
        )
        knowledge_endpoint._upsert_class_knowledge_snapshot(  # noqa: SLF001
            db,
            aggregate=class_aggregate,
            class_group=class_group,
            created_by_user_id=created_by_user_id,
            granularity=granularity,
            from_at=period_start,
            to_at=period_end,
        )
        class_snapshot_count += 1
        if heartbeat is not None:
            heartbeat.maybe()
        if course.status != "published":
            continue
        for student in _active_class_students(db, class_group.id):
            user_aggregate = knowledge_endpoint._build_user_knowledge(  # noqa: SLF001
                db,
                student.id,
                [class_group.id],
                class_group.id,
                course.id,
                period_start,
                period_end,
                student_visible_resources=True,
            )
            knowledge_endpoint._upsert_user_knowledge_snapshot(  # noqa: SLF001
                db,
                aggregate=user_aggregate,
                current_user=student,
                class_group=class_group,
                course=course,
                granularity=granularity,
                from_at=period_start,
                to_at=period_end,
            )
            user_snapshot_count += 1
            if heartbeat is not None:
                heartbeat.maybe()
    return {
        "class_course_pairs": class_course_pairs,
        "class_snapshot_count": class_snapshot_count,
        "user_snapshot_count": user_snapshot_count,
    }


def _active_class_courses(db: Session) -> list[tuple[ClassGroup, Course]]:
    return list(
        db.execute(
            select(ClassGroup, Course)
            .join(CourseClass, CourseClass.class_id == ClassGroup.id)
            .join(Course, Course.id == CourseClass.course_id)
            .where(ClassGroup.status == "active", CourseClass.status == "active")
            .order_by(ClassGroup.id, Course.id)
        ).all()
    )


def _active_class_students(db: Session, class_id: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(ClassMembership, ClassMembership.user_id == User.id)
            .where(
                ClassMembership.class_id == class_id,
                ClassMembership.role == "student",
                ClassMembership.status == "active",
                User.status == "active",
            )
            .order_by(User.id)
        ).all()
    )


def _class_snapshot_actor_id(db: Session, class_group: ClassGroup, course: Course) -> int:
    teacher_id = db.scalar(
        select(ClassMembership.user_id)
        .where(
            ClassMembership.class_id == class_group.id,
            ClassMembership.role == "teacher",
            ClassMembership.status == "active",
        )
        .order_by(ClassMembership.id)
    )
    return int(teacher_id or course.creator_user_id)


def _get_or_create_run(
    db: Session,
    run_key: str,
    granularity: SnapshotGranularity,
    period_start: datetime,
    period_end: datetime,
    trigger_source: str,
) -> KnowledgeSnapshotRun:
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if run is not None:
        return run
    run = KnowledgeSnapshotRun(
        run_key=run_key,
        granularity=granularity,
        period_start=period_start,
        period_end=period_end,
        trigger_source=trigger_source,
        status="running",
        started_at=utc_now(),
    )
    db.add(run)
    return run


def _start_run(
    db: Session,
    run: KnowledgeSnapshotRun,
    *,
    trigger_source: str,
    attempt_count: int,
    scheduler_lease_owner: str | None,
    scheduler_lease_token: str | None,
    clock: Callable[[], datetime],
) -> KnowledgeSnapshotRun:
    started_at = clock()
    if scheduler_lease_owner is None:
        run.status = "running"
        run.trigger_source = trigger_source
        run.started_at = started_at
        run.finished_at = None
        run.error_message = None
        run.attempt_count = attempt_count
        run.user_snapshot_count = 0
        run.class_snapshot_count = 0
        run.metadata_json = {"trigger_source": trigger_source}
        db.commit()
        db.refresh(run)
        return run
    if not scheduler_lease_token:
        db.rollback()
        raise SnapshotRunLeaseLost("knowledge snapshot run lease token was missing before start")
    result = db.execute(
        update(KnowledgeSnapshotRun)
        .where(
            KnowledgeSnapshotRun.id == run.id,
            KnowledgeSnapshotRun.status == "running",
            KnowledgeSnapshotRun.scheduler_lease_owner == scheduler_lease_owner,
            KnowledgeSnapshotRun.scheduler_lease_token == scheduler_lease_token,
            KnowledgeSnapshotRun.scheduler_lease_expires_at.is_not(None),
            KnowledgeSnapshotRun.scheduler_lease_expires_at > started_at,
            KnowledgeSnapshotRun.scheduler_heartbeat_at.is_not(None),
        )
        .values(
            trigger_source=trigger_source,
            started_at=started_at,
            finished_at=None,
            error_message=None,
            attempt_count=attempt_count,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={"trigger_source": trigger_source, "scheduler_lease_owner": scheduler_lease_owner},
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise SnapshotRunLeaseLost("knowledge snapshot run lease was lost before start")
    db.commit()
    db.refresh(run)
    return run


def _finish_run_success(
    db: Session,
    run: KnowledgeSnapshotRun,
    *,
    user_snapshot_count: int,
    class_snapshot_count: int,
    metadata_json: dict,
    scheduler_lease_owner: str | None,
    scheduler_lease_token: str | None,
    clock: Callable[[], datetime],
) -> None:
    finished_at = clock()
    if scheduler_lease_owner is None:
        run.status = "success"
        run.user_snapshot_count = user_snapshot_count
        run.class_snapshot_count = class_snapshot_count
        run.finished_at = finished_at
        run.metadata_json = metadata_json
        return
    result = db.execute(
        update(KnowledgeSnapshotRun)
        .where(
            KnowledgeSnapshotRun.id == run.id,
            KnowledgeSnapshotRun.status == "running",
            KnowledgeSnapshotRun.scheduler_lease_owner == scheduler_lease_owner,
            KnowledgeSnapshotRun.scheduler_lease_token == scheduler_lease_token,
            KnowledgeSnapshotRun.scheduler_lease_expires_at.is_not(None),
            KnowledgeSnapshotRun.scheduler_lease_expires_at > finished_at,
            KnowledgeSnapshotRun.scheduler_heartbeat_at.is_not(None),
        )
        .values(
            status="success",
            user_snapshot_count=user_snapshot_count,
            class_snapshot_count=class_snapshot_count,
            finished_at=finished_at,
            error_message=None,
            scheduler_lease_owner=None,
            scheduler_lease_token=None,
            scheduler_lease_expires_at=None,
            scheduler_heartbeat_at=None,
            metadata_json=metadata_json,
        )
    )
    if result.rowcount != 1:
        raise SnapshotRunLeaseLost("knowledge snapshot run lease was lost or expired before success")


def _finish_run_failure(
    db: Session,
    run: KnowledgeSnapshotRun,
    *,
    trigger_source: str,
    attempt_count: int,
    error_message: str,
    scheduler_lease_owner: str | None,
    scheduler_lease_token: str | None,
    clock: Callable[[], datetime],
) -> None:
    finished_at = clock()
    if scheduler_lease_owner is None:
        run.status = "failed"
        run.trigger_source = trigger_source
        run.started_at = run.started_at or finished_at
        run.finished_at = finished_at
        run.attempt_count = attempt_count
        run.error_message = error_message
        run.metadata_json = {"trigger_source": trigger_source}
        return
    result = db.execute(
        update(KnowledgeSnapshotRun)
        .where(
            KnowledgeSnapshotRun.id == run.id,
            KnowledgeSnapshotRun.status == "running",
            KnowledgeSnapshotRun.scheduler_lease_owner == scheduler_lease_owner,
            KnowledgeSnapshotRun.scheduler_lease_token == scheduler_lease_token,
            KnowledgeSnapshotRun.scheduler_lease_expires_at.is_not(None),
            KnowledgeSnapshotRun.scheduler_lease_expires_at > finished_at,
            KnowledgeSnapshotRun.scheduler_heartbeat_at.is_not(None),
        )
        .values(
            status="failed",
            trigger_source=trigger_source,
            finished_at=finished_at,
            attempt_count=attempt_count,
            error_message=error_message,
            scheduler_lease_owner=None,
            scheduler_lease_token=None,
            scheduler_lease_expires_at=None,
            scheduler_heartbeat_at=None,
            metadata_json={"trigger_source": trigger_source},
        )
    )
    if result.rowcount != 1:
        raise SnapshotRunLeaseLost("knowledge snapshot run lease was lost or expired before failure")


class _SnapshotRunHeartbeat:
    def __init__(
        self,
        *,
        heartbeat: Callable[[], bool] | None,
        heartbeat_seconds: int | None,
        clock: Callable[[], datetime],
    ) -> None:
        self.heartbeat = heartbeat
        self.heartbeat_seconds = heartbeat_seconds
        self.clock = clock
        self.last_heartbeat_at = clock()

    def maybe(self) -> None:
        if self.heartbeat is None or self.heartbeat_seconds is None:
            return
        now = self.clock()
        elapsed_seconds = (now - self.last_heartbeat_at).total_seconds()
        if elapsed_seconds < self.heartbeat_seconds:
            return
        if not self.heartbeat():
            raise SnapshotRunLeaseLost("knowledge snapshot run lease heartbeat failed")
        self.last_heartbeat_at = now


def _run_key(granularity: SnapshotGranularity, period_start: datetime, period_end: datetime) -> str:
    return snapshot_run_key(granularity, period_start, period_end)


def snapshot_run_key(granularity: SnapshotGranularity, period_start: datetime, period_end: datetime) -> str:
    return f"knowledge:{granularity}:{period_start.isoformat()}:{period_end.isoformat()}"


def _date_value(reference_date: date | datetime | None) -> date:
    if reference_date is None:
        return utc_now().date()
    if isinstance(reference_date, datetime):
        return reference_date.date()
    return reference_date
