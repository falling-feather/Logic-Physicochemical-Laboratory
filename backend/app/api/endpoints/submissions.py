from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    Course,
    CourseUnit,
    LearningEvent,
    PointLedger,
    Submission,
    User,
)
from app.models.base import utc_now
from app.schemas.course import AssignmentRead, AssignmentReviewRead, SubmissionCreate, SubmissionGrade, SubmissionRead
from app.services.audit import record_audit_log
from app.services.access_control import (
    course_attached_to_class,
    get_class,
    require_class_member,
    require_class_teacher_or_admin,
    require_course_visible,
    require_school_role,
    require_student_unit_published,
    teacher_class_ids,
)


router = APIRouter()


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
    if assignment.status != "active":
        raise HTTPException(status_code=409, detail="Assignment is not active")
    require_course_visible(db, current_user, course.id)
    require_student_unit_published(current_user, unit)
    class_group = require_class_member(db, current_user, payload.class_id)
    if class_group.school_id != course.school_id:
        raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
    if not course_attached_to_class(db, course.id, class_group.id):
        raise HTTPException(status_code=403, detail="Course is not attached to this class")

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
                "content_keys": sorted(payload.content.keys()),
            }
        },
    )
    db.commit()
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
        class_group = require_class_member(db, current_user, class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
        if not course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        statement = statement.where(Submission.class_id == class_group.id)
    submission = db.scalars(statement.limit(1)).first()
    submit_block_reason = _assignment_submit_block_reason(assignment, submission)
    can_submit = submit_block_reason is None
    return AssignmentReviewRead(
        course_id=course.id,
        unit_id=unit.id,
        assignment=AssignmentRead.model_validate(assignment),
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
            require_class_member(db, current_user, class_id)
            statement = statement.where(Submission.class_id == class_id)
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
    submission.score = payload.score
    submission.feedback = (payload.feedback or "").strip() or None
    submission.status = payload.status
    submission.graded_by_user_id = current_user.id
    submission.graded_at = utc_now()

    delta = payload.score - previous_score
    if delta:
        db.add(
            PointLedger(
                user_id=submission.student_id,
                school_id=course.school_id,
                class_id=submission.class_id,
                assignment_id=assignment.id,
                submission_id=submission.id,
                delta=delta,
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
        "score_delta": delta,
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


def _assignment_submit_block_reason(assignment: Assignment, submission: Submission | None) -> str | None:
    if assignment.status == "closed":
        return "assignment_closed"
    if assignment.status == "archived":
        return "assignment_archived"
    if assignment.status != "active":
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
