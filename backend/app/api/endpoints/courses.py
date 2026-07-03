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
    SchoolMembership,
    User,
)
from app.schemas.course import (
    AssignmentCreate,
    AssignmentRead,
    CourseClassAttach,
    CourseClassRead,
    CourseCreate,
    CourseRead,
    CourseUnitCreate,
    CourseUnitRead,
)
from app.services.audit import record_audit_log


router = APIRouter()


@router.get("", response_model=list[CourseRead])
def list_courses(
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Course]:
    statement = select(Course).order_by(Course.id)
    if class_id is not None:
        class_group = _require_class_member(db, current_user, class_id)
        if school_id is not None and class_group.school_id != school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to requested school")
        statement = statement.join(CourseClass, CourseClass.course_id == Course.id).where(
            CourseClass.class_id == class_id,
            CourseClass.status == "active",
        )
    elif school_id is not None:
        _require_school_member(db, current_user, school_id)
        statement = statement.where(Course.school_id == school_id)
    elif current_user.role != "admin":
        teacher_school_ids = _teacher_school_ids(db, current_user.id)
        if teacher_school_ids:
            statement = statement.where(Course.school_id.in_(teacher_school_ids))
            return list(db.scalars(statement).all())
        class_ids = _visible_class_ids(db, current_user.id)
        if not class_ids:
            return []
        statement = statement.join(CourseClass, CourseClass.course_id == Course.id).where(
            CourseClass.class_id.in_(class_ids),
            CourseClass.status == "active",
        )
    return list(db.scalars(statement).all())


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    _require_school_role(db, current_user, payload.school_id, {"admin", "teacher"})
    title = payload.title.strip()
    existing = db.scalar(select(Course).where(Course.school_id == payload.school_id, Course.title == title))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Course already exists in this school")

    course = Course(
        school_id=payload.school_id,
        creator_user_id=current_user.id,
        title=title,
        summary=(payload.summary or "").strip() or None,
        status=payload.status,
    )
    db.add(course)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="course.create",
        resource_type="course",
        resource_id=course.id,
        school_id=course.school_id,
        snapshot={
            "after": {
                "school_id": course.school_id,
                "creator_user_id": course.creator_user_id,
                "title": course.title,
                "summary": course.summary,
                "status": course.status,
            }
        },
    )
    db.commit()
    db.refresh(course)
    return course


@router.post("/{course_id}/classes", response_model=CourseClassRead, status_code=status.HTTP_201_CREATED)
def attach_course_class(
    course_id: int,
    payload: CourseClassAttach,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseClass:
    course = _get_course(db, course_id)
    _require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    class_group = db.get(ClassGroup, payload.class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_group.school_id != course.school_id:
        raise HTTPException(status_code=422, detail="Class must belong to course school")

    existing = db.scalar(
        select(CourseClass).where(CourseClass.course_id == course.id, CourseClass.class_id == class_group.id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Course is already attached to this class")

    course_class = CourseClass(course_id=course.id, class_id=class_group.id)
    db.add(course_class)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="course.class.attach",
        resource_type="course_class",
        resource_id=course_class.id,
        school_id=course.school_id,
        class_id=class_group.id,
        snapshot={
            "after": {
                "course_id": course_class.course_id,
                "class_id": course_class.class_id,
                "status": course_class.status,
            }
        },
    )
    db.commit()
    db.refresh(course_class)
    return course_class


@router.get("/{course_id}/units", response_model=list[CourseUnitRead])
def list_course_units(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseUnit]:
    _require_course_visible(db, current_user, course_id)
    return list(
        db.scalars(select(CourseUnit).where(CourseUnit.course_id == course_id).order_by(CourseUnit.position)).all()
    )


@router.post("/{course_id}/units", response_model=CourseUnitRead, status_code=status.HTTP_201_CREATED)
def create_course_unit(
    course_id: int,
    payload: CourseUnitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseUnit:
    course = _get_course(db, course_id)
    _require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    content_slug = (payload.content_slug or "").strip() or None
    existing_position = db.scalar(
        select(CourseUnit).where(CourseUnit.course_id == course_id, CourseUnit.position == payload.position)
    )
    if existing_position is not None:
        raise HTTPException(status_code=409, detail="Course unit position already exists")
    if content_slug is not None:
        existing_slug = db.scalar(
            select(CourseUnit).where(CourseUnit.course_id == course_id, CourseUnit.content_slug == content_slug)
        )
        if existing_slug is not None:
            raise HTTPException(status_code=409, detail="Course unit content slug already exists")

    unit = CourseUnit(
        course_id=course_id,
        title=payload.title.strip(),
        position=payload.position,
        content_slug=content_slug,
        status=payload.status,
    )
    db.add(unit)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="course.unit.create",
        resource_type="course_unit",
        resource_id=unit.id,
        school_id=course.school_id,
        snapshot={
            "after": {
                "course_id": unit.course_id,
                "title": unit.title,
                "position": unit.position,
                "content_slug": unit.content_slug,
                "status": unit.status,
            }
        },
    )
    db.commit()
    db.refresh(unit)
    return unit


@router.get("/{course_id}/assignments", response_model=list[AssignmentRead])
def list_course_assignments(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Assignment]:
    _require_course_visible(db, current_user, course_id)
    return list(
        db.scalars(
            select(Assignment)
            .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
            .where(CourseUnit.course_id == course_id)
            .order_by(Assignment.id)
        ).all()
    )


@router.post(
    "/{course_id}/units/{unit_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    course_id: int,
    unit_id: int,
    payload: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    course = _get_course(db, course_id)
    _require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    unit = db.get(CourseUnit, unit_id)
    if unit is None or unit.course_id != course_id:
        raise HTTPException(status_code=404, detail="Course unit not found")
    title = payload.title.strip()
    existing = db.scalar(select(Assignment).where(Assignment.unit_id == unit_id, Assignment.title == title))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Assignment already exists in this unit")

    assignment = Assignment(
        unit_id=unit_id,
        title=title,
        description=(payload.description or "").strip() or None,
        due_at=payload.due_at,
        max_score=payload.max_score,
        status=payload.status,
    )
    db.add(assignment)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="assignment.create",
        resource_type="assignment",
        resource_id=assignment.id,
        school_id=course.school_id,
        snapshot={
            "after": {
                "course_id": course.id,
                "unit_id": assignment.unit_id,
                "title": assignment.title,
                "due_at": assignment.due_at.isoformat() if assignment.due_at is not None else None,
                "max_score": assignment.max_score,
                "status": assignment.status,
            }
        },
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def _get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _visible_class_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.class_id).where(
                ClassMembership.user_id == user_id,
                ClassMembership.status == "active",
            )
        ).all()
    )


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
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
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


def _require_school_member(db: Session, user: User, school_id: int) -> None:
    if user.role == "admin":
        return
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="School is outside current user scope")


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
