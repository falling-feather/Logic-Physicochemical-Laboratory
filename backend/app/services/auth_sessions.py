from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuthSession


def cleanup_expired_auth_sessions(
    *,
    database_url: str | None = None,
    before_at: datetime | None = None,
    limit: int = 5000,
    apply: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    settings = get_settings()
    now = _ensure_utc(generated_at) if generated_at is not None else _utc_now()
    cutoff_at = _ensure_utc(before_at) if before_at is not None else now
    if cutoff_at > now:
        raise ValueError("before_at cannot be in the future")

    session_factory = get_session_factory(database_url or settings.database_url)
    with session_factory() as db:
        return cleanup_expired_auth_sessions_in_session(
            db,
            cutoff_at=cutoff_at,
            cutoff_source="before" if before_at is not None else "generated_at",
            limit=limit,
            apply=apply,
            generated_at=now,
        )


def cleanup_expired_auth_sessions_in_session(
    db: Session,
    *,
    cutoff_at: datetime,
    cutoff_source: str,
    limit: int,
    apply: bool,
    generated_at: datetime,
) -> dict[str, Any]:
    statement = eligible_expired_auth_sessions_statement(cutoff_at)
    total_candidates = int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    auth_sessions = list(db.scalars(statement.limit(limit)).all())
    selected = [_selected_session_summary(auth_session) for auth_session in auth_sessions]

    revoked_count = 0
    if apply:
        for auth_session in auth_sessions:
            auth_session.revoked_at = generated_at
        db.commit()
        revoked_count = len(auth_sessions)

    return _cleanup_report(
        generated_at=generated_at,
        cutoff_at=cutoff_at,
        cutoff_source=cutoff_source,
        limit=limit,
        total_candidates=total_candidates,
        selected=selected,
        revoked_count=revoked_count,
        apply=apply,
    )


def eligible_expired_auth_sessions_statement(cutoff_at: datetime):
    cutoff = _ensure_utc(cutoff_at)
    return (
        select(AuthSession)
        .where(
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at <= cutoff,
        )
        .order_by(AuthSession.id.asc())
    )


def _cleanup_report(
    *,
    generated_at: datetime,
    cutoff_at: datetime,
    cutoff_source: str,
    limit: int,
    total_candidates: int,
    selected: list[dict[str, Any]],
    revoked_count: int,
    apply: bool,
) -> dict[str, Any]:
    expires_times = [item["expires_at"] for item in selected]
    return {
        "ok": True,
        "status": "revoked" if apply else "dry_run",
        "generated_at": generated_at.isoformat(),
        "capabilities": {
            "revoke": apply,
            "delete": False,
            "external_anchor": False,
        },
        "policy": {
            "source": cutoff_source,
            "cutoff_at": cutoff_at.isoformat(),
        },
        "limit": limit,
        "total_candidates": total_candidates,
        "selected_count": len(selected),
        "revoked_count": revoked_count,
        "selected_by_status": {
            "expired_unrevoked": len(selected),
        },
        "candidate_basis": "revoked_at IS NULL AND expires_at <= cutoff_at",
        "sensitive_fields_returned": False,
        "truncated": total_candidates > len(selected),
        "first_id": selected[0]["id"] if selected else None,
        "last_id": selected[-1]["id"] if selected else None,
        "oldest_expires_at": min(expires_times).isoformat() if expires_times else None,
        "newest_expires_at": max(expires_times).isoformat() if expires_times else None,
    }


def _selected_session_summary(auth_session: AuthSession) -> dict[str, Any]:
    return {
        "id": auth_session.id,
        "expires_at": _ensure_utc(auth_session.expires_at),
        "status": "expired_unrevoked",
    }


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
