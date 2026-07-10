from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    AssignmentClassPolicy,
    ClassKnowledgeSnapshot,
    ClassGroup,
    Course,
    CourseClass,
    CourseUnit,
    LearningEvent,
    PointLedger,
    Submission,
    User,
    UserKnowledgeSnapshot,
)
from app.models.base import utc_now
from app.schemas.knowledge import (
    ClassKnowledgeRead,
    ClassKnowledgeSnapshotPage,
    ClassKnowledgeSnapshotRead,
    KnowledgeSnapshotGranularity,
    KnowledgeStatRead,
    UserKnowledgeSnapshotPage,
    UserKnowledgeSnapshotRead,
    UserKnowledgeRead,
)
from app.services.audit import record_audit_log
from app.services.assignment_policies import (
    assignment_class_effective_status_expression,
    assignment_class_is_assigned_expression,
)
from app.services.access_control import (
    active_class_student_ids,
    course_attached_to_class,
    get_class,
    require_class_member,
    require_class_teacher_or_admin,
    require_course_scope,
    user_assignment_class_ids,
)


router = APIRouter()

KNOWLEDGE_RULE_VERSION = "v2"


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
        class_group = require_class_member(db, current_user, class_id)
    if course_id is not None:
        require_course_scope(db, current_user, class_group, course_id)
    assignment_class_ids = (
        None
        if current_user.role == "admin" and class_id is None
        else user_assignment_class_ids(db, current_user.id, class_id)
    )
    return _build_user_knowledge(
        db,
        current_user.id,
        assignment_class_ids,
        class_id,
        course_id,
        from_at,
        to_at,
        student_visible_resources=current_user.role == "student",
    )


@router.post(
    "/knowledge/me/snapshots",
    response_model=UserKnowledgeSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def rebuild_my_knowledge_snapshot(
    request: Request,
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    granularity: KnowledgeSnapshotGranularity = Query(default="custom"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserKnowledgeSnapshotRead:
    _validate_snapshot_period(from_at, to_at)
    class_group: ClassGroup | None = None
    course: Course | None = None
    if class_id is not None:
        class_group = require_class_member(db, current_user, class_id)
    if course_id is not None:
        course = require_course_scope(db, current_user, class_group, course_id)
    assignment_class_ids = (
        None
        if current_user.role == "admin" and class_id is None
        else user_assignment_class_ids(db, current_user.id, class_id)
    )
    aggregate = _build_user_knowledge(
        db,
        current_user.id,
        assignment_class_ids,
        class_id,
        course_id,
        from_at,
        to_at,
        student_visible_resources=current_user.role == "student",
    )
    snapshot = _upsert_user_knowledge_snapshot(
        db,
        aggregate=aggregate,
        current_user=current_user,
        class_group=class_group,
        course=course,
        granularity=granularity,
        from_at=from_at,
        to_at=to_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="knowledge.user_snapshot.rebuild",
        resource_type="user_knowledge_snapshot",
        resource_id=snapshot.id,
        school_id=snapshot.school_id,
        class_id=snapshot.class_id,
        event_result="success",
        request=request,
        snapshot={
            "after": {
                "user_id": current_user.id,
                "class_id": class_id,
                "course_id": course_id,
                "granularity": granularity,
                "period_start": from_at.isoformat() if from_at is not None else None,
                "period_end": to_at.isoformat() if to_at is not None else None,
                "rule_version": snapshot.rule_version,
                "knowledge_stat_rules": [item.rule_code for item in aggregate.knowledge_stats],
            }
        },
    )
    db.commit()
    db.refresh(snapshot)
    return _user_snapshot_to_read(snapshot)


@router.get("/knowledge/me/snapshots", response_model=UserKnowledgeSnapshotPage)
def list_my_knowledge_snapshots(
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    granularity: KnowledgeSnapshotGranularity | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserKnowledgeSnapshotPage:
    _validate_period(from_at, to_at)
    class_group: ClassGroup | None = None
    if class_id is not None:
        class_group = require_class_member(db, current_user, class_id)
    if course_id is not None:
        require_course_scope(db, current_user, class_group, course_id)

    statement = select(UserKnowledgeSnapshot).where(UserKnowledgeSnapshot.user_id == current_user.id)
    if class_id is not None:
        statement = statement.where(UserKnowledgeSnapshot.class_id == class_id)
    if course_id is not None:
        statement = statement.where(UserKnowledgeSnapshot.course_id == course_id)
    if granularity is not None:
        statement = statement.where(UserKnowledgeSnapshot.granularity == granularity)
    if from_at is not None:
        statement = statement.where(UserKnowledgeSnapshot.period_start >= from_at)
    if to_at is not None:
        statement = statement.where(UserKnowledgeSnapshot.period_end <= to_at)
    if current_user.role == "student":
        statement = statement.outerjoin(Course, Course.id == UserKnowledgeSnapshot.course_id).where(
            or_(UserKnowledgeSnapshot.course_id.is_(None), Course.status == "published")
        )
    statement = statement.order_by(UserKnowledgeSnapshot.period_end.desc(), UserKnowledgeSnapshot.id.desc())
    total = _statement_count(db, statement)
    snapshots = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return UserKnowledgeSnapshotPage(
        items=[_user_snapshot_to_read(snapshot) for snapshot in snapshots],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(snapshots)),
    )


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
    class_group = get_class(db, class_id)
    require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        require_course_scope(db, current_user, class_group, course_id)
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
    class_group = get_class(db, class_id)
    require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        require_course_scope(db, current_user, class_group, course_id)

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
    class_group = get_class(db, class_id)
    require_class_teacher_or_admin(db, current_user, class_group)
    if course_id is not None:
        require_course_scope(db, current_user, class_group, course_id)

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
    *,
    student_visible_resources: bool = False,
) -> UserKnowledgeRead:
    assignment_count = _active_assignment_count(
        db,
        assignment_class_ids,
        course_id,
        student_visible_resources=student_visible_resources,
    )
    submitted_assignments = _submission_count(
        db,
        user_id,
        class_id,
        course_id,
        from_at,
        to_at,
        graded=False,
        student_visible_resources=student_visible_resources,
    )
    graded_assignments = _submission_count(
        db,
        user_id,
        class_id,
        course_id,
        from_at,
        to_at,
        graded=True,
        student_visible_resources=student_visible_resources,
    )
    score_total, max_score_total = _score_totals(
        db,
        user_id,
        class_id,
        course_id,
        from_at,
        to_at,
        student_visible_resources=student_visible_resources,
    )
    event_counts = _event_counts(
        db,
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
        student_visible_resources=student_visible_resources,
    )
    total_points = _point_total(
        db,
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
        student_visible_resources=student_visible_resources,
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
    stats.extend(
        _dimension_knowledge_stats(
            db,
            user_id=user_id,
            class_ids=assignment_class_ids,
            class_id=class_id,
            course_id=course_id,
            from_at=from_at,
            to_at=to_at,
            learner_count=1,
        )
    )
    return UserKnowledgeRead(
        rule_version=KNOWLEDGE_RULE_VERSION,
        statistics_policy=_statistics_policy(KNOWLEDGE_RULE_VERSION),
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


def _upsert_user_knowledge_snapshot(
    db: Session,
    *,
    aggregate: UserKnowledgeRead,
    current_user: User,
    class_group: ClassGroup | None,
    course: Course | None,
    granularity: KnowledgeSnapshotGranularity,
    from_at: datetime,
    to_at: datetime,
) -> UserKnowledgeSnapshot:
    class_scope_id = aggregate.class_id or 0
    course_scope_id = aggregate.course_id or 0
    snapshot = db.scalar(
        select(UserKnowledgeSnapshot).where(
            UserKnowledgeSnapshot.user_id == current_user.id,
            UserKnowledgeSnapshot.class_scope_id == class_scope_id,
            UserKnowledgeSnapshot.course_scope_id == course_scope_id,
            UserKnowledgeSnapshot.granularity == granularity,
            UserKnowledgeSnapshot.period_start == from_at,
            UserKnowledgeSnapshot.period_end == to_at,
            UserKnowledgeSnapshot.rule_version == KNOWLEDGE_RULE_VERSION,
        )
    )
    if snapshot is None:
        snapshot = UserKnowledgeSnapshot(
            user_id=current_user.id,
            school_id=_snapshot_school_id(class_group, course),
            class_id=aggregate.class_id,
            class_scope_id=class_scope_id,
            course_id=aggregate.course_id,
            course_scope_id=course_scope_id,
            granularity=granularity,
            period_start=from_at,
            period_end=to_at,
            rule_version=KNOWLEDGE_RULE_VERSION,
            created_by_user_id=current_user.id,
        )
        db.add(snapshot)
    else:
        snapshot.created_by_user_id = current_user.id
        snapshot.school_id = _snapshot_school_id(class_group, course)
    _apply_user_knowledge_snapshot(snapshot, aggregate)
    db.flush()
    return snapshot


def _apply_user_knowledge_snapshot(snapshot: UserKnowledgeSnapshot, aggregate: UserKnowledgeRead) -> None:
    snapshot.assignment_count = aggregate.assignment_count
    snapshot.submitted_assignments = aggregate.submitted_assignments
    snapshot.graded_assignments = aggregate.graded_assignments
    snapshot.total_events = aggregate.total_events
    snapshot.visit_events = aggregate.visit_events
    snapshot.start_events = aggregate.start_events
    snapshot.submit_events = aggregate.submit_events
    snapshot.complete_events = aggregate.complete_events
    snapshot.score_total = aggregate.score_total
    snapshot.max_score_total = aggregate.max_score_total
    snapshot.accuracy_percent = aggregate.accuracy_percent
    snapshot.completion_percent = aggregate.completion_percent
    snapshot.total_points = aggregate.total_points
    snapshot.knowledge_stats_json = [stat.model_dump() for stat in aggregate.knowledge_stats]
    snapshot.calculated_at = utc_now()


def _user_snapshot_to_read(snapshot: UserKnowledgeSnapshot) -> UserKnowledgeSnapshotRead:
    return UserKnowledgeSnapshotRead(
        id=snapshot.id,
        user_id=snapshot.user_id,
        school_id=snapshot.school_id,
        class_id=snapshot.class_id,
        course_id=snapshot.course_id,
        granularity=snapshot.granularity,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        rule_version=snapshot.rule_version,
        statistics_policy=_statistics_policy(snapshot.rule_version),
        created_by_user_id=snapshot.created_by_user_id,
        calculated_at=snapshot.calculated_at,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
        assignment_count=snapshot.assignment_count,
        submitted_assignments=snapshot.submitted_assignments,
        graded_assignments=snapshot.graded_assignments,
        total_events=snapshot.total_events,
        visit_events=snapshot.visit_events,
        start_events=snapshot.start_events,
        submit_events=snapshot.submit_events,
        complete_events=snapshot.complete_events,
        score_total=snapshot.score_total,
        max_score_total=snapshot.max_score_total,
        accuracy_percent=snapshot.accuracy_percent,
        completion_percent=snapshot.completion_percent,
        total_points=snapshot.total_points,
        knowledge_stats=snapshot.knowledge_stats_json,
    )


def _build_class_knowledge(
    db: Session,
    class_group: ClassGroup,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> ClassKnowledgeRead:
    student_ids = active_class_student_ids(db, class_group.id)
    students_total = len(student_ids)
    assignment_count = _active_assignment_count(
        db,
        [class_group.id],
        course_id,
        student_visible_resources=True,
    )
    submitted_assignments = _class_submission_count(
        db,
        class_group.id,
        course_id,
        from_at,
        to_at,
        graded=False,
        visible_resources=True,
    )
    graded_assignments = _class_submission_count(
        db,
        class_group.id,
        course_id,
        from_at,
        to_at,
        graded=True,
        visible_resources=True,
    )
    score_total, max_score_total = _class_score_totals(
        db,
        class_group.id,
        course_id,
        from_at,
        to_at,
        visible_resources=True,
    )
    event_counts = _event_counts(
        db,
        user_id=None,
        class_id=class_group.id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
        student_visible_resources=True,
    )
    total_points = _point_total(
        db,
        user_id=None,
        class_id=class_group.id,
        course_id=course_id,
        from_at=from_at,
        to_at=to_at,
        student_visible_resources=True,
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
    stats.extend(
        _dimension_knowledge_stats(
            db,
            user_id=None,
            class_ids=[class_group.id],
            class_id=class_group.id,
            course_id=course_id,
            from_at=from_at,
            to_at=to_at,
            learner_count=students_total,
        )
    )
    return ClassKnowledgeRead(
        rule_version=KNOWLEDGE_RULE_VERSION,
        statistics_policy=_statistics_policy(KNOWLEDGE_RULE_VERSION),
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
            ClassKnowledgeSnapshot.rule_version == KNOWLEDGE_RULE_VERSION,
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
            rule_version=KNOWLEDGE_RULE_VERSION,
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
        statistics_policy=_statistics_policy(snapshot.rule_version),
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


def _snapshot_school_id(class_group: ClassGroup | None, course: Course | None) -> int | None:
    if class_group is not None:
        return class_group.school_id
    if course is not None:
        return course.school_id
    return None


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


def _dimension_knowledge_stats(
    db: Session,
    *,
    user_id: int | None,
    class_ids: list[int] | None,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    learner_count: int,
) -> list[KnowledgeStatRead]:
    if not class_ids:
        return []
    assignment_statement = (
        select(Assignment, CourseUnit, Course, CourseClass, AssignmentClassPolicy)
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .join(CourseClass, CourseClass.course_id == Course.id)
        .outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == Assignment.id,
                AssignmentClassPolicy.class_id == CourseClass.class_id,
            ),
        )
        .where(
            CourseClass.class_id.in_(class_ids),
            CourseClass.status == "active",
            Course.status == "published",
            CourseUnit.status == "published",
            assignment_class_is_assigned_expression(),
            assignment_class_effective_status_expression() == "active",
        )
        .order_by(CourseClass.class_id, Course.id, CourseUnit.position, Assignment.id)
    )
    if course_id is not None:
        assignment_statement = assignment_statement.where(Course.id == course_id)
    assignment_rows = db.execute(assignment_statement).all()
    if not assignment_rows:
        return []

    assignment_ids = {assignment.id for assignment, _, _, _, _ in assignment_rows}
    scope_keys = {
        (assignment.id, course_class.class_id)
        for assignment, _, _, course_class, _ in assignment_rows
    }
    submissions_statement = select(Submission).where(
        Submission.assignment_id.in_(assignment_ids),
        Submission.class_id.in_(class_ids),
    )
    if user_id is not None:
        submissions_statement = submissions_statement.where(Submission.student_id == user_id)
    if from_at is not None:
        submissions_statement = submissions_statement.where(Submission.submitted_at >= from_at)
    if to_at is not None:
        submissions_statement = submissions_statement.where(Submission.submitted_at <= to_at)
    submissions = [
        submission
        for submission in db.scalars(submissions_statement).all()
        if (submission.assignment_id, submission.class_id) in scope_keys
    ]

    graded_submissions_statement = select(Submission).where(
        Submission.assignment_id.in_(assignment_ids),
        Submission.class_id.in_(class_ids),
        Submission.score.is_not(None),
        Submission.graded_at.is_not(None),
    )
    if user_id is not None:
        graded_submissions_statement = graded_submissions_statement.where(Submission.student_id == user_id)
    if from_at is not None:
        graded_submissions_statement = graded_submissions_statement.where(Submission.graded_at >= from_at)
    if to_at is not None:
        graded_submissions_statement = graded_submissions_statement.where(Submission.graded_at <= to_at)
    graded_submissions = [
        submission
        for submission in db.scalars(graded_submissions_statement).all()
        if (submission.assignment_id, submission.class_id) in scope_keys
    ]

    events_statement = select(LearningEvent).where(LearningEvent.class_id.in_(class_ids))
    if user_id is not None:
        events_statement = events_statement.where(LearningEvent.user_id == user_id)
    if course_id is not None:
        events_statement = events_statement.where(LearningEvent.course_id == course_id)
    if from_at is not None:
        events_statement = events_statement.where(LearningEvent.occurred_at >= from_at)
    if to_at is not None:
        events_statement = events_statement.where(LearningEvent.occurred_at <= to_at)
    valid_unit_ids = {unit.id for _, unit, _, _, _ in assignment_rows}
    valid_course_ids = {course.id for _, _, course, _, _ in assignment_rows}
    events = []
    for event in db.scalars(events_statement).all():
        if event.assignment_id is not None:
            if (event.assignment_id, event.class_id) not in scope_keys:
                continue
        elif event.unit_id is not None:
            if event.unit_id not in valid_unit_ids:
                continue
        elif event.course_id not in valid_course_ids:
            continue
        events.append(event)

    points_statement = select(PointLedger).where(
        PointLedger.assignment_id.in_(assignment_ids),
        PointLedger.class_id.in_(class_ids),
    )
    if user_id is not None:
        points_statement = points_statement.where(PointLedger.user_id == user_id)
    if from_at is not None:
        points_statement = points_statement.where(PointLedger.created_at >= from_at)
    if to_at is not None:
        points_statement = points_statement.where(PointLedger.created_at <= to_at)
    points = [
        point
        for point in db.scalars(points_statement).all()
        if (point.assignment_id, point.class_id) in scope_keys
    ]

    submission_map: dict[tuple[int, int], list[Submission]] = {}
    for submission in submissions:
        submission_map.setdefault((submission.assignment_id, submission.class_id), []).append(submission)
    graded_submission_map: dict[tuple[int, int], list[Submission]] = {}
    for submission in graded_submissions:
        graded_submission_map.setdefault((submission.assignment_id, submission.class_id), []).append(submission)
    event_map: dict[tuple[int, int], list[LearningEvent]] = {}
    for event in events:
        if event.assignment_id is not None:
            event_map.setdefault((event.assignment_id, event.class_id), []).append(event)
    point_map: dict[tuple[int, int], int] = {}
    for point in points:
        key = (point.assignment_id, point.class_id)
        point_map[key] = point_map.get(key, 0) + point.delta

    stats: list[KnowledgeStatRead] = []
    unit_buckets: dict[tuple[int, int, int], dict] = {}
    course_buckets: dict[tuple[int, int], dict] = {}
    for assignment, unit, course, course_class, _ in assignment_rows:
        key = (assignment.id, course_class.class_id)
        scoped_submissions = submission_map.get(key, [])
        scoped_events = event_map.get(key, [])
        submitted_count = len(scoped_submissions)
        scoped_graded_submissions = graded_submission_map.get(key, [])
        score_total = sum(item.score or 0 for item in scoped_graded_submissions)
        max_score_total = len(scoped_graded_submissions) * assignment.max_score
        expected_count = learner_count if user_id is None else 1
        event_counts = _event_type_counts(scoped_events)
        evidence = {
            "course_id": course.id,
            "unit_id": unit.id,
            "assignment_id": assignment.id,
            "class_id": course_class.class_id,
            "effective_status": "active",
            "submitted_count": submitted_count,
            "graded_count": len(scoped_graded_submissions),
            "score_total": score_total,
            "max_score_total": max_score_total,
            "points": point_map.get(key, 0),
            "events": event_counts,
        }
        stats.append(
            KnowledgeStatRead(
                rule_code=f"assignment_completion:{course_class.class_id}:{assignment.id}",
                dimension="assignment",
                user_id=user_id,
                class_id=course_class.class_id,
                course_id=course.id,
                unit_id=unit.id,
                assignment_id=assignment.id,
                label=assignment.title,
                frequency=submitted_count,
                sample_size=expected_count,
                percent=_percent(submitted_count, expected_count),
                evidence=evidence,
            )
        )
        _merge_dimension_bucket(
            unit_buckets,
            (course_class.class_id, course.id, unit.id),
            assignment.id,
            expected_count,
            evidence,
            label=unit.title,
        )
        _merge_dimension_bucket(
            course_buckets,
            (course_class.class_id, course.id),
            assignment.id,
            expected_count,
            evidence,
            label=course.title,
        )

    for (bucket_class_id, bucket_course_id, unit_id), bucket in sorted(unit_buckets.items()):
        stats.append(
            _bucket_stat(
                rule_code=f"unit_completion:{bucket_class_id}:{unit_id}",
                dimension="unit",
                bucket=bucket,
                user_id=user_id,
                class_id=bucket_class_id,
                course_id=bucket_course_id,
                unit_id=unit_id,
            )
        )
    for (bucket_class_id, bucket_course_id), bucket in sorted(course_buckets.items()):
        stats.append(
            _bucket_stat(
                rule_code=f"course_completion:{bucket_class_id}:{bucket_course_id}",
                dimension="course",
                bucket=bucket,
                user_id=user_id,
                class_id=bucket_class_id,
                course_id=bucket_course_id,
            )
        )

    knowledge_buckets: dict[str, list[LearningEvent]] = {}
    for event in events:
        if event.knowledge_code:
            knowledge_buckets.setdefault(event.knowledge_code, []).append(event)
    for knowledge_code, knowledge_events in sorted(knowledge_buckets.items()):
        event_counts = _event_type_counts(knowledge_events)
        stats.append(
            KnowledgeStatRead(
                rule_code=f"knowledge_completion:{knowledge_code}",
                dimension="knowledge_point",
                user_id=user_id,
                class_id=class_id,
                course_id=course_id,
                knowledge_code=knowledge_code,
                label=knowledge_code,
                frequency=event_counts["complete"],
                sample_size=event_counts["total"],
                percent=_percent(event_counts["complete"], event_counts["total"]),
                evidence={"events": event_counts},
            )
        )
    return stats


def _event_type_counts(events: list[LearningEvent]) -> dict[str, int]:
    counts = {"visit": 0, "start": 0, "submit": 0, "complete": 0}
    for event in events:
        if event.event_type in counts:
            counts[event.event_type] += 1
    counts["total"] = sum(counts.values())
    return counts


def _merge_dimension_bucket(
    buckets: dict,
    key: tuple,
    assignment_id: int,
    expected_count: int,
    evidence: dict,
    *,
    label: str,
) -> None:
    bucket = buckets.setdefault(
        key,
        {
            "label": label,
            "assignment_ids": [],
            "submitted_count": 0,
            "expected_count": 0,
            "graded_count": 0,
            "score_total": 0,
            "max_score_total": 0,
            "points": 0,
            "events": {"visit": 0, "start": 0, "submit": 0, "complete": 0, "total": 0},
        },
    )
    bucket["assignment_ids"].append(assignment_id)
    bucket["submitted_count"] += evidence["submitted_count"]
    bucket["expected_count"] += expected_count
    bucket["graded_count"] += evidence["graded_count"]
    bucket["score_total"] += evidence["score_total"]
    bucket["max_score_total"] += evidence["max_score_total"]
    bucket["points"] += evidence["points"]
    for event_type, count in evidence["events"].items():
        bucket["events"][event_type] += count


def _bucket_stat(
    *,
    rule_code: str,
    dimension: str,
    bucket: dict,
    user_id: int | None,
    class_id: int,
    course_id: int,
    unit_id: int | None = None,
) -> KnowledgeStatRead:
    return KnowledgeStatRead(
        rule_code=rule_code,
        dimension=dimension,
        user_id=user_id,
        class_id=class_id,
        course_id=course_id,
        unit_id=unit_id,
        label=bucket["label"],
        frequency=bucket["submitted_count"],
        sample_size=bucket["expected_count"],
        percent=_percent(bucket["submitted_count"], bucket["expected_count"]),
        evidence={
            "assignment_ids": sorted(bucket["assignment_ids"]),
            "submitted_count": bucket["submitted_count"],
            "expected_count": bucket["expected_count"],
            "graded_count": bucket["graded_count"],
            "score_total": bucket["score_total"],
            "max_score_total": bucket["max_score_total"],
            "points": bucket["points"],
            "events": bucket["events"],
        },
    )


def _active_assignment_count(
    db: Session,
    class_ids: list[int] | None,
    course_id: int | None,
    *,
    student_visible_resources: bool = False,
) -> int:
    if class_ids is not None:
        if not class_ids:
            return 0
        rows = (
            select(Assignment.id.label("assignment_id"), CourseClass.class_id.label("class_id"))
            .select_from(Assignment)
            .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
            .join(Course, Course.id == CourseUnit.course_id)
            .join(CourseClass, CourseClass.course_id == Course.id)
            .outerjoin(
                AssignmentClassPolicy,
                and_(
                    AssignmentClassPolicy.assignment_id == Assignment.id,
                    AssignmentClassPolicy.class_id == CourseClass.class_id,
                ),
            )
            .where(
                CourseClass.class_id.in_(class_ids),
                CourseClass.status == "active",
                assignment_class_is_assigned_expression(),
                assignment_class_effective_status_expression() == "active",
            )
        )
        if course_id is not None:
            rows = rows.where(Course.id == course_id)
        if student_visible_resources:
            rows = rows.where(Course.status == "published", CourseUnit.status == "published")
        scoped_rows = rows.group_by(Assignment.id, CourseClass.class_id).subquery()
        return int(db.scalar(select(func.count()).select_from(scoped_rows)) or 0)

    statement = (
        select(func.count(func.distinct(Assignment.id)))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .where(Assignment.status == "active")
    )
    if course_id is not None:
        statement = statement.where(CourseUnit.course_id == course_id)
    if student_visible_resources:
        statement = statement.join(Course, Course.id == CourseUnit.course_id).where(
            Course.status == "published",
            CourseUnit.status == "published",
        )
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
    student_visible_resources: bool = False,
) -> int:
    statement = select(func.count(func.distinct(Submission.id))).select_from(Submission)
    statement = statement.where(Submission.student_id == user_id)
    statement = _apply_submission_filters(
        statement,
        class_id,
        course_id,
        from_at,
        to_at,
        graded,
        student_visible_resources=student_visible_resources,
    )
    return int(db.scalar(statement) or 0)


def _class_submission_count(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    graded: bool,
    visible_resources: bool = False,
) -> int:
    statement = select(func.count(func.distinct(Submission.id))).select_from(Submission)
    statement = _apply_submission_filters(
        statement,
        class_id,
        course_id,
        from_at,
        to_at,
        graded,
        student_visible_resources=visible_resources,
    )
    return int(db.scalar(statement) or 0)


def _score_totals(
    db: Session,
    user_id: int,
    class_id: int | None,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    student_visible_resources: bool = False,
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
        student_visible_resources=student_visible_resources,
    )
    score_total, max_score_total = db.execute(statement).one()
    return int(score_total or 0), int(max_score_total or 0)


def _class_score_totals(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
    *,
    visible_resources: bool = False,
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
        student_visible_resources=visible_resources,
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
    student_visible_resources: bool = False,
):
    if class_id is not None:
        statement = statement.where(Submission.class_id == class_id)
    if course_id is not None or student_visible_resources:
        if not assignment_joined:
            statement = statement.join(Assignment, Assignment.id == Submission.assignment_id)
        statement = statement.join(CourseUnit, CourseUnit.id == Assignment.unit_id)
    if course_id is not None:
        statement = statement.where(CourseUnit.course_id == course_id)
    if student_visible_resources:
        statement = statement.join(Course, Course.id == CourseUnit.course_id).outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == Assignment.id,
                AssignmentClassPolicy.class_id == Submission.class_id,
            ),
        )
        statement = statement.where(
            Course.status == "published",
            CourseUnit.status == "published",
            assignment_class_is_assigned_expression(),
            assignment_class_effective_status_expression() == "active",
        )
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
    student_visible_resources: bool = False,
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
    if student_visible_resources:
        effective_assignment_status = assignment_class_effective_status_expression()
        statement = (
            statement.outerjoin(Course, Course.id == LearningEvent.course_id)
            .outerjoin(CourseUnit, CourseUnit.id == LearningEvent.unit_id)
            .outerjoin(Assignment, Assignment.id == LearningEvent.assignment_id)
            .outerjoin(
                AssignmentClassPolicy,
                and_(
                    AssignmentClassPolicy.assignment_id == LearningEvent.assignment_id,
                    AssignmentClassPolicy.class_id == LearningEvent.class_id,
                ),
            )
            .where(
                or_(LearningEvent.course_id.is_(None), Course.status == "published"),
                or_(LearningEvent.unit_id.is_(None), CourseUnit.status == "published"),
                or_(
                    LearningEvent.assignment_id.is_(None),
                    and_(
                        assignment_class_is_assigned_expression(),
                        effective_assignment_status == "active",
                    ),
                ),
            )
        )
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
    student_visible_resources: bool = False,
) -> int:
    statement = select(func.coalesce(func.sum(PointLedger.delta), 0)).select_from(PointLedger)
    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    if class_id is not None:
        statement = statement.where(PointLedger.class_id == class_id)
    if course_id is not None or student_visible_resources:
        statement = statement.outerjoin(Assignment, Assignment.id == PointLedger.assignment_id).outerjoin(
            CourseUnit,
            CourseUnit.id == Assignment.unit_id,
        )
    if course_id is not None:
        statement = statement.where(CourseUnit.course_id == course_id)
    if student_visible_resources:
        statement = statement.outerjoin(Course, Course.id == CourseUnit.course_id).outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == PointLedger.assignment_id,
                AssignmentClassPolicy.class_id == PointLedger.class_id,
            ),
        ).where(
            or_(
                PointLedger.assignment_id.is_(None),
                and_(
                    Course.status == "published",
                    CourseUnit.status == "published",
                    assignment_class_is_assigned_expression(),
                    assignment_class_effective_status_expression() == "active",
                ),
            )
        )
    if from_at is not None:
        statement = statement.where(PointLedger.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(PointLedger.created_at <= to_at)
    return int(db.scalar(statement) or 0)


def _class_active_user_ids(
    db: Session,
    class_id: int,
    course_id: int | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> set[int]:
    event_statement = (
        select(func.distinct(LearningEvent.user_id))
        .outerjoin(Course, Course.id == LearningEvent.course_id)
        .outerjoin(CourseUnit, CourseUnit.id == LearningEvent.unit_id)
        .outerjoin(Assignment, Assignment.id == LearningEvent.assignment_id)
        .outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == LearningEvent.assignment_id,
                AssignmentClassPolicy.class_id == LearningEvent.class_id,
            ),
        )
        .where(
            LearningEvent.class_id == class_id,
            or_(LearningEvent.course_id.is_(None), Course.status == "published"),
            or_(LearningEvent.unit_id.is_(None), CourseUnit.status == "published"),
            or_(
                LearningEvent.assignment_id.is_(None),
                and_(
                    assignment_class_is_assigned_expression(),
                    assignment_class_effective_status_expression() == "active",
                ),
            ),
        )
    )
    if course_id is not None:
        event_statement = event_statement.where(LearningEvent.course_id == course_id)
    if from_at is not None:
        event_statement = event_statement.where(LearningEvent.occurred_at >= from_at)
    if to_at is not None:
        event_statement = event_statement.where(LearningEvent.occurred_at <= to_at)

    submission_statement = (
        select(func.distinct(Submission.student_id))
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == Assignment.id,
                AssignmentClassPolicy.class_id == Submission.class_id,
            ),
        )
        .where(
            Submission.class_id == class_id,
            Course.status == "published",
            CourseUnit.status == "published",
            assignment_class_is_assigned_expression(),
            assignment_class_effective_status_expression() == "active",
        )
    )
    if course_id is not None:
        submission_statement = submission_statement.where(CourseUnit.course_id == course_id)
    if from_at is not None:
        submission_statement = submission_statement.where(Submission.submitted_at >= from_at)
    if to_at is not None:
        submission_statement = submission_statement.where(Submission.submitted_at <= to_at)

    return set(db.scalars(event_statement).all()).union(db.scalars(submission_statement).all())


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


def _statistics_policy(rule_version: str) -> dict:
    if rule_version == "v1":
        return {
            "assignment_denominator": "base active assignments",
            "resource_visibility": "legacy base status filters",
            "knowledge_point_source": "not_available",
        }
    return {
        "assignment_denominator": "effective active assignment-class pairs",
        "resource_visibility": "published course + published unit + assigned class policy + effective active status",
        "submission_window": "submitted_at for submitted counts; graded_at for graded and score counts",
        "event_window": "occurred_at",
        "point_window": "point ledger created_at",
        "knowledge_point_source": "normalized learning_event.knowledge_code",
        "snapshot_compatibility": "v1 snapshots remain readable; new rebuilds write v2",
    }
