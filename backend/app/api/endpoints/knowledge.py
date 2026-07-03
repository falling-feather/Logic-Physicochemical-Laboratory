from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    ClassKnowledgeSnapshot,
    ClassGroup,
    ClassMembership,
    Course,
    CourseClass,
    CourseUnit,
    LearningEvent,
    PointLedger,
    SchoolMembership,
    Submission,
    User,
)
from app.models.base import utc_now
from app.schemas.knowledge import (
    ClassKnowledgeRead,
    ClassKnowledgeSnapshotPage,
    ClassKnowledgeSnapshotRead,
    KnowledgeSnapshotGranularity,
    KnowledgeStatRead,
    UserKnowledgeRead,
)
from app.services.audit import record_audit_log


router = APIRouter()


@router.get("/knowledge/me", response_model=UserKnowledgeRead)
def get_my_knowledge(
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserKnowledgeRead:
    _validate_period(from_at, to_at)
    class_group: ClassGroup | None = None
    if class_id is not None:
        class_group = _require_class_member(db, current_user, class_id)
    if course_id is not None:
        _require_course_scope(db, current_user, class_group, course_id)
    assignment_class_ids = (
        None
        if current_user.role == "admin" and class_id is None
        else _user_assignment_class_ids(db, current_user.id, class_id)
    )
    return _build_user_knowledge(db, current_user.id, assignment_class_ids, class_id, course_id, from_at, to_at)


@router.get("/classes/{class_id}/knowledge", response_model=ClassKnowledgeRead)
def get_class_knowledge(
    class_id: int,
    course_id: int | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassKnowledgeRead:
    _validate_period(from_at, to_at)
    class_group = _get_class(db, class_id)
    _require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        _require_course_scope(db, current_user, class_group, course_id)
    return _build_class_knowledge(db, class_group, course_id, from_at, to_at)


@router.post(
    "/classes/{class_id}/knowledge/snapshots",
    response_model=ClassKnowledgeSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def rebuild_class_knowledge_snapshot(
    class_id: int,
    request: Request,
    course_id: int | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    granularity: KnowledgeSnapshotGranularity = Query(default="custom"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassKnowledgeSnapshotRead:
    _validate_snapshot_period(from_at, to_at)
    class_group = _get_class(db, class_id)
    _require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        _require_course_scope(db, current_user, class_group, course_id)

    aggregate = _build_class_knowledge(db, class_group, course_id, from_at, to_at)
    snapshot = _upsert_class_knowledge_snapshot(
        db,
        aggregate=aggregate,
        class_group=class_group,
        created_by_user_id=current_user.id,
        granularity=granularity,
        from_at=from_at,
        to_at=to_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="knowledge.snapshot.rebuild",
        resource_type="class_knowledge_snapshot",
        resource_id=snapshot.id,
        school_id=class_group.school_id,
        class_id=class_group.id,
        event_result="success",
        request=request,
        snapshot={
            "after": {
                "class_id": class_group.id,
                "course_id": course_id,
                "granularity": granularity,
                "period_start": from_at.isoformat() if from_at is not None else None,
                "period_end": to_at.isoformat() if to_at is not None else None,
                "rule_version": snapshot.rule_version,
                "students_total": aggregate.students_total,
                "students_active": aggregate.students_active,
                "knowledge_stat_rules": [item.rule_code for item in aggregate.knowledge_stats],
            }
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_read(snapshot)


@router.get("/classes/{class_id}/knowledge/snapshots", response_model=ClassKnowledgeSnapshotPage)
def list_class_knowledge_snapshots(
    class_id: int,
    course_id: int | None = Query(default=None),
    granularity: KnowledgeSnapshotGranularity | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassKnowledgeSnapshotPage:
    _validate_period(from_at, to_at)
    class_group = _get_class(db, class_id)
    _require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        _require_course_scope(db, current_user, class_group, course_id)

    statement = select(ClassKnowledgeSnapshot).where(ClassKnowledgeSnapshot.class_id == class_group.id)
    if course_id is not None:
        statement = statement.where(ClassKnowledgeSnapshot.course_id == course_id)
    if granularity is not None:
        statement = statement.where(ClassKnowledgeSnapshot.granularity == granularity)
    if from_at is not None:
        statement = statement.where(ClassKnowledgeSnapshot.period_start >= from_at)
    if to_at is not None:
        statement = statement.where(ClassKnowledgeSnapshot.period_end <= to_at)
    statement = statement.order_by(ClassKnowledgeSnapshot.period_end.desc(), ClassKnowledgeSnapshot.id.desc())
    total = _statement_count(db, statement)
    snapshots = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return ClassKnowledgeSnapshotPage(
        items=[_snapshot_to_read(snapshot) for snapshot in snapshots],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(snapshots)),
    )


def _build_user_knowledge(
    db: Session,
    user_id: int,
    assignment_class_ids: list[int] | None,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> UserKnowledgeRead:
    assignment_count = _active_assignment_count(db, assignment_class_ids, course_id)
    submitted_assignments = _submission_count(db, user_id, class_id, course_id, from_at, to_at, graded=False)
    graded_assignments = _submission_count(db, user_id, class_id, course_id, from_at, to_at, graded=True)
    score_total, max_score_total = _score_totals(db, user_id, class_id, course_id, from_at, to_at)
    event_counts = _event_counts(
        db,
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
    )
    total_points = _point_total(
        db,
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
    )
    accuracy_percent = _percent(score_total, max_score_total)
    completion_percent = _percent(event_counts["complete"], event_counts["total"])
    stats = _knowledge_stats(
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        assignment_count=assignment_count,
        submitted_assignments=submitted_assignments,
        graded_assignments=graded_assignments,
        total_events=event_counts["total"],
        complete_events=event_counts["complete"],
        score_total=score_total,
        max_score_total=max_score_total,
    )
    return UserKnowledgeRead(
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        period_start=from_at,
        period_end=to_at,
        assignment_count=assignment_count,
        submitted_assignments=submitted_assignments,
        graded_assignments=graded_assignments,
        total_events=event_counts["total"],
        visit_events=event_counts["visit"],
        start_events=event_counts["start"],
        submit_events=event_counts["submit"],
        complete_events=event_counts["complete"],
        score_total=score_total,
        max_score_total=max_score_total,
        accuracy_percent=accuracy_percent,
        completion_percent=completion_percent,
        total_points=total_points,
        knowledge_stats=stats,
    )


def _build_class_knowledge(
    db: Session,
    class_group: ClassGroup,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> ClassKnowledgeRead:
    student_ids = _active_class_student_ids(db, class_group.id)
    students_total = len(student_ids)
    assignment_count = _active_assignment_count(db, [class_group.id], course_id)
    submitted_assignments = _class_submission_count(db, class_group.id, course_id, from_at, to_at, graded=False)
    graded_assignments = _class_submission_count(db, class_group.id, course_id, from_at, to_at, graded=True)
    score_total, max_score_total = _class_score_totals(db, class_group.id, course_id, from_at, to_at)
    event_counts = _event_counts(
        db,
        user_id=None,
        class_id=class_group.id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
    )
    total_points = _point_total(
        db,
        user_id=None,
        class_id=class_group.id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
    )
    active_user_ids = _class_active_user_ids(db, class_group.id, course_id, from_at, to_at)
    students_active = len(set(student_ids).intersection(active_user_ids))
    expected_submissions = students_total * assignment_count
    average_score_percent = _percent(score_total, max_score_total)
    completion_percent = _percent(event_counts["complete"], event_counts["total"])
    stats = _knowledge_stats(
        user_id=None,
        class_id=class_group.id,
        course_id=course_id,
        assignment_count=expected_submissions,
        submitted_assignments=submitted_assignments,
        graded_assignments=graded_assignments,
        total_events=event_counts["total"],
        complete_events=event_counts["complete"],
        score_total=score_total,
        max_score_total=max_score_total,
    )
    return ClassKnowledgeRead(
        class_id=class_group.id,
        school_id=class_group.school_id,
        course_id=course_id,
        period_start=from_at,
        period_end=to_at,
        students_total=students_total,
        students_active=students_active,
        assignment_count=assignment_count,
        expected_submissions=expected_submissions,
        submitted_assignments=submitted_assignments,
        graded_assignments=graded_assignments,
        total_events=event_counts["total"],
        complete_events=event_counts["complete"],
        score_total=score_total,
        max_score_total=max_score_total,
        average_score_percent=average_score_percent,
        completion_percent=completion_percent,
        total_points=total_points,
        average_points_per_student=_average(total_points, students_total),
        knowledge_stats=stats,
    )


def _upsert_class_knowledge_snapshot(
    db: Session,
    *,
    aggregate: ClassKnowledgeRead,
    class_group: ClassGroup,
    created_by_user_id: int,
    granularity: KnowledgeSnapshotGranularity,
    from_at: datetime,
    to_at: datetime,
) -> ClassKnowledgeSnapshot:
    course_scope_id = aggregate.course_id or 0
    snapshot = db.scalar(
        select(ClassKnowledgeSnapshot).where(
            ClassKnowledgeSnapshot.class_id == class_group.id,
            ClassKnowledgeSnapshot.course_scope_id == course_scope_id,
            ClassKnowledgeSnapshot.granularity == granularity,
            ClassKnowledgeSnapshot.period_start == from_at,
            ClassKnowledgeSnapshot.period_end == to_at,
            ClassKnowledgeSnapshot.rule_version == "v1",
        )
    )
    if snapshot is None:
        snapshot = ClassKnowledgeSnapshot(
            school_id=class_group.school_id,
            class_id=class_group.id,
            course_id=aggregate.course_id,
            course_scope_id=course_scope_id,
            granularity=granularity,
            period_start=from_at,
            period_end=to_at,
            rule_version="v1",
            created_by_user_id=created_by_user_id,
        )
        db.add(snapshot)
    else:
        snapshot.created_by_user_id = created_by_user_id
    _apply_class_knowledge_snapshot(snapshot, aggregate)
    db.flush()
    return snapshot


def _apply_class_knowledge_snapshot(snapshot: ClassKnowledgeSnapshot, aggregate: ClassKnowledgeRead) -> None:
    snapshot.students_total = aggregate.students_total
    snapshot.students_active = aggregate.students_active
    snapshot.assignment_count = aggregate.assignment_count
    snapshot.expected_submissions = aggregate.expected_submissions
    snapshot.submitted_assignments = aggregate.submitted_assignments
    snapshot.graded_assignments = aggregate.graded_assignments
    snapshot.total_events = aggregate.total_events
    snapshot.complete_events = aggregate.complete_events
    snapshot.score_total = aggregate.score_total
    snapshot.max_score_total = aggregate.max_score_total
    snapshot.average_score_percent = aggregate.average_score_percent
    snapshot.completion_percent = aggregate.completion_percent
    snapshot.total_points = aggregate.total_points
    snapshot.average_points_per_student = aggregate.average_points_per_student
    snapshot.knowledge_stats_json = [stat.model_dump() for stat in aggregate.knowledge_stats]
    snapshot.calculated_at = utc_now()


def _snapshot_to_read(snapshot: ClassKnowledgeSnapshot) -> ClassKnowledgeSnapshotRead:
    return ClassKnowledgeSnapshotRead(
        id=snapshot.id,
        school_id=snapshot.school_id,
        class_id=snapshot.class_id,
        course_id=snapshot.course_id,
        granularity=snapshot.granularity,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        rule_version=snapshot.rule_version,
        created_by_user_id=snapshot.created_by_user_id,
        calculated_at=snapshot.calculated_at,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
        students_total=snapshot.students_total,
        students_active=snapshot.students_active,
        assignment_count=snapshot.assignment_count,
        expected_submissions=snapshot.expected_submissions,
        submitted_assignments=snapshot.submitted_assignments,
        graded_assignments=snapshot.graded_assignments,
        total_events=snapshot.total_events,
        complete_events=snapshot.complete_events,
        score_total=snapshot.score_total,
        max_score_total=snapshot.max_score_total,
        average_score_percent=snapshot.average_score_percent,
        completion_percent=snapshot.completion_percent,
        total_points=snapshot.total_points,
        average_points_per_student=snapshot.average_points_per_student,
        knowledge_stats=snapshot.knowledge_stats_json,
    )


def _knowledge_stats(
    *,
    user_id: int | None,
    class_id: int | None,
    course_id: int | None,
    assignment_count: int,
    submitted_assignments: int,
    graded_assignments: int,
    total_events: int,
    complete_events: int,
    score_total: int,
    max_score_total: int,
) -> list[KnowledgeStatRead]:
    return [
        KnowledgeStatRead(
            rule_code="assignment_completion",
            user_id=user_id,
            class_id=class_id,
            course_id=course_id,
            frequency=submitted_assignments,
            sample_size=assignment_count,
            percent=_percent(submitted_assignments, assignment_count),
            evidence={
                "assigned_assignments": assignment_count,
                "submitted_assignments": submitted_assignments,
            },
        ),
        KnowledgeStatRead(
            rule_code="graded_score",
            user_id=user_id,
            class_id=class_id,
            course_id=course_id,
            frequency=score_total,
            sample_size=max_score_total,
            percent=_percent(score_total, max_score_total),
            evidence={
                "graded_assignments": graded_assignments,
                "score_total": score_total,
                "max_score_total": max_score_total,
            },
        ),
        KnowledgeStatRead(
            rule_code="learning_completion",
            user_id=user_id,
            class_id=class_id,
            course_id=course_id,
            frequency=complete_events,
            sample_size=total_events,
            percent=_percent(complete_events, total_events),
            evidence={
                "learning_events": total_events,
                "complete_events": complete_events,
            },
        ),
    ]


def _active_assignment_count(db: Session, class_ids: list[int] | None, course_id: int | None) -> int:
    statement = (
        select(func.count(func.distinct(Assignment.id)))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .where(Assignment.status == "active")
    )
    if course_id is not None:
        statement = statement.where(CourseUnit.course_id == course_id)
    if class_ids is not None:
        if not class_ids:
            return 0
        statement = statement.join(Course, Course.id == CourseUnit.course_id).join(
            CourseClass,
            CourseClass.course_id == Course.id,
        )
        statement = statement.where(CourseClass.class_id.in_(class_ids), CourseClass.status == "active")
    return int(db.scalar(statement) or 0)


def _submission_count(
    db: Session,
    user_id: int,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    graded: bool,
) -> int:
    statement = select(func.count(func.distinct(Submission.id))).select_from(Submission)
    statement = statement.where(Submission.student_id == user_id)
    statement = _apply_submission_filters(statement, class_id, course_id, from_at, to_at, graded)
    return int(db.scalar(statement) or 0)


def _class_submission_count(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    graded: bool,
) -> int:
    statement = select(func.count(func.distinct(Submission.id))).select_from(Submission)
    statement = _apply_submission_filters(statement, class_id, course_id, from_at, to_at, graded)
    return int(db.scalar(statement) or 0)


def _score_totals(
    db: Session,
    user_id: int,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[int, int]:
    statement = (
        select(func.coalesce(func.sum(Submission.score), 0), func.coalesce(func.sum(Assignment.max_score), 0))
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Submission.student_id == user_id)
    )
    statement = _apply_submission_filters(
        statement,
        class_id,
        course_id,
        from_at,
        to_at,
        graded=True,
        assignment_joined=True,
    )
    score_total, max_score_total = db.execute(statement).one()
    return int(score_total or 0), int(max_score_total or 0)


def _class_score_totals(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[int, int]:
    statement = (
        select(func.coalesce(func.sum(Submission.score), 0), func.coalesce(func.sum(Assignment.max_score), 0))
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
    )
    statement = _apply_submission_filters(
        statement,
        class_id,
        course_id,
        from_at,
        to_at,
        graded=True,
        assignment_joined=True,
    )
    score_total, max_score_total = db.execute(statement).one()
    return int(score_total or 0), int(max_score_total or 0)


def _apply_submission_filters(
    statement,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    graded: bool,
    *,
    assignment_joined: bool = False,
):
    if class_id is not None:
        statement = statement.where(Submission.class_id == class_id)
    if course_id is not None:
        if not assignment_joined:
            statement = statement.join(Assignment, Assignment.id == Submission.assignment_id)
        statement = statement.join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        statement = statement.where(CourseUnit.course_id == course_id)
    if graded:
        statement = statement.where(Submission.score.is_not(None), Submission.graded_at.is_not(None))
        if from_at is not None:
            statement = statement.where(Submission.graded_at >= from_at)
        if to_at is not None:
            statement = statement.where(Submission.graded_at <= to_at)
    else:
        if from_at is not None:
            statement = statement.where(Submission.submitted_at >= from_at)
        if to_at is not None:
            statement = statement.where(Submission.submitted_at <= to_at)
    return statement


def _event_counts(
    db: Session,
    *,
    user_id: int | None,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, int]:
    statement = select(LearningEvent.event_type, func.count()).group_by(LearningEvent.event_type)
    if user_id is not None:
        statement = statement.where(LearningEvent.user_id == user_id)
    if class_id is not None:
        statement = statement.where(LearningEvent.class_id == class_id)
    if course_id is not None:
        statement = statement.where(LearningEvent.course_id == course_id)
    if from_at is not None:
        statement = statement.where(LearningEvent.occurred_at >= from_at)
    if to_at is not None:
        statement = statement.where(LearningEvent.occurred_at <= to_at)
    counts = {"visit": 0, "start": 0, "submit": 0, "complete": 0}
    for event_type, count in db.execute(statement).all():
        if event_type in counts:
            counts[event_type] = int(count or 0)
    counts["total"] = sum(counts.values())
    return counts


def _point_total(
    db: Session,
    *,
    user_id: int | None,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> int:
    statement = select(func.coalesce(func.sum(PointLedger.delta), 0)).select_from(PointLedger)
    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    if class_id is not None:
        statement = statement.where(PointLedger.class_id == class_id)
    if course_id is not None:
        statement = statement.join(Assignment, Assignment.id == PointLedger.assignment_id).join(
            CourseUnit,
            CourseUnit.id == Assignment.unit_id,
        )
        statement = statement.where(CourseUnit.course_id == course_id)
    if from_at is not None:
        statement = statement.where(PointLedger.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(PointLedger.created_at <= to_at)
    return int(db.scalar(statement) or 0)


def _active_class_student_ids(db: Session, class_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.user_id).where(
                ClassMembership.class_id == class_id,
                ClassMembership.role == "student",
                ClassMembership.status == "active",
            )
        ).all()
    )


def _class_active_user_ids(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> set[int]:
    event_statement = select(func.distinct(LearningEvent.user_id)).where(LearningEvent.class_id == class_id)
    if course_id is not None:
        event_statement = event_statement.where(LearningEvent.course_id == course_id)
    if from_at is not None:
        event_statement = event_statement.where(LearningEvent.occurred_at >= from_at)
    if to_at is not None:
        event_statement = event_statement.where(LearningEvent.occurred_at <= to_at)

    submission_statement = select(func.distinct(Submission.student_id)).where(Submission.class_id == class_id)
    if course_id is not None:
        submission_statement = submission_statement.join(Assignment, Assignment.id == Submission.assignment_id).join(
            CourseUnit,
            CourseUnit.id == Assignment.unit_id,
        )
        submission_statement = submission_statement.where(CourseUnit.course_id == course_id)
    if from_at is not None:
        submission_statement = submission_statement.where(Submission.submitted_at >= from_at)
    if to_at is not None:
        submission_statement = submission_statement.where(Submission.submitted_at <= to_at)

    return set(db.scalars(event_statement).all()).union(db.scalars(submission_statement).all())


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _require_course_scope(
    db: Session,
    user: User,
    class_group: ClassGroup | None,
    course_id: int,
) -> Course:
    course = _get_course(db, course_id)
    if class_group is not None:
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to course school")
        if not _course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        return course
    return _require_course_visible(db, user, course_id)


def _require_course_visible(db: Session, user: User, course_id: int) -> Course:
    course = _get_course(db, course_id)
    if user.role == "admin":
        return course
    school_membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == course.school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.role.in_(["admin", "teacher"]),
            SchoolMembership.status == "active",
        )
    )
    if school_membership is not None:
        return course
    class_ids = _visible_class_ids(db, user.id)
    if class_ids:
        course_class = db.scalar(
            select(CourseClass).where(
                CourseClass.course_id == course.id,
                CourseClass.class_id.in_(class_ids),
                CourseClass.status == "active",
            )
        )
        if course_class is not None:
            return course
    raise HTTPException(status_code=403, detail="Course is outside current user scope")


def _require_class_member(db: Session, user: User, class_id: int) -> ClassGroup:
    class_group = _get_class(db, class_id)
    if user.role == "admin":
        return class_group
    membership = db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user.id,
            ClassMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Class is outside current user scope")
    return class_group


def _require_class_teacher_or_admin(db: Session, user: User, class_group: ClassGroup) -> None:
    if user.role == "admin":
        return
    membership = db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_group.id,
            ClassMembership.user_id == user.id,
            ClassMembership.role == "teacher",
            ClassMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Class statistics require teacher scope")


def _visible_class_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.class_id).where(
                ClassMembership.user_id == user_id,
                ClassMembership.status == "active",
            )
        ).all()
    )


def _user_assignment_class_ids(db: Session, user_id: int, class_id: int | None) -> list[int]:
    if class_id is not None:
        return [class_id]
    return _visible_class_ids(db, user_id)


def _course_attached_to_class(db: Session, course_id: int, class_id: int) -> bool:
    return (
        db.scalar(
            select(CourseClass).where(
                CourseClass.course_id == course_id,
                CourseClass.class_id == class_id,
                CourseClass.status == "active",
            )
        )
        is not None
    )


def _validate_period(from_at: datetime | None, to_at: datetime | None) -> None:
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")


def _validate_snapshot_period(from_at: datetime | None, to_at: datetime | None) -> None:
    if from_at is None or to_at is None:
        raise HTTPException(status_code=422, detail="Snapshot period requires from and to")
    _validate_period(from_at, to_at)


def _statement_count(db: Session, statement) -> int:
    return int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)


def _next_offset(total: int, offset: int, item_count: int) -> int | None:
    next_offset = offset + item_count
    return next_offset if next_offset < total else None


def _percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _average(total: int, count: int) -> float:
    return round(total / count, 2) if count else 0.0
