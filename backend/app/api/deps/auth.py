from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.models import AuthSession, User
from app.services.request_metadata import request_client_ip_hash


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


def get_current_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = _read_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_digest = hash_token(token)
    now = datetime.now(UTC)
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_digest,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    user = db.get(User, auth_session.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    _touch_auth_session(db, auth_session, request, now)
    db.refresh(user)
    return AuthContext(user=user, session=auth_session)


def get_current_user(context: AuthContext = Depends(get_current_auth_context)) -> User:
    return context.user


def _read_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.cookies.get(get_settings().session_cookie_name)


def _touch_auth_session(db: Session, auth_session: AuthSession, request: Request, now: datetime) -> bool:
    client_ip_hash = request_client_ip_hash(request)
    if not _should_update_last_seen(auth_session, now, client_ip_hash):
        return False
    auth_session.last_seen_at = now
    auth_session.last_seen_ip_hash = client_ip_hash
    db.commit()
    db.refresh(auth_session)
    return True


def _should_update_last_seen(auth_session: AuthSession, now: datetime, client_ip_hash: str | None) -> bool:
    if auth_session.last_seen_at is None:
        return True
    if auth_session.last_seen_ip_hash != client_ip_hash:
        return True
    throttle_seconds = get_settings().session_last_seen_update_seconds
    if throttle_seconds <= 0:
        return True
    return _as_utc(auth_session.last_seen_at) <= now - timedelta(seconds=throttle_seconds)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
