from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClassGroup, ClassJoinRequest, ClassMembership, SchoolMembership, User
from app.models.base import utc_now
from app.services.audit import record_audit_log


CLASS_ROLES = {"student", "teacher"}
JOIN_REQUEST_STATUSES = {"pending", "approved", "rejected"}


def normalize_class_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in CLASS_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported class role")
    return normalized


def normalize_join_request_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in JOIN_REQUEST_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported class join request status")
    return normalized


def ensure_school_membership(db: Session, school_id: int, user_id: int, role: str) -> SchoolMembership:
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user_id,
            SchoolMembership.role == role,
        )
    )
    if membership is None:
        membership = SchoolMembership(school_id=school_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
    return membership


def ensure_class_membership(
    db: Session,
    class_id: int,
    user_id: int,
    role: str,
) -> tuple[ClassMembership, bool]:
    membership = db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user_id,
            ClassMembership.role == role,
        )
    )
    if membership is None:
        membership = ClassMembership(class_id=class_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
        return membership, True
    return membership, False


def existing_active_class_membership(
    db: Session,
    class_id: int,
    user_id: int,
    role: str,
) -> ClassMembership | None:
    return db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user_id,
            ClassMembership.role == role,
            ClassMembership.status == "active",
        )
    )


def apply_class_join_request_review(
    db: Session,
    *,
    join_request: ClassJoinRequest,
    reviewer: User,
    request: Request,
    next_status: str,
    note: str | None,
    approval_source: str,
) -> ClassJoinRequest:
    next_status = normalize_join_request_status(next_status)
    if next_status == "pending":
        raise HTTPException(status_code=422, detail="Class join request review requires approved or rejected")
    if join_request.status in {"approved", "rejected"}:
        if join_request.status == next_status:
            return join_request
        raise HTTPException(status_code=409, detail="Class join request already reviewed")

    class_group = db.get(ClassGroup, join_request.class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")

    before_status = join_request.status
    before_reviewed_by_user_id = join_request.reviewed_by_user_id
    join_request.status = next_status
    join_request.reviewed_by_user_id = reviewer.id
    join_request.reviewed_at = utc_now()
    join_request.review_note = trim_optional(note)

    membership_created = False
    membership: ClassMembership | None = None
    if next_status == "approved":
        ensure_school_membership(db, join_request.school_id, join_request.user_id, join_request.role)
        membership, membership_created = ensure_class_membership(
            db,
            join_request.class_id,
            join_request.user_id,
            join_request.role,
        )
        if membership_created:
            record_audit_log(
                db,
                actor=reviewer,
                action="class.join",
                resource_type="class_membership",
                resource_id=membership.id,
                school_id=class_group.school_id,
                class_id=class_group.id,
                event_result="success",
                request=request,
                snapshot={
                    "after": {
                        "class_id": membership.class_id,
                        "user_id": membership.user_id,
                        "role": membership.role,
                        "status": membership.status,
                        "source_join_request_id": join_request.id,
                    }
                },
            )

    record_audit_log(
        db,
        actor=reviewer,
        action=join_request_review_action(next_status),
        resource_type="class_join_request",
        resource_id=join_request.id,
        school_id=class_group.school_id,
        class_id=class_group.id,
        event_result="success",
        request=request,
        snapshot={
            "before": {
                "status": before_status,
                "reviewed_by_user_id": before_reviewed_by_user_id,
            },
            "after": {
                "class_id": join_request.class_id,
                "user_id": join_request.user_id,
                "role": join_request.role,
                "status": join_request.status,
                "reviewed_by_user_id": join_request.reviewed_by_user_id,
                "reviewer_role": reviewer.role,
                "has_review_note": join_request.review_note is not None,
                "approval_source": approval_source,
                "membership_created": membership_created,
                "membership_id": membership.id if membership is not None else None,
            }
        },
    )
    return join_request


def join_request_review_action(status_value: str) -> str:
    if status_value == "approved":
        return "class.join.request.approve"
    return "class.join.request.reject"


def trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
