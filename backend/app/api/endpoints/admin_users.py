from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.core.security import hash_password, password_strength_errors
from app.db.session import get_db
from app.models import AuthSession, Course, LoginAttempt, User
from app.schemas.admin import (
    AdminBootstrapRequest,
    AdminUserPage,
    AdminUserPasswordReset,
    AdminUserPasswordResetResponse,
    AdminUserRead,
    AdminUserUpdate,
)
from app.services.access_control import deactivate_incompatible_authority_rows
from app.services.admin_common import (
    change_snapshot,
    count_rows,
    next_offset,
    require_admin,
    statement_count,
)
from app.services.audit import record_audit_log
from app.services.security_control_locks import ADMIN_AUTHORITY_LOCK, acquire_security_control_lock
from app.services.text import require_trimmed_text
from app.services.users import find_user_by_normalized_username, require_normalized_username


router = APIRouter()


@router.post("/bootstrap", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: AdminBootstrapRequest, request: Request, db: Session = Depends(get_db)) -> User:
    acquire_security_control_lock(db, ADMIN_AUTHORITY_LOCK)
    if _active_admin_count(db) > 0:
        raise HTTPException(status_code=409, detail="Admin bootstrap is already complete")

    settings = get_settings()
    if not settings.admin_bootstrap_enabled:
        raise HTTPException(status_code=403, detail="Admin bootstrap is disabled")
    if settings.admin_bootstrap_token:
        if payload.bootstrap_token != settings.admin_bootstrap_token:
            raise HTTPException(status_code=403, detail="Invalid admin bootstrap token")
    elif not settings.is_local_development:
        raise HTTPException(status_code=403, detail="Admin bootstrap token is required outside local development")

    username = require_normalized_username(payload.username, min_length=3)
    display_name = require_trimmed_text(payload.display_name, "Display name is required")
    _enforce_password_strength(payload.password, username)
    existing = find_user_by_normalized_username(db, username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        normalized_username=username,
        display_name=display_name,
        role="admin",
        status="active",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    record_audit_log(
        db,
        actor=user,
        action="admin.bootstrap",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot={"after": {"username": user.username, "role": user.role, "status": user.status}},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return user


@router.get("/users", response_model=AdminUserPage)
def list_users(
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUserPage:
    require_admin(current_user)
    statement = select(User).order_by(User.id)
    if role is not None:
        statement = statement.where(User.role == role.strip().lower())
    if status_filter is not None:
        statement = statement.where(User.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
    total = statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminUserPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    require_admin(current_user)
    acquire_security_control_lock(db, ADMIN_AUTHORITY_LOCK)
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    before = _user_snapshot(user)
    next_role = payload.role or user.role
    next_status = payload.status or user.status
    if user.role == "admin" and (next_role != "admin" or next_status != "active"):
        if _active_admin_count(db) <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove the last active admin")
    if next_role == "student" and user.role != "student":
        owned_course_count = count_rows(db, Course, Course.creator_user_id == user.id)
        if owned_course_count:
            raise HTTPException(status_code=409, detail="Transfer owned courses before changing user to student")

    if payload.display_name is not None:
        user.display_name = require_trimmed_text(payload.display_name, "Display name is required")
    if payload.role is not None:
        user.role = payload.role
    if payload.status is not None:
        user.status = payload.status

    after = _user_snapshot(user)
    snapshot = change_snapshot(before, after)
    authority_changed = payload.role is not None and before["role"] != after["role"]
    if authority_changed:
        snapshot["deactivated_authority_rows"] = deactivate_incompatible_authority_rows(db, user)
    revoked_sessions = _revoke_user_sessions(db, user) if authority_changed or payload.status == "disabled" else 0
    if revoked_sessions:
        snapshot["revoked_sessions"] = revoked_sessions
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.update",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot=snapshot,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/password-reset", response_model=AdminUserPasswordResetResponse)
def reset_user_password(
    user_id: int,
    payload: AdminUserPasswordReset,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUserPasswordResetResponse:
    require_admin(current_user)
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    _enforce_password_strength(payload.password, user.username)
    user.password_hash = hash_password(payload.password)
    cleared_login_attempt = _clear_user_login_attempt(db, user)
    revoked_sessions = _revoke_user_sessions(db, user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.password_reset",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot={
            "user": _user_snapshot(user),
            "revoked_sessions": revoked_sessions,
            "cleared_login_attempt": cleared_login_attempt,
        },
    )
    db.commit()
    return AdminUserPasswordResetResponse(
        user_id=user.id,
        revoked_sessions=revoked_sessions,
        cleared_login_attempt=cleared_login_attempt,
    )


def _enforce_password_strength(password: str, username: str) -> None:
    errors = password_strength_errors(password, username=username)
    if errors:
        raise HTTPException(status_code=422, detail={"password": errors})


def _active_admin_count(db: Session) -> int:
    return count_rows(db, User, User.role == "admin", User.status == "active")


def _user_snapshot(user: User) -> dict[str, str]:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


def _revoke_user_sessions(db: Session, user: User) -> int:
    now = datetime.now(UTC)
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    ).all()
    for auth_session in sessions:
        auth_session.revoked_at = now
    return len(sessions)


def _clear_user_login_attempt(db: Session, user: User) -> bool:
    attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.normalized_username == user.normalized_username))
    if attempt is None:
        return False
    db.delete(attempt)
    return True
