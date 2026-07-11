from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    AssignmentClassPolicy,
    ClassGroup,
    Course,
    CourseUnit,
    LearningEvent,
    User,
)
from app.models.base import utc_now
from app.schemas.course import LearningEventCreate, LearningEventRead
from app.services.access_control import (
    course_attached_to_class,
    get_class,
    require_class_member,
    require_class_teacher_or_admin,
    require_course_visible,
    require_student_unit_published,
    teacher_class_ids,
)
from app.services.assignment_policies import resolve_assignment_class_policy


router = APIRouter()


@router.post("", response_model=LearningEventRead, status_code=status.HTTP_201_CREATED)
def create_learning_event(
    payload: LearningEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningEvent:
    if payload.assignment_id is not None and payload.class_id is None:
        raise HTTPException(status_code=422, detail="Assignment learning events require class_id")
    course, unit, assignment = _resolve_learning_scope(db, payload)
    if course is None:
        raise HTTPException(status_code=422, detail="Learning event must target a course, unit, or assignment")
    require_course_visible(db, current_user, course.id)
    if unit is not None:
        require_student_unit_published(current_user, unit)

    class_group: ClassGroup | None = None
    if payload.class_id is not None:
        class_group = require_class_member(db, current_user, payload.class_id)
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to course school")
        if not course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
    if assignment is not None and class_group is not None:
        effective = resolve_assignment_class_policy(db, assignment, class_group.id)
        if not effective.assigned:
            raise HTTPException(status_code=403, detail="Assignment is not assigned to this class")
        if current_user.role == "student" and effective.status != "active":
            raise HTTPException(status_code=409, detail="Assignment is not active")

    event = LearningEvent(
        user_id=current_user.id,
        school_id=course.school_id,
        class_id=class_group.id if class_group is not None else None,
        course_id=course.id,
        unit_id=unit.id if unit is not None else None,
        assignment_id=assignment.id if assignment is not None else None,
        knowledge_code=(payload.knowledge_code or "").strip().lower() or None,
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
            require_class_member(db, current_user, class_id)
            statement = statement.where(LearningEvent.class_id == class_id)
        statement = _apply_student_visible_event_filters(statement)
        return list(db.scalars(statement).all())

    if class_id is not None:
        class_group = get_class(db, class_id)
        require_class_teacher_or_admin(
            db,
            current_user,
            class_group,
            detail="Learning events require class teacher scope",
        )
        statement = statement.where(LearningEvent.class_id == class_id)
        if user_id is not None:
            statement = statement.where(LearningEvent.user_id == user_id)
        return list(db.scalars(statement).all())

    class_ids = teacher_class_ids(db, current_user.id)
    if not class_ids:
        return []
    statement = statement.where(LearningEvent.class_id.in_(class_ids))
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


def _apply_student_visible_event_filters(statement):
    effective_assignment_status = func.coalesce(AssignmentClassPolicy.status_override, Assignment.status)
    assignment_is_visible = or_(
        and_(
            Assignment.audience_mode == "selected_classes",
            AssignmentClassPolicy.id.is_not(None),
            AssignmentClassPolicy.assigned.is_(True),
        ),
        and_(
            Assignment.audience_mode == "all_attached_classes",
            or_(AssignmentClassPolicy.id.is_(None), AssignmentClassPolicy.assigned.is_(True)),
        ),
    )
    return (
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
                and_(assignment_is_visible, effective_assignment_status == "active"),
            ),
        )
    )
