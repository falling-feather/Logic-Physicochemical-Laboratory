from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ClassGroup, ClassMembership, School, SchoolMembership, User
from app.schemas.admin import AdminClassUpdate, AdminSchoolUpdate
from app.services.admin_common import lock_active_admin
from app.services.audit import record_audit_log
from app.services.security_control_locks import ADMIN_AUTHORITY_LOCK, acquire_security_control_lock


_SCHOOL_MUTABLE_FIELDS = {"name", "region", "description", "status"}
_CLASS_MUTABLE_FIELDS = {"name", "grade", "term", "description", "status"}


def update_admin_school(
    db: Session,
    *,
    school_id: int,
    payload: AdminSchoolUpdate,
    actor: User,
    request: Request,
) -> School:
    acquire_security_control_lock(db, ADMIN_AUTHORITY_LOCK)
    school = db.scalar(
        select(School)
        .where(School.id == school_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    actor = lock_active_admin(db, actor.id)
    if school.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Organization version conflict")

    reason = _normalized_reason(payload.reason)
    changes = _school_changes(payload)
    before = _school_snapshot(school)
    effective = _effective_changes(before, changes)
    if not effective:
        raise HTTPException(status_code=409, detail="Organization update has no changes")

    responsibility_count = _active_school_responsibility_count(db, school.id)
    active_child_class_count = _active_child_class_count(db, school.id)
    next_status = effective.get("status", school.status)
    if next_status != school.status:
        if responsibility_count < 1:
            raise HTTPException(status_code=409, detail="School requires an active responsible member")
        if next_status == "archived" and active_child_class_count:
            raise HTTPException(status_code=409, detail="Archive active classes before archiving school")

    action = _governance_action("school", school.status, next_status)
    try:
        result = db.execute(
            update(School)
            .where(School.id == school.id, School.version == payload.expected_version)
            .values(**effective, version=School.version + 1)
        )
    except IntegrityError as exc:
        db.rollback()
        if _is_unique_violation(exc):
            raise HTTPException(status_code=409, detail="School name already exists") from None
        raise
    if int(result.rowcount or 0) != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization version conflict")
    school = db.scalar(
        select(School)
        .where(School.id == school.id)
        .execution_options(populate_existing=True)
    )
    if school is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="School not found")
    after = _school_snapshot(school)
    record_audit_log(
        db,
        actor=actor,
        action=action,
        resource_type="school",
        resource_id=school.id,
        school_id=school.id,
        event_result="success",
        request=request,
        snapshot={
            "before": before,
            "after": after,
            "changes": _change_snapshot(before, after, effective),
            "expected_version": payload.expected_version,
            "new_version": school.version,
            "reason": reason,
            "responsible_count": responsibility_count,
            "active_child_class_count": active_child_class_count,
        },
    )
    db.commit()
    db.refresh(school)
    return school


def update_admin_class(
    db: Session,
    *,
    class_id: int,
    payload: AdminClassUpdate,
    actor: User,
    request: Request,
) -> ClassGroup:
    acquire_security_control_lock(db, ADMIN_AUTHORITY_LOCK)
    school_id = db.scalar(select(ClassGroup.school_id).where(ClassGroup.id == class_id))
    if school_id is None:
        raise HTTPException(status_code=404, detail="Class not found")
    school = db.scalar(
        select(School)
        .where(School.id == school_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    class_group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.id == class_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if school is None or class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if class_group.school_id != school.id:
        raise HTTPException(status_code=409, detail="Class organization changed during update")
    actor = lock_active_admin(db, actor.id)
    if class_group.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Organization version conflict")

    reason = _normalized_reason(payload.reason)
    changes = _class_changes(payload)
    before = _class_snapshot(class_group)
    effective = _effective_changes(before, changes)
    if not effective:
        raise HTTPException(status_code=409, detail="Organization update has no changes")

    active_teacher_count = _active_class_teacher_count(db, class_group.id)
    next_status = effective.get("status", class_group.status)
    if next_status != class_group.status:
        if active_teacher_count < 1:
            raise HTTPException(status_code=409, detail="Class requires an active teacher")
        if next_status == "active" and school.status != "active":
            raise HTTPException(status_code=409, detail="Cannot restore class under archived school")

    action = _governance_action("class", class_group.status, next_status)
    try:
        result = db.execute(
            update(ClassGroup)
            .where(ClassGroup.id == class_group.id, ClassGroup.version == payload.expected_version)
            .values(**effective, version=ClassGroup.version + 1)
        )
    except IntegrityError as exc:
        db.rollback()
        if _is_unique_violation(exc):
            raise HTTPException(status_code=409, detail="Class name already exists in school") from None
        raise
    if int(result.rowcount or 0) != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Organization version conflict")
    class_group = db.scalar(
        select(ClassGroup)
        .where(ClassGroup.id == class_group.id)
        .execution_options(populate_existing=True)
    )
    if class_group is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Class not found")
    after = _class_snapshot(class_group)
    record_audit_log(
        db,
        actor=actor,
        action=action,
        resource_type="class",
        resource_id=class_group.id,
        school_id=class_group.school_id,
        class_id=class_group.id,
        event_result="success",
        request=request,
        snapshot={
            "before": before,
            "after": after,
            "changes": _change_snapshot(before, after, effective),
            "expected_version": payload.expected_version,
            "new_version": class_group.version,
            "reason": reason,
            "active_teacher_count": active_teacher_count,
        },
    )
    db.commit()
    db.refresh(class_group)
    return class_group


def _school_changes(payload: AdminSchoolUpdate) -> dict[str, Any]:
    fields = payload.model_fields_set.intersection(_SCHOOL_MUTABLE_FIELDS)
    if not fields:
        raise HTTPException(status_code=422, detail="At least one school field is required")
    changes: dict[str, Any] = {}
    for field in fields:
        value = getattr(payload, field)
        if field == "name":
            changes[field] = _required_text(value, "School name is required")
        elif field in {"region", "description"}:
            changes[field] = _optional_text(value)
        else:
            if value is None:
                raise HTTPException(status_code=422, detail="School status is required")
            changes[field] = value
    return changes


def _class_changes(payload: AdminClassUpdate) -> dict[str, Any]:
    fields = payload.model_fields_set.intersection(_CLASS_MUTABLE_FIELDS)
    if not fields:
        raise HTTPException(status_code=422, detail="At least one class field is required")
    changes: dict[str, Any] = {}
    for field in fields:
        value = getattr(payload, field)
        if field == "name":
            changes[field] = _required_text(value, "Class name is required")
        elif field in {"grade", "term", "description"}:
            changes[field] = _optional_text(value)
        else:
            if value is None:
                raise HTTPException(status_code=422, detail="Class status is required")
            changes[field] = value
    return changes


def _normalized_reason(value: str) -> str:
    reason = value.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Organization update reason is required")
    if len(reason) > 500:
        raise HTTPException(status_code=422, detail="Organization update reason is too long")
    return reason


def _required_text(value: str | None, detail: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=detail)
    return normalized


def _optional_text(value: str | None) -> str | None:
    return (value or "").strip() or None


def _is_unique_violation(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    if args and args[0] == 1062:
        return True
    return "unique constraint failed" in str(original).lower()


def _effective_changes(before: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    return {field: value for field, value in changes.items() if before.get(field) != value}


def _change_snapshot(
    before: dict[str, Any],
    after: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {field: {"before": before.get(field), "after": after.get(field)} for field in changes}


def _governance_action(resource: str, previous_status: str, next_status: str) -> str:
    if previous_status != next_status:
        transition = "archive" if next_status == "archived" else "restore"
        return f"admin.{resource}.{transition}"
    return f"admin.{resource}.update"


def _school_snapshot(school: School) -> dict[str, Any]:
    return {
        "id": school.id,
        "name": school.name,
        "region": school.region,
        "description": school.description,
        "status": school.status,
        "version": school.version,
    }


def _class_snapshot(class_group: ClassGroup) -> dict[str, Any]:
    return {
        "id": class_group.id,
        "school_id": class_group.school_id,
        "name": class_group.name,
        "grade": class_group.grade,
        "term": class_group.term,
        "description": class_group.description,
        "status": class_group.status,
        "version": class_group.version,
    }


def _active_school_responsibility_count(db: Session, school_id: int) -> int:
    return len(
        db.execute(
            select(SchoolMembership.id, User.id)
            .join(User, User.id == SchoolMembership.user_id)
            .where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.role.in_(["admin", "teacher"]),
                SchoolMembership.status == "active",
                User.role.in_(["admin", "teacher"]),
                User.status == "active",
            )
            .with_for_update()
        ).all()
    )


def _active_child_class_count(db: Session, school_id: int) -> int:
    return len(
        db.scalars(
            select(ClassGroup.id)
            .where(
                ClassGroup.school_id == school_id,
                ClassGroup.status == "active",
            )
            .order_by(ClassGroup.id)
            .with_for_update()
        ).all()
    )


def _active_class_teacher_count(db: Session, class_id: int) -> int:
    return len(
        db.execute(
            select(ClassMembership.id, User.id)
            .join(User, User.id == ClassMembership.user_id)
            .where(
                ClassMembership.class_id == class_id,
                ClassMembership.role == "teacher",
                ClassMembership.status == "active",
                User.role.in_(["admin", "teacher"]),
                User.status == "active",
            )
            .with_for_update()
        ).all()
    )
