from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
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
from app.schemas.course import SubmissionCreate, SubmissionGrade, SubmissionRead
from app.services.audit import record_audit_log


router = APIRouter()


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    assignment_id: int,
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can submit assignments")
    assignment, unit, course = _resolve_assignment(db, assignment_id)
    if assignment.status != "active":
        raise HTTPException(status_code=409, detail="Assignment is not active")
    _require_course_visible(db, current_user, course.id)
    class_group = _require_class_member(db, current_user, payload.class_id)
    if class_group.school_id != course.school_id:
        raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
    if not _course_attached_to_class(db, course.id, class_group.id):
        raise HTTPException(status_code=403, detail="Course is not attached to this class")

    existing = db.scalar(
        select(Submission).where(
            Submission.assignment_id == assignment.id,
            Submission.student_id == current_user.id,
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
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionRead])
def list_assignment_submissions(
    assignment_id: int,
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Submission]:
    assignment, _, course = _resolve_assignment(db, assignment_id)
    statement = select(Submission).where(Submission.assignment_id == assignment.id).order_by(Submission.id)

    if current_user.role == "student":
        _require_course_visible(db, current_user, course.id)
        statement = statement.where(Submission.student_id == current_user.id)
        if class_id is not None:
            _require_class_member(db, current_user, class_id)
            statement = statement.where(Submission.class_id == class_id)
        return list(db.scalars(statement).all())

    _require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    if class_id is not None:
        class_group = _get_class(db, class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to assignment school")
        if not _course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        statement = statement.where(Submission.class_id == class_id)
    return list(db.scalars(statement).all())


@router.patch("/submissions/{submission_id}/grade", response_model=SubmissionRead)
def grade_submission(
    submission_id: int,
    payload: SubmissionGrade,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment, _, course = _resolve_assignment(db, submission.assignment_id)
    _require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
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
        snapshot={"before": previous_snapshot, "after": next_snapshot},
    )
    db.commit()
    db.refresh(submission)
    return submission


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


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _visible_class_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.class_id).where(
                ClassMembership.user_id == user_id,
                ClassMembership.status == "active",
            )
        ).all()
    )


def _require_course_visible(db: Session, user: User, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
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


def _require_school_role(db: Session, user: User, school_id: int, roles: set[str]) -> None:
    if user.role == "admin":
        return
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.role.in_(roles),
            SchoolMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="School role is outside current user scope")


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
