from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ClassGroup, ClassJoinRequest, ClassMembership, SchoolMembership, User
from app.models.base import utc_now
from app.schemas.school import (
    ClassCreate,
    ClassJoinPayload,
    ClassJoinRequestCreate,
    ClassJoinRequestRead,
    ClassJoinRequestReview,
    ClassRead,
    MembershipRead,
)
from app.services.audit import record_audit_log


router = APIRouter()
_CLASS_ROLES = {"student", "teacher"}
_JOIN_REQUEST_STATUSES = {"pending", "approved", "rejected"}


@router.get("", response_model=list[ClassRead])
def list_classes(
    school_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassGroup]:
    statement = select(ClassGroup).order_by(ClassGroup.id)
    if school_id is not None:
        _require_school_member(db, current_user, school_id)
        statement = statement.where(ClassGroup.school_id == school_id)
    elif current_user.role != "admin":
        school_ids = _visible_school_ids(db, current_user.id)
        if not school_ids:
            return []
        statement = statement.where(ClassGroup.school_id.in_(school_ids))
    return list(db.scalars(statement).all())


@router.post("", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassGroup:
    _require_school_role(db, current_user, payload.school_id, {"admin", "teacher"})
    existing = db.scalar(
        select(ClassGroup).where(
            ClassGroup.school_id == payload.school_id,
            ClassGroup.name == payload.name.strip(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Class already exists in this school")

    class_group = ClassGroup(
        school_id=payload.school_id,
        name=payload.name.strip(),
        grade=(payload.grade or "").strip() or None,
        term=(payload.term or "").strip() or None,
    )
    db.add(class_group)
    db.flush()
    _ensure_school_membership(db, payload.school_id, current_user.id, "teacher")
    _ensure_class_membership(db, class_group.id, current_user.id, "teacher")
    record_audit_log(
        db,
        actor=current_user,
        action="class.create",
        resource_type="class",
        resource_id=class_group.id,
        school_id=class_group.school_id,
        class_id=class_group.id,
        event_result="success",
        request=request,
        snapshot={
            "after": {
                "school_id": class_group.school_id,
                "name": class_group.name,
                "grade": class_group.grade,
                "term": class_group.term,
                "status": class_group.status,
                "creator_membership_role": "teacher",
            }
        },
    )
    db.commit()
    db.refresh(class_group)
    return class_group


@router.post("/{class_id}/join", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
def join_class(
    class_id: int,
    payload: ClassJoinPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassMembership:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")

    role = _normalize_class_role(payload.role)
    if role == "teacher" and current_user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Only teachers can join with teacher role")
    if role == "teacher" and current_user.role != "admin":
        _require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})

    _ensure_school_membership(db, class_group.school_id, current_user.id, role)
    membership, membership_created = _ensure_class_membership(db, class_group.id, current_user.id, role)
    join_request = db.scalar(
        select(ClassJoinRequest).where(
            ClassJoinRequest.class_id == class_group.id,
            ClassJoinRequest.user_id == current_user.id,
            ClassJoinRequest.role == role,
            ClassJoinRequest.status == "pending",
        )
    )
    if join_request is not None:
        join_request.status = "approved"
        join_request.reviewed_by_user_id = current_user.id
        join_request.reviewed_at = utc_now()
        join_request.review_note = "approved by legacy direct join"
        record_audit_log(
            db,
            actor=current_user,
            action="class.join.request.approve",
            resource_type="class_join_request",
            resource_id=join_request.id,
            school_id=class_group.school_id,
            class_id=class_group.id,
            event_result="success",
            request=request,
            snapshot={
                "before": {
                    "status": "pending",
                },
                "after": {
                    "class_id": join_request.class_id,
                    "user_id": join_request.user_id,
                    "role": join_request.role,
                    "status": join_request.status,
                    "reviewed_by_user_id": join_request.reviewed_by_user_id,
                    "reviewer_role": current_user.role,
                    "approval_source": "legacy_direct_join",
                    "membership_created": membership_created,
                    "membership_id": membership.id,
                },
            },
        )
    if membership_created:
        record_audit_log(
            db,
            actor=current_user,
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
                }
            },
        )
    db.commit()
    db.refresh(membership)
    return membership


@router.post(
    "/{class_id}/join-requests",
    response_model=ClassJoinRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_class_join_request(
    class_id: int,
    payload: ClassJoinRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassJoinRequest:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")

    role = _normalize_class_role(payload.role)
    if role == "teacher" and current_user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Only teachers can request teacher role")
    if role == "teacher" and current_user.role != "admin":
        _require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})

    if _existing_active_class_membership(db, class_group.id, current_user.id, role) is not None:
        raise HTTPException(status_code=409, detail="Class membership already exists")

    join_request = db.scalar(
        select(ClassJoinRequest).where(
            ClassJoinRequest.class_id == class_group.id,
            ClassJoinRequest.user_id == current_user.id,
            ClassJoinRequest.role == role,
        )
    )
    if join_request is not None:
        if join_request.status == "pending":
            return join_request
        if join_request.status == "approved":
            raise HTTPException(status_code=409, detail="Class join request already approved")
        join_request.status = "pending"
        join_request.message = _trim_optional(payload.message)
        join_request.requested_by_user_id = current_user.id
        join_request.reviewed_by_user_id = None
        join_request.reviewed_at = None
        join_request.review_note = None
    else:
        join_request = ClassJoinRequest(
            school_id=class_group.school_id,
            class_id=class_group.id,
            user_id=current_user.id,
            role=role,
            status="pending",
            message=_trim_optional(payload.message),
            requested_by_user_id=current_user.id,
        )
        db.add(join_request)
        db.flush()

    record_audit_log(
        db,
        actor=current_user,
        action="class.join.request.create",
        resource_type="class_join_request",
        resource_id=join_request.id,
        school_id=class_group.school_id,
        class_id=class_group.id,
        event_result="success",
        request=request,
        snapshot={
            "after": {
                "class_id": join_request.class_id,
                "user_id": join_request.user_id,
                "role": join_request.role,
                "status": join_request.status,
                "has_message": join_request.message is not None,
            }
        },
    )
    db.commit()
    db.refresh(join_request)
    return join_request


@router.get("/{class_id}/join-requests", response_model=list[ClassJoinRequestRead])
def list_class_join_requests(
    class_id: int,
    status_filter: str | None = Query(default="pending", alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassJoinRequest]:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    _require_class_review_scope(db, current_user, class_group)

    statement = (
        select(ClassJoinRequest)
        .where(ClassJoinRequest.class_id == class_group.id)
        .order_by(ClassJoinRequest.id)
    )
    if status_filter is not None:
        statement = statement.where(ClassJoinRequest.status == _normalize_join_request_status(status_filter))
    return list(db.scalars(statement).all())


@router.patch("/{class_id}/join-requests/{join_request_id}", response_model=ClassJoinRequestRead)
def review_class_join_request(
    class_id: int,
    join_request_id: int,
    payload: ClassJoinRequestReview,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassJoinRequest:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    _require_class_review_scope(db, current_user, class_group)

    join_request = db.scalar(
        select(ClassJoinRequest).where(
            ClassJoinRequest.id == join_request_id,
            ClassJoinRequest.class_id == class_group.id,
        )
    )
    if join_request is None:
        raise HTTPException(status_code=404, detail="Class join request not found")

    next_status = payload.status
    if join_request.status in {"approved", "rejected"}:
        if join_request.status == next_status:
            return join_request
        raise HTTPException(status_code=409, detail="Class join request already reviewed")

    before_status = join_request.status
    before_reviewed_by_user_id = join_request.reviewed_by_user_id
    join_request.status = next_status
    join_request.reviewed_by_user_id = current_user.id
    join_request.reviewed_at = utc_now()
    join_request.review_note = _trim_optional(payload.note)

    membership_created = False
    membership: ClassMembership | None = None
    if next_status == "approved":
        _ensure_school_membership(db, join_request.school_id, join_request.user_id, join_request.role)
        membership, membership_created = _ensure_class_membership(
            db,
            join_request.class_id,
            join_request.user_id,
            join_request.role,
        )
        if membership_created:
            record_audit_log(
                db,
                actor=current_user,
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
        actor=current_user,
        action=_join_request_review_action(next_status),
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
                "reviewer_role": current_user.role,
                "has_review_note": join_request.review_note is not None,
                "membership_created": membership_created,
                "membership_id": membership.id if membership is not None else None,
            }
        },
    )
    db.commit()
    db.refresh(join_request)
    return join_request


def _visible_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.status == "active",
            )
        ).all()
    )


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


def _require_class_review_scope(db: Session, user: User, class_group: ClassGroup) -> None:
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
        raise HTTPException(status_code=403, detail="Class review scope requires class teacher role")


def _ensure_school_membership(db: Session, school_id: int, user_id: int, role: str) -> SchoolMembership:
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


def _ensure_class_membership(db: Session, class_id: int, user_id: int, role: str) -> tuple[ClassMembership, bool]:
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


def _existing_active_class_membership(
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


def _normalize_class_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in _CLASS_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported class role")
    return normalized


def _normalize_join_request_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _JOIN_REQUEST_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported class join request status")
    return normalized


def _join_request_review_action(status_value: str) -> str:
    if status_value == "approved":
        return "class.join.request.approve"
    return "class.join.request.reject"


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
