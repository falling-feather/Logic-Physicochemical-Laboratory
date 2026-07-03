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
    SchoolMembership,
    User,
)
from app.models.base import utc_now
from app.schemas.course import LearningEventCreate, LearningEventRead


router = APIRouter()


@router.post("", response_model=LearningEventRead, status_code=status.HTTP_201_CREATED)
def create_learning_event(
    payload: LearningEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningEvent:
    course, unit, assignment = _resolve_learning_scope(db, payload)
    if course is None:
        raise HTTPException(status_code=422, detail="Learning event must target a course, unit, or assignment")
    _require_course_visible(db, current_user, course.id)

    class_group: ClassGroup | None = None
    if payload.class_id is not None:
        class_group = _require_class_member(db, current_user, payload.class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to course school")
        if not _course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")

    event = LearningEvent(
        user_id=current_user.id,
        school_id=course.school_id,
        class_id=class_group.id if class_group is not None else None,
        course_id=course.id,
        unit_id=unit.id if unit is not None else None,
        assignment_id=assignment.id if assignment is not None else None,
        event_type=payload.event_type,
        payload=payload.payload,
        occurred_at=payload.occurred_at or utc_now(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=list[LearningEventRead])
def list_learning_events(
    class_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LearningEvent]:
    statement = select(LearningEvent).order_by(LearningEvent.id)
    if current_user.role == "admin":
        if class_id is not None:
            statement = statement.where(LearningEvent.class_id == class_id)
        if user_id is not None:
            statement = statement.where(LearningEvent.user_id == user_id)
        return list(db.scalars(statement).all())

    if current_user.role == "student":
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Students can only view their own learning events")
        statement = statement.where(LearningEvent.user_id == current_user.id)
        if class_id is not None:
            _require_class_member(db, current_user, class_id)
            statement = statement.where(LearningEvent.class_id == class_id)
        return list(db.scalars(statement).all())

    if class_id is not None:
        class_group = _get_class(db, class_id)
        _require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})
        statement = statement.where(LearningEvent.class_id == class_id)
        if user_id is not None:
            statement = statement.where(LearningEvent.user_id == user_id)
        return list(db.scalars(statement).all())

    school_ids = _teacher_school_ids(db, current_user.id)
    if not school_ids:
        return []
    statement = statement.where(LearningEvent.school_id.in_(school_ids))
    if user_id is not None:
        statement = statement.where(LearningEvent.user_id == user_id)
    return list(db.scalars(statement).all())


def _resolve_learning_scope(
    db: Session,
    payload: LearningEventCreate,
) -> tuple[Course | None, CourseUnit | None, Assignment | None]:
    assignment: Assignment | None = None
    unit: CourseUnit | None = None
    course: Course | None = None

    if payload.assignment_id is not None:
        assignment = db.get(Assignment, payload.assignment_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail="Assignment not found")
        unit = db.get(CourseUnit, assignment.unit_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Course unit not found")
        course = db.get(Course, unit.course_id)
    elif payload.unit_id is not None:
        unit = db.get(CourseUnit, payload.unit_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Course unit not found")
        course = db.get(Course, unit.course_id)
    elif payload.course_id is not None:
        course = db.get(Course, payload.course_id)

    if course is None and (payload.course_id is not None or unit is not None):
        raise HTTPException(status_code=404, detail="Course not found")
    if payload.course_id is not None and course is not None and course.id != payload.course_id:
        raise HTTPException(status_code=422, detail="Course scope does not match referenced resource")
    if payload.unit_id is not None and unit is not None and unit.id != payload.unit_id:
        raise HTTPException(status_code=422, detail="Unit scope does not match referenced resource")
    return course, unit, assignment


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _teacher_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.role.in_(["admin", "teacher"]),
                SchoolMembership.status == "active",
            )
        ).all()
    )


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
