from datetime import UTC, datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.core.security import create_session_token, hash_password, hash_token, password_strength_errors, verify_password
from app.db.session import get_db
from app.models import AuthSession, LoginAttempt, User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserPublic
from app.services.audit import record_audit_log
from app.services.text import require_trimmed_text
from app.services.users import find_user_by_normalized_username, require_normalized_username


router = APIRouter()
REGISTER_ROLES = {"teacher", "student"}


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    username = require_normalized_username(payload.username, min_length=3)
    display_name = require_trimmed_text(payload.display_name, "Display name is required")
    role = payload.role.strip().lower()
    if role not in REGISTER_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported registration role")
    _enforce_password_strength(payload.password, username)
    existing = find_user_by_normalized_username(db, username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        normalized_username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    username = require_normalized_username(payload.username)

    settings = get_settings()
    now = datetime.now(UTC)
    attempt = _get_login_attempt(db, username)
    _reset_expired_lockout(attempt, now)
    if _is_login_locked(attempt, now):
        retry_after = _retry_after_seconds(attempt, now)
        _record_login_locked(db, request, username, attempt, retry_after)
        db.commit()
        _raise_login_locked(retry_after)

    user = find_user_by_normalized_username(db, username)
    if user is None or not verify_password(payload.password, user.password_hash):
        locked = _record_failed_login(db, attempt, now, settings.login_max_attempts, settings.login_lockout_seconds)
        retry_after = _retry_after_seconds(attempt, now) if locked else None
        if locked:
            _record_login_locked(db, request, username, attempt, retry_after or 1)
        else:
            _record_login_failure(db, request, username, attempt)
        db.commit()
        if locked:
            _raise_login_locked(retry_after or 1)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if user.status != "active":
        record_audit_log(
            db,
            actor=None,
            action="auth.login.failed",
            resource_type="user",
            resource_id=user.id,
            event_result="failure",
            failure_reason="user_disabled",
            request=request,
            snapshot={"username": user.username, "status": user.status},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")

    token = create_session_token()
    _clear_login_attempt(attempt)
    _revoke_expired_sessions(db, now)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=settings.session_days),
    )
    db.add(auth_session)
    record_audit_log(
        db,
        actor=user,
        action="auth.login.success",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot={"username": user.username, "role": user.role},
    )
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment.lower() in {"production", "prod"},
    )
    return LoginResponse(user=UserPublic.model_validate(user), access_token=token)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    auth_sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == current_user.id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()
    now = datetime.now(UTC)
    for auth_session in auth_sessions:
        auth_session.revoked_at = now
    record_audit_log(
        db,
        actor=current_user,
        action="auth.logout",
        resource_type="user",
        resource_id=current_user.id,
        event_result="success",
        request=request,
        snapshot={"revoked_sessions": len(auth_sessions)},
    )
    db.commit()
    response.delete_cookie(settings.session_cookie_name)
    return {"status": "ok"}


def _enforce_password_strength(password: str, username: str) -> None:
    errors = password_strength_errors(password, username=username)
    if errors:
        raise HTTPException(status_code=422, detail={"password": errors})


def _get_login_attempt(db: Session, username: str) -> LoginAttempt:
    attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.normalized_username == username))
    if attempt is None:
        attempt = LoginAttempt(username=username, normalized_username=username, failure_count=0)
        db.add(attempt)
    return attempt


def _record_failed_login(
    db: Session,
    attempt: LoginAttempt,
    now: datetime,
    max_attempts: int,
    lockout_seconds: int,
) -> bool:
    window_seconds = max(1, get_settings().login_attempt_window_seconds)
    if attempt.last_failed_at is None or _as_utc(attempt.last_failed_at) <= now - timedelta(seconds=window_seconds):
        attempt.failure_count = 0
    attempt.failure_count += 1
    attempt.last_failed_at = now
    if attempt.failure_count >= max(1, max_attempts):
        attempt.locked_until = now + timedelta(seconds=max(1, lockout_seconds))
        db.flush()
        return True
    db.flush()
    return False


def _clear_login_attempt(attempt: LoginAttempt) -> None:
    attempt.failure_count = 0
    attempt.locked_until = None
    attempt.last_failed_at = None


def _reset_expired_lockout(attempt: LoginAttempt, now: datetime) -> None:
    if attempt.locked_until is not None and _as_utc(attempt.locked_until) <= now:
        _clear_login_attempt(attempt)


def _is_login_locked(attempt: LoginAttempt, now: datetime) -> bool:
    return attempt.locked_until is not None and _as_utc(attempt.locked_until) > now


def _retry_after_seconds(attempt: LoginAttempt, now: datetime) -> int:
    locked_until = _as_utc(attempt.locked_until) if attempt.locked_until else now
    return max(1, ceil((locked_until - now).total_seconds()))


def _raise_login_locked(retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed login attempts",
        headers={"Retry-After": str(retry_after)},
    )


def _record_login_failure(db: Session, request: Request, username: str, attempt: LoginAttempt) -> None:
    record_audit_log(
        db,
        actor=None,
        action="auth.login.failed",
        resource_type="auth_login",
        resource_id=username,
        event_result="failure",
        failure_reason="invalid_credentials",
        request=request,
        snapshot={"username": username, "failure_count": attempt.failure_count},
    )


def _record_login_locked(
    db: Session,
    request: Request,
    username: str,
    attempt: LoginAttempt,
    retry_after: int,
) -> None:
    record_audit_log(
        db,
        actor=None,
        action="auth.login.locked",
        resource_type="auth_login",
        resource_id=username,
        event_result="blocked",
        failure_reason="account_locked",
        request=request,
        snapshot={
            "username": username,
            "failure_count": attempt.failure_count,
            "retry_after": retry_after,
        },
    )


def _revoke_expired_sessions(db: Session, now: datetime) -> None:
    expired_sessions = db.scalars(
        select(AuthSession).where(AuthSession.revoked_at.is_(None), AuthSession.expires_at <= now)
    ).all()
    for auth_session in expired_sessions:
        auth_session.revoked_at = now


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
