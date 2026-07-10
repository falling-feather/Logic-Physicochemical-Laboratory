from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    AssignmentClassPolicy,
    ClassGroup,
    ClassMembership,
    Course,
    CourseClass,
    CourseUnit,
    LearningEvent,
    PointLedger,
    Submission,
    User,
)
from app.models.base import utc_now
from app.schemas.course import (
    AssignmentRead,
    AssignmentReviewRead,
    CourseRead,
    CourseUnitRead,
    StudentAssignmentCenterItem,
    StudentAssignmentCenterPage,
    StudentAssignmentFilter,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionRead,
)
from app.schemas.school import ClassRead
from app.services.audit import record_audit_log
from app.services.assignment_policies import (
    build_effective_assignment_policy,
    effective_assignment_payload,
    resolve_assignment_class_policy,
)
from app.services.access_control import (
    course_attached_to_class,
    get_class,
    require_class_teacher_or_admin,
    require_course_scope,
    require_course_visible,
    require_school_role,
    require_student_unit_published,
    teacher_class_ids,
)
from app.services.points import (
    assignment_grade_point_total,
    points_for_assignment_score,
)


router = APIRouter()


@router.get("/assignments/me", response_model=StudentAssignmentCenterPage)
def list_my_assignments(
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    filter_by: StudentAssignmentFilter = Query(default="all", alias="filter"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudentAssignmentCenterPage:
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can view their assignment center")

    class_group: ClassGroup | None = None
    if class_id is not None:
        class_group = _require_active_user_class(db, current_user.id, class_id)
    if course_id is not None:
        if class_group is not None:
            require_course_scope(db, current_user, class_group, course_id)
        else:
            require_course_visible(db, current_user, course_id)

    active_class_ids = select(ClassMembership.class_id).where(
        ClassMembership.user_id == current_user.id,
        ClassMembership.role == "student",
        ClassMembership.status == "active",
    )
    statement = (
        select(ClassGroup, Course, CourseUnit, Assignment, Submission, AssignmentClassPolicy)
        .select_from(ClassGroup)
        .join(CourseClass, CourseClass.class_id == ClassGroup.id)
        .join(Course, Course.id == CourseClass.course_id)
        .join(CourseUnit, CourseUnit.course_id == Course.id)
        .join(Assignment, Assignment.unit_id == CourseUnit.id)
        .outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == Assignment.id,
                AssignmentClassPolicy.class_id == ClassGroup.id,
            ),
        )
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == current_user.id,
                Submission.class_id == ClassGroup.id,
            ),
        )
        .where(
            ClassGroup.id.in_(active_class_ids),
            CourseClass.status == "active",
            Course.status == "published",
            CourseUnit.status == "published",
            or_(
                and_(
                    Assignment.audience_mode == "selected_classes",
                    AssignmentClassPolicy.id.is_not(None),
                    AssignmentClassPolicy.assigned.is_(True),
                ),
                and_(
                    Assignment.audience_mode == "all_attached_classes",
                    or_(
                        AssignmentClassPolicy.id.is_(None),
                        AssignmentClassPolicy.assigned.is_(True),
                    ),
                ),
            ),
        )
    )
    effective_status = func.coalesce(AssignmentClassPolicy.status_override, Assignment.status)
    if class_id is not None:
        statement = statement.where(ClassGroup.id == class_id)
    if course_id is not None:
        statement = statement.where(Course.id == course_id)
    if filter_by == "active":
        statement = statement.where(effective_status == "active")
    elif filter_by == "feedback":
        statement = statement.where(Submission.status.in_(["graded", "returned"]))
    elif filter_by == "history":
        statement = statement.where(effective_status.in_(["closed", "archived"]))

    statement = statement.order_by(ClassGroup.id, Course.id, CourseUnit.position, Assignment.id)
    total = int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    rows = db.execute(statement.offset(offset).limit(limit)).all()
    items: list[StudentAssignmentCenterItem] = []
    for row_class, course, unit, assignment, submission, policy in rows:
        effective = build_effective_assignment_policy(assignment, row_class.id, policy)
        submit_block_reason = _assignment_submit_block_reason(effective.status, submission)
        items.append(
            StudentAssignmentCenterItem(
                class_=ClassRead.model_validate(row_class),
                course=CourseRead.model_validate(course),
                unit=CourseUnitRead.model_validate(unit),
                assignment=AssignmentRead.model_validate(effective_assignment_payload(assignment, effective)),
                submission=SubmissionRead.model_validate(submission) if submission is not None else None,
                can_submit=submit_block_reason is None,
                read_only=submit_block_reason is not None,
                submit_block_reason=submit_block_reason,
            )
        )
    next_offset = offset + len(items)
    return StudentAssignmentCenterPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset if next_offset < total else None,
    )


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    assignment_id: int,
    payload: SubmissionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can submit assignments")
    assignment, unit, course = _resolve_assignment(db, assignment_id)
    require_course_visible(db, current_user, course.id)
    require_student_unit_published(current_user, unit)
    class_group = _require_active_user_class(db, current_user.id, payload.class_id)
    if class_group.school_id != course.school_id:
        raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
    if not course_attached_to_class(db, course.id, class_group.id):
        raise HTTPException(status_code=403, detail="Course is not attached to this class")
    effective = resolve_assignment_class_policy(db, assignment, class_group.id)
    if not effective.assigned:
        raise HTTPException(status_code=403, detail="Assignment is not assigned to this class")
    if effective.status != "active":
        raise HTTPException(status_code=409, detail="Assignment is not active")

    existing = db.scalar(
        select(Submission).where(
            Submission.assignment_id == assignment.id,
            Submission.student_id == current_user.id,
            Submission.class_id == class_group.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Assignment already submitted")

    now = utc_now()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=current_user.id,
        class_id=class_group.id,
        content=payload.content,
        status="submitted",
        submitted_at=now,
    )
    try:
        db.add(submission)
        db.flush()
        db.add(
            LearningEvent(
                user_id=current_user.id,
                school_id=course.school_id,
                class_id=class_group.id,
                course_id=course.id,
                unit_id=unit.id,
                assignment_id=assignment.id,
                event_type="submit",
                payload={"submission_id": submission.id},
                occurred_at=now,
            )
        )
        record_audit_log(
            db,
            actor=current_user,
            action="submission.create",
            resource_type="submission",
            resource_id=submission.id,
            school_id=course.school_id,
            class_id=class_group.id,
            event_result="success",
            request=request,
            snapshot={
                "after": {
                    "assignment_id": assignment.id,
                    "student_id": current_user.id,
                    "class_id": class_group.id,
                    "course_id": course.id,
                    "unit_id": unit.id,
                    "status": submission.status,
                    "assignment_policy_source": effective.policy_source,
                    "content_keys": sorted(payload.content.keys()),
                }
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        conflict = db.scalar(
            select(Submission.id).where(
                Submission.assignment_id == assignment.id,
                Submission.student_id == current_user.id,
                Submission.class_id == class_group.id,
            )
        )
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Assignment already submitted") from exc
        raise
    db.refresh(submission)
    return submission


@router.get("/assignments/{assignment_id}/review", response_model=AssignmentReviewRead)
def read_assignment_review(
    assignment_id: int,
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssignmentReviewRead:
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can review their assignment history")
    assignment, unit, course = _resolve_assignment(db, assignment_id)
    require_course_visible(db, current_user, course.id)
    require_student_unit_published(current_user, unit)
    statement = (
        select(Submission)
        .where(
            Submission.assignment_id == assignment.id,
            Submission.student_id == current_user.id,
        )
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
    )
    if class_id is not None:
        class_group = _require_active_user_class(db, current_user.id, class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
        if not course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        effective = resolve_assignment_class_policy(db, assignment, class_group.id)
        if not effective.assigned:
            raise HTTPException(status_code=403, detail="Assignment is not assigned to this class")
        statement = statement.where(Submission.class_id == class_group.id)
    else:
        eligible_class_ids = _active_user_course_class_ids(db, current_user.id, course.id)
        eligible_class_ids = [
            eligible_class_id
            for eligible_class_id in eligible_class_ids
            if resolve_assignment_class_policy(db, assignment, eligible_class_id).assigned
        ]
        if len(eligible_class_ids) > 1:
            raise HTTPException(
                status_code=422,
                detail="class_id is required when assignment is available in multiple classes",
            )
        if not eligible_class_ids:
            raise HTTPException(status_code=403, detail="Assignment is outside current student class scope")
        effective = resolve_assignment_class_policy(db, assignment, eligible_class_ids[0])
        statement = statement.where(Submission.class_id == effective.class_id)
    submission = db.scalars(statement.limit(1)).first()
    submit_block_reason = _assignment_submit_block_reason(effective.status, submission)
    can_submit = submit_block_reason is None
    return AssignmentReviewRead(
        course_id=course.id,
        unit_id=unit.id,
        assignment=AssignmentRead.model_validate(effective_assignment_payload(assignment, effective)),
        submission=SubmissionRead.model_validate(submission) if submission is not None else None,
        can_submit=can_submit,
        read_only=not can_submit,
        submit_block_reason=submit_block_reason,
    )


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionRead])
def list_assignment_submissions(
    assignment_id: int,
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Submission]:
    assignment, unit, course = _resolve_assignment(db, assignment_id)
    statement = select(Submission).where(Submission.assignment_id == assignment.id).order_by(Submission.id)

    if current_user.role == "student":
        require_course_visible(db, current_user, course.id)
        require_student_unit_published(current_user, unit)
        statement = statement.where(Submission.student_id == current_user.id)
        if class_id is not None:
            _require_active_user_class(db, current_user.id, class_id)
            if not course_attached_to_class(db, course.id, class_id):
                raise HTTPException(status_code=403, detail="Course is not attached to this class")
            if not resolve_assignment_class_policy(db, assignment, class_id).assigned:
                raise HTTPException(status_code=403, detail="Assignment is not assigned to this class")
            statement = statement.where(Submission.class_id == class_id)
        else:
            eligible_class_ids = [
                eligible_class_id
                for eligible_class_id in _active_user_course_class_ids(db, current_user.id, course.id)
                if resolve_assignment_class_policy(db, assignment, eligible_class_id).assigned
            ]
            if not eligible_class_ids:
                return []
            statement = statement.where(Submission.class_id.in_(eligible_class_ids))
        return list(db.scalars(statement).all())

    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    if class_id is not None:
        class_group = get_class(db, class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
        if not course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        require_class_teacher_or_admin(
            db,
            current_user,
            class_group,
            detail="Assignment submissions require class teacher scope",
        )
        statement = statement.where(Submission.class_id == class_id)
    elif current_user.role != "admin":
        class_ids = teacher_class_ids(db, current_user.id)
        if not class_ids:
            return []
        statement = statement.where(Submission.class_id.in_(class_ids))
    return list(db.scalars(statement).all())


@router.patch("/submissions/{submission_id}/grade", response_model=SubmissionRead)
def grade_submission(
    submission_id: int,
    payload: SubmissionGrade,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment, _, course = _resolve_assignment(db, submission.assignment_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    class_group = get_class(db, submission.class_id)
    require_class_teacher_or_admin(
        db,
        current_user,
        class_group,
        detail="Submission grading requires class teacher scope",
    )
    if payload.score > assignment.max_score:
        raise HTTPException(status_code=422, detail="Score cannot exceed assignment max_score")

    previous_snapshot = {
        "status": submission.status,
        "score": submission.score,
        "feedback": submission.feedback,
        "graded_by_user_id": submission.graded_by_user_id,
    }
    previous_score = submission.score or 0
    previous_points = assignment_grade_point_total(db, submission.id)
    effective = resolve_assignment_class_policy(db, assignment, class_group.id)
    point_rule = effective.point_rule
    submission.score = payload.score
    submission.feedback = (payload.feedback or "").strip() or None
    submission.status = payload.status
    submission.graded_by_user_id = current_user.id
    submission.graded_at = utc_now()

    score_delta = payload.score - previous_score
    next_points = points_for_assignment_score(payload.score, point_rule)
    point_delta = next_points - previous_points
    if point_delta:
        db.add(
            PointLedger(
                user_id=submission.student_id,
                school_id=course.school_id,
                class_id=submission.class_id,
                assignment_id=assignment.id,
                submission_id=submission.id,
                delta=point_delta,
                reason="assignment_grade",
                note=submission.feedback,
                created_by_user_id=current_user.id,
            )
        )
    next_snapshot = {
        "status": submission.status,
        "score": submission.score,
        "feedback": submission.feedback,
        "graded_by_user_id": submission.graded_by_user_id,
        "assignment_id": assignment.id,
        "student_id": submission.student_id,
        "score_delta": score_delta,
        "point_delta": point_delta,
        "point_rule": point_rule,
        "point_rule_source": effective.point_rule_source,
    }
    record_audit_log(
        db,
        actor=current_user,
        action="submission.grade",
        resource_type="submission",
        resource_id=submission.id,
        school_id=course.school_id,
        class_id=submission.class_id,
        event_result="success",
        request=request,
        snapshot={"before": previous_snapshot, "after": next_snapshot},
    )
    db.commit()
    db.refresh(submission)
    return submission


def _require_active_user_class(db: Session, user_id: int, class_id: int) -> ClassGroup:
    class_group = get_class(db, class_id)
    membership = db.scalar(
        select(ClassMembership.id).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user_id,
            ClassMembership.role == "student",
            ClassMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Class is outside current student scope")
    return class_group


def _active_user_course_class_ids(db: Session, user_id: int, course_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.class_id)
            .join(CourseClass, CourseClass.class_id == ClassMembership.class_id)
            .where(
                ClassMembership.user_id == user_id,
                ClassMembership.role == "student",
                ClassMembership.status == "active",
                CourseClass.course_id == course_id,
                CourseClass.status == "active",
            )
            .distinct()
            .order_by(ClassMembership.class_id)
        ).all()
    )


def _assignment_submit_block_reason(assignment_status: str, submission: Submission | None) -> str | None:
    if assignment_status == "closed":
        return "assignment_closed"
    if assignment_status == "archived":
        return "assignment_archived"
    if assignment_status != "active":
        return "assignment_not_active"
    if submission is not None:
        return "already_submitted"
    return None


def _resolve_assignment(db: Session, assignment_id: int) -> tuple[Assignment, CourseUnit, Course]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    unit = db.get(CourseUnit, assignment.unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Course unit not found")
    course = db.get(Course, unit.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return assignment, unit, course
