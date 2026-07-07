from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import (
    Assignment,
    ClassGroup,
    Course,
    CourseClass,
    CourseCollaborator,
    CourseUnit,
    SchoolMembership,
    User,
)
from app.schemas.course import (
    AssignmentCreate,
    AssignmentRead,
    CourseClassAttach,
    CourseClassRead,
    CourseCollaboratorCreate,
    CourseCollaboratorRead,
    CourseCollaboratorUpdate,
    CourseCreate,
    CourseRead,
    CourseUnitCreate,
    CourseUnitRead,
)
from app.services.audit import record_audit_log
from app.services.access_control import (
    get_course,
    require_class_member,
    require_class_teacher_or_admin,
    require_course_author_or_admin,
    require_course_editor_or_admin,
    require_course_visible,
    require_school_member,
    require_school_role,
    teacher_school_ids,
    visible_class_ids,
)
from app.services.text import require_trimmed_text


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
        class_group = require_class_member(db, current_user, class_id)
        if school_id is not None and class_group.school_id != school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to requested school")
        statement = statement.join(CourseClass, CourseClass.course_id == Course.id).where(
            CourseClass.class_id == class_id,
            CourseClass.status == "active",
        )
    elif school_id is not None:
        require_school_member(db, current_user, school_id)
        statement = statement.where(Course.school_id == school_id)
        if current_user.role == "student":
            class_ids = visible_class_ids(db, current_user.id)
            if not class_ids:
                return []
            statement = statement.join(CourseClass, CourseClass.course_id == Course.id).where(
                CourseClass.class_id.in_(class_ids),
                CourseClass.status == "active",
            )
    elif current_user.role != "admin":
        school_ids = teacher_school_ids(db, current_user.id)
        if school_ids:
            statement = statement.where(Course.school_id.in_(school_ids))
            return list(db.scalars(statement).all())
        class_ids = visible_class_ids(db, current_user.id)
        if not class_ids:
            return []
        statement = statement.join(CourseClass, CourseClass.course_id == Course.id).where(
            CourseClass.class_id.in_(class_ids),
            CourseClass.status == "active",
        )
    if current_user.role == "student":
        statement = statement.where(Course.status == "published").distinct()
    return list(db.scalars(statement).all())


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    require_school_role(db, current_user, payload.school_id, {"admin", "teacher"})
    title = require_trimmed_text(payload.title, "Course title is required")
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
        event_result="success",
        request=request,
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseClass:
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    class_group = db.get(ClassGroup, payload.class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_group.school_id != course.school_id:
        raise HTTPException(status_code=422, detail="Class must belong to course school")
    require_class_teacher_or_admin(
        db,
        current_user,
        class_group,
        detail="Course class attachment requires class teacher role",
    )

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
        event_result="success",
        request=request,
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


@router.get("/{course_id}/collaborators", response_model=list[CourseCollaboratorRead])
def list_course_collaborators(
    course_id: int,
    status_filter: str = Query(default="active", alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseCollaborator]:
    if status_filter not in {"active", "inactive", "all"}:
        raise HTTPException(status_code=400, detail="Invalid collaborator status")
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_editor_or_admin(
        db,
        current_user,
        course,
        detail="Course collaborators require course editor role",
    )
    statement = select(CourseCollaborator).where(CourseCollaborator.course_id == course.id).order_by(
        CourseCollaborator.id
    )
    if status_filter != "all":
        statement = statement.where(CourseCollaborator.status == status_filter)
    return list(db.scalars(statement).all())


@router.post(
    "/{course_id}/collaborators",
    response_model=CourseCollaboratorRead,
    status_code=status.HTTP_201_CREATED,
)
def create_course_collaborator(
    course_id: int,
    payload: CourseCollaboratorCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseCollaborator:
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_author_or_admin(
        current_user,
        course,
        detail="Course collaborator management requires course owner role",
    )
    _require_active_school_teacher(db, course.school_id, payload.user_id)
    if payload.user_id == course.creator_user_id:
        raise HTTPException(status_code=409, detail="Course creator is already an owner")
    existing = db.scalar(
        select(CourseCollaborator).where(
            CourseCollaborator.course_id == course.id,
            CourseCollaborator.user_id == payload.user_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Course collaborator already exists")

    collaborator = CourseCollaborator(
        course_id=course.id,
        user_id=payload.user_id,
        role=payload.role,
        status="active",
    )
    db.add(collaborator)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="course.collaborator.create",
        resource_type="course_collaborator",
        resource_id=collaborator.id,
        school_id=course.school_id,
        event_result="success",
        request=request,
        snapshot={"after": _course_collaborator_snapshot(collaborator)},
    )
    db.commit()
    db.refresh(collaborator)
    return collaborator


@router.patch("/{course_id}/collaborators/{collaborator_id}", response_model=CourseCollaboratorRead)
def update_course_collaborator(
    course_id: int,
    collaborator_id: int,
    payload: CourseCollaboratorUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseCollaborator:
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_author_or_admin(
        current_user,
        course,
        detail="Course collaborator management requires course owner role",
    )
    collaborator = db.get(CourseCollaborator, collaborator_id)
    if collaborator is None or collaborator.course_id != course.id:
        raise HTTPException(status_code=404, detail="Course collaborator not found")
    before = _course_collaborator_snapshot(collaborator)
    if collaborator.status == payload.status:
        return collaborator

    collaborator.status = payload.status
    after = _course_collaborator_snapshot(collaborator)
    record_audit_log(
        db,
        actor=current_user,
        action="course.collaborator.update",
        resource_type="course_collaborator",
        resource_id=collaborator.id,
        school_id=course.school_id,
        event_result="success",
        request=request,
        snapshot={"before": before, "after": after},
    )
    db.commit()
    db.refresh(collaborator)
    return collaborator


@router.get("/{course_id}/units", response_model=list[CourseUnitRead])
def list_course_units(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseUnit]:
    require_course_visible(db, current_user, course_id)
    statement = select(CourseUnit).where(CourseUnit.course_id == course_id).order_by(CourseUnit.position)
    if current_user.role == "student":
        statement = statement.where(CourseUnit.status == "published")
    return list(db.scalars(statement).all())


@router.post("/{course_id}/units", response_model=CourseUnitRead, status_code=status.HTTP_201_CREATED)
def create_course_unit(
    course_id: int,
    payload: CourseUnitCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseUnit:
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_editor_or_admin(
        db,
        current_user,
        course,
        detail="Course unit creation requires course editor role",
    )
    content_slug = (payload.content_slug or "").strip() or None
    title = require_trimmed_text(payload.title, "Course unit title is required")
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
        title=title,
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
        event_result="success",
        request=request,
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
    require_course_visible(db, current_user, course_id)
    statement = (
        select(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .where(CourseUnit.course_id == course_id)
        .order_by(Assignment.id)
    )
    if current_user.role == "student":
        statement = statement.where(CourseUnit.status == "published", Assignment.status == "active")
    return list(db.scalars(statement).all())


@router.post(
    "/{course_id}/units/{unit_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    course_id: int,
    unit_id: int,
    payload: AssignmentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Assignment:
    course = get_course(db, course_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_editor_or_admin(
        db,
        current_user,
        course,
        detail="Assignment creation requires course editor role",
    )
    unit = db.get(CourseUnit, unit_id)
    if unit is None or unit.course_id != course_id:
        raise HTTPException(status_code=404, detail="Course unit not found")
    title = require_trimmed_text(payload.title, "Assignment title is required")
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
        event_result="success",
        request=request,
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


def _require_active_school_teacher(db: Session, school_id: int, user_id: int) -> None:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Course collaborator user not found")
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user_id,
            SchoolMembership.role.in_(["admin", "teacher"]),
            SchoolMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=422, detail="Course collaborator must be active school teacher/admin")


def _course_collaborator_snapshot(collaborator: CourseCollaborator) -> dict:
    return {
        "id": collaborator.id,
        "course_id": collaborator.course_id,
        "user_id": collaborator.user_id,
        "role": collaborator.role,
        "status": collaborator.status,
    }
