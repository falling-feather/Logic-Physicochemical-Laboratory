from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ClassGroup, ClassJoinRequest, ClassMembership, User
from app.models.base import utc_now
from app.schemas.school import (
    ClassCreate,
    ClassJoinPayload,
    ClassJoinRequestCreate,
    ClassJoinRequestRead,
    ClassJoinRequestReview,
    ClassMemberRead,
    ClassRead,
    MembershipRead,
)
from app.services.audit import record_audit_log
from app.services.class_join_requests import (
    apply_class_join_request_review,
    ensure_class_membership,
    ensure_school_membership,
    existing_active_class_membership,
    normalize_class_role,
    normalize_join_request_status,
    trim_optional,
)
from app.services.access_control import (
    require_class_teacher_or_admin,
    require_school_member,
    require_school_role,
    visible_school_ids,
)
from app.services.text import require_trimmed_text


router = APIRouter()


@router.get("", response_model=list[ClassRead])
def list_classes(
    school_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassGroup]:
    statement = select(ClassGroup).order_by(ClassGroup.id)
    if school_id is not None:
        require_school_member(db, current_user, school_id)
        statement = statement.where(ClassGroup.school_id == school_id)
    elif current_user.role != "admin":
        school_ids = visible_school_ids(db, current_user.id)
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
    require_school_role(db, current_user, payload.school_id, {"admin", "teacher"})
    name = require_trimmed_text(payload.name, "Class name is required")
    existing = db.scalar(
        select(ClassGroup).where(
            ClassGroup.school_id == payload.school_id,
            ClassGroup.name == name,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Class already exists in this school")

    class_group = ClassGroup(
        school_id=payload.school_id,
        name=name,
        grade=(payload.grade or "").strip() or None,
        term=(payload.term or "").strip() or None,
    )
    db.add(class_group)
    db.flush()
    ensure_school_membership(db, payload.school_id, current_user.id, "teacher")
    ensure_class_membership(db, class_group.id, current_user.id, "teacher")
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

    role = normalize_class_role(payload.role)
    if role == "teacher" and current_user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Only teachers can join with teacher role")
    if role == "teacher" and current_user.role != "admin":
        require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})

    ensure_school_membership(db, class_group.school_id, current_user.id, role)
    membership, membership_created = ensure_class_membership(db, class_group.id, current_user.id, role)
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


@router.get("/{class_id}/members", response_model=list[ClassMemberRead])
def list_class_members(
    class_id: int,
    role: str | None = Query(default=None, max_length=32),
    status_filter: str | None = Query(default="active", alias="status", max_length=32),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassMemberRead]:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    require_class_teacher_or_admin(
        db,
        current_user,
        class_group,
        detail="Class members require class teacher scope",
    )

    statement = (
        select(ClassMembership, User)
        .join(User, User.id == ClassMembership.user_id)
        .where(ClassMembership.class_id == class_group.id)
        .order_by(ClassMembership.role, User.username, ClassMembership.id)
    )
    if role is not None:
        statement = statement.where(ClassMembership.role == normalize_class_role(role))
    if status_filter is not None:
        membership_status = status_filter.strip().lower()
        if membership_status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Unsupported class member status")
        statement = statement.where(ClassMembership.status == membership_status)

    rows = db.execute(statement).all()
    return [
        ClassMemberRead(
            id=membership.id,
            class_id=membership.class_id,
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            user_status=user.status,
            role=membership.role,
            status=membership.status,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )
        for membership, user in rows
    ]


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

    role = normalize_class_role(payload.role)
    if role == "teacher" and current_user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Only teachers can request teacher role")
    if role == "teacher" and current_user.role != "admin":
        require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})

    if existing_active_class_membership(db, class_group.id, current_user.id, role) is not None:
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
        join_request.message = trim_optional(payload.message)
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
            message=trim_optional(payload.message),
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
    require_class_teacher_or_admin(
        db,
        current_user,
        class_group,
        detail="Class review scope requires class teacher role",
    )

    statement = (
        select(ClassJoinRequest)
        .where(ClassJoinRequest.class_id == class_group.id)
        .order_by(ClassJoinRequest.id)
    )
    if status_filter is not None:
        statement = statement.where(ClassJoinRequest.status == normalize_join_request_status(status_filter))
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
    require_class_teacher_or_admin(
        db,
        current_user,
        class_group,
        detail="Class review scope requires class teacher role",
    )

    join_request = db.scalar(
        select(ClassJoinRequest).where(
            ClassJoinRequest.id == join_request_id,
            ClassJoinRequest.class_id == class_group.id,
        )
    )
    if join_request is None:
        raise HTTPException(status_code=404, detail="Class join request not found")

    apply_class_join_request_review(
        db,
        join_request=join_request,
        reviewer=current_user,
        request=request,
        next_status=payload.status,
        note=payload.note,
        approval_source="class_review",
    )
    db.commit()
    db.refresh(join_request)
    return join_request
