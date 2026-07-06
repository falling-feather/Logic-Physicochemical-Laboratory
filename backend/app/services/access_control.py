from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, ClassGroup, ClassMembership, Course, CourseClass, CourseUnit, SchoolMembership, User


def get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def visible_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.status == "active",
            )
        ).all()
    )


def teacher_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.role.in_(["admin", "teacher"]),
                SchoolMembership.status == "active",
            )
        ).all()
    )


def visible_class_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.class_id).where(
                ClassMembership.user_id == user_id,
                ClassMembership.status == "active",
            )
        ).all()
    )


def active_class_student_ids(db: Session, class_id: int) -> list[int]:
    return list(
        db.scalars(
            select(ClassMembership.user_id).where(
                ClassMembership.class_id == class_id,
                ClassMembership.role == "student",
                ClassMembership.status == "active",
            )
        ).all()
    )


def user_assignment_class_ids(db: Session, user_id: int, class_id: int | None) -> list[int]:
    if class_id is not None:
        return [class_id]
    return visible_class_ids(db, user_id)


def require_school_member(db: Session, user: User, school_id: int) -> None:
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


def require_school_role(db: Session, user: User, school_id: int, roles: set[str]) -> None:
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


def require_class_member(db: Session, user: User, class_id: int) -> ClassGroup:
    class_group = get_class(db, class_id)
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


def require_class_teacher_or_admin(
    db: Session,
    user: User,
    class_group: ClassGroup,
    *,
    detail: str = "Class statistics require teacher scope",
) -> None:
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
        raise HTTPException(status_code=403, detail=detail)


def require_course_visible(db: Session, user: User, course_id: int) -> Course:
    course = get_course(db, course_id)
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
    class_ids = visible_class_ids(db, user.id)
    if class_ids:
        course_class = db.scalar(
            select(CourseClass).where(
                CourseClass.course_id == course.id,
                CourseClass.class_id.in_(class_ids),
                CourseClass.status == "active",
            )
        )
        if course_class is not None:
            require_student_course_published(user, course)
            return course
    raise HTTPException(status_code=403, detail="Course is outside current user scope")


def require_course_scope(
    db: Session,
    user: User,
    class_group: ClassGroup | None,
    course_id: int,
) -> Course:
    course = get_course(db, course_id)
    if class_group is not None:
        if class_group.school_id != course.school_id:
            raise HTTPException(status_code=422, detail="Class does not belong to course school")
        if not course_attached_to_class(db, course.id, class_group.id):
            raise HTTPException(status_code=403, detail="Course is not attached to this class")
        require_student_course_published(user, course)
        return course
    return require_course_visible(db, user, course_id)


def course_attached_to_class(db: Session, course_id: int, class_id: int) -> bool:
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


def require_student_course_published(user: User, course: Course) -> None:
    if user.role == "student" and course.status != "published":
        raise HTTPException(status_code=403, detail="Course is not published")


def require_student_unit_published(user: User, unit: CourseUnit) -> None:
    if user.role == "student" and unit.status != "published":
        raise HTTPException(status_code=403, detail="Course unit is not published")


def require_student_assignment_active(user: User, assignment: Assignment) -> None:
    if user.role == "student" and assignment.status != "active":
        raise HTTPException(status_code=409, detail="Assignment is not active")
