from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.endpoints import knowledge as knowledge_endpoint
from app.models import ClassGroup, ClassMembership, Course, CourseClass, KnowledgeSnapshotRun, User
from app.models.base import utc_now


SnapshotGranularity = Literal["day", "week"]


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


def rebuild_periodic_knowledge_snapshots(
    db: Session,
    *,
    granularity: SnapshotGranularity,
    reference_date: date | datetime | None = None,
    trigger_source: str = "script",
) -> KnowledgeSnapshotRun:
    period_start, period_end = snapshot_window(granularity, reference_date)
    run_key = _run_key(granularity, period_start, period_end)
    run = _get_or_create_run(db, run_key, granularity, period_start, period_end, trigger_source)
    attempt_count = (run.attempt_count or 0) + 1
    run.status = "running"
    run.trigger_source = trigger_source
    run.started_at = utc_now()
    run.finished_at = None
    run.error_message = None
    run.attempt_count = attempt_count
    run.user_snapshot_count = 0
    run.class_snapshot_count = 0
    run.metadata_json = {"trigger_source": trigger_source}
    db.flush()
    try:
        counts = _rebuild_window(db, granularity, period_start, period_end)
        run.status = "success"
        run.user_snapshot_count = counts["user_snapshot_count"]
        run.class_snapshot_count = counts["class_snapshot_count"]
        run.finished_at = utc_now()
        run.metadata_json = {
            "trigger_source": trigger_source,
            "class_course_pairs": counts["class_course_pairs"],
        }
        db.commit()
    except Exception as exc:
        db.rollback()
        run = _get_or_create_run(db, run_key, granularity, period_start, period_end, trigger_source)
        run.status = "failed"
        run.trigger_source = trigger_source
        run.started_at = run.started_at or utc_now()
        run.finished_at = utc_now()
        run.attempt_count = attempt_count
        run.error_message = exc.__class__.__name__
        run.metadata_json = {"trigger_source": trigger_source}
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
        "metadata": run.metadata_json,
    }


def _rebuild_window(
    db: Session,
    granularity: SnapshotGranularity,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, int]:
    user_snapshot_count = 0
    class_snapshot_count = 0
    class_course_pairs = 0
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
        for student in _active_class_students(db, class_group.id):
            user_aggregate = knowledge_endpoint._build_user_knowledge(  # noqa: SLF001
                db,
                student.id,
                [class_group.id],
                class_group.id,
                course.id,
                period_start,
                period_end,
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
