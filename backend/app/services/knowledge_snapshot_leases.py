from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


KNOWLEDGE_SNAPSHOT_LEASE_FIELDS = (
    "scheduler_lease_owner",
    "scheduler_lease_token",
    "scheduler_lease_expires_at",
    "scheduler_heartbeat_at",
)


def knowledge_snapshot_lease_missing_fields(run: Any) -> list[str]:
    return [field for field in KNOWLEDGE_SNAPSHOT_LEASE_FIELDS if not getattr(run, field, None)]


def knowledge_snapshot_lease_has_any_field(run: Any) -> bool:
    return any(getattr(run, field, None) for field in KNOWLEDGE_SNAPSHOT_LEASE_FIELDS)


def knowledge_snapshot_lease_is_complete(run: Any) -> bool:
    return not knowledge_snapshot_lease_missing_fields(run)


def knowledge_snapshot_lease_is_expired(run: Any, now: datetime, lease_seconds: int) -> bool:
    now_value = _as_naive_utc(now)
    expires_at = getattr(run, "scheduler_lease_expires_at", None)
    if expires_at is not None:
        return _as_naive_utc(expires_at) <= now_value
    started_at = getattr(run, "started_at", None)
    if started_at is None:
        return True
    return _as_naive_utc(started_at) <= now_value - timedelta(seconds=lease_seconds)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
