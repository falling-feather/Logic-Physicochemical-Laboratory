from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import PasswordResetToken


def cleanup_password_reset_tokens(
    *,
    database_url: str | None = None,
    retention_days: int | None = None,
    before_at: datetime | None = None,
    limit: int = 5000,
    apply: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    if before_at is not None and retention_days is not None:
        raise ValueError("before_at and retention_days are mutually exclusive")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if retention_days is not None and retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    settings = get_settings()
    now = _ensure_utc(generated_at) if generated_at is not None else _utc_now()
    if before_at is not None and _ensure_utc(before_at) > now:
        raise ValueError("before_at cannot be in the future")
    cutoff_at, cutoff_source, effective_retention_days = _resolve_cutoff(
        before_at=before_at,
        retention_days=retention_days,
        configured_retention_days=settings.password_reset_token_retention_days,
        generated_at=now,
    )

    session_factory = get_session_factory(database_url or settings.database_url)
    with session_factory() as db:
        return _cleanup_password_reset_tokens_in_session(
            db,
            cutoff_at=cutoff_at,
            cutoff_source=cutoff_source,
            retention_days=effective_retention_days,
            limit=limit,
            apply=apply,
            generated_at=now,
        )


def _cleanup_password_reset_tokens_in_session(
    db: Session,
    *,
    cutoff_at: datetime,
    cutoff_source: str,
    retention_days: int | None,
    limit: int,
    apply: bool,
    generated_at: datetime,
) -> dict[str, Any]:
    statement = _eligible_password_reset_tokens_statement(cutoff_at)
    total_candidates = int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
    tokens = list(db.scalars(statement.limit(limit)).all())
    selected = [_selected_token_summary(token) for token in tokens]

    deleted_count = 0
    if apply:
        for token in tokens:
            db.delete(token)
        db.commit()
        deleted_count = len(tokens)

    return _cleanup_report(
        generated_at=generated_at,
        cutoff_at=cutoff_at,
        cutoff_source=cutoff_source,
        retention_days=retention_days,
        limit=limit,
        total_candidates=total_candidates,
        selected=selected,
        deleted_count=deleted_count,
        apply=apply,
    )


def _eligible_password_reset_tokens_statement(cutoff_at: datetime):
    cutoff = _ensure_utc(cutoff_at)
    return (
        select(PasswordResetToken)
        .where(
            or_(
                PasswordResetToken.used_at <= cutoff,
                and_(
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at <= cutoff,
                ),
            )
        )
        .order_by(PasswordResetToken.id.asc())
    )


def _cleanup_report(
    *,
    generated_at: datetime,
    cutoff_at: datetime,
    cutoff_source: str,
    retention_days: int | None,
    limit: int,
    total_candidates: int,
    selected: list[dict[str, Any]],
    deleted_count: int,
    apply: bool,
) -> dict[str, Any]:
    terminal_times = [item["terminal_at"] for item in selected]
    status_counts = {
        "used": sum(1 for item in selected if item["status"] == "used"),
        "expired": sum(1 for item in selected if item["status"] == "expired"),
    }
    return {
        "ok": True,
        "status": "deleted" if apply else "dry_run",
        "generated_at": generated_at.isoformat(),
        "capabilities": {
            "delete": apply,
            "purge": False,
            "external_anchor": False,
        },
        "policy": {
            "source": cutoff_source,
            "retention_days": retention_days,
            "cutoff_at": cutoff_at.isoformat(),
        },
        "limit": limit,
        "total_candidates": total_candidates,
        "selected_count": len(selected),
        "deleted_count": deleted_count,
        "selected_by_status": status_counts,
        "candidate_basis": "used_at <= cutoff_at OR (used_at IS NULL AND expires_at <= cutoff_at)",
        "sensitive_fields_returned": False,
        "truncated": total_candidates > len(selected),
        "first_id": selected[0]["id"] if selected else None,
        "last_id": selected[-1]["id"] if selected else None,
        "oldest_terminal_at": min(terminal_times).isoformat() if terminal_times else None,
        "newest_terminal_at": max(terminal_times).isoformat() if terminal_times else None,
    }


def _selected_token_summary(token: PasswordResetToken) -> dict[str, Any]:
    return {
        "id": token.id,
        "terminal_at": _terminal_at(token),
        "status": "used" if token.used_at is not None else "expired",
    }


def _terminal_at(token: PasswordResetToken) -> datetime:
    if token.used_at is not None:
        return _ensure_utc(token.used_at)
    return _ensure_utc(token.expires_at)


def _resolve_cutoff(
    *,
    before_at: datetime | None,
    retention_days: int | None,
    configured_retention_days: int,
    generated_at: datetime,
) -> tuple[datetime, str, int | None]:
    if before_at is not None:
        return _ensure_utc(before_at), "before", None
    days = retention_days or configured_retention_days
    source = "query" if retention_days is not None else "config"
    return generated_at - timedelta(days=days), source, days


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
