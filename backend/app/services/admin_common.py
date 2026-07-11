from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


PENDING_SUBMISSION_STATUSES = ("submitted", "returned")


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def count_rows(db: Session, model: Any, *criteria: Any) -> int:
    statement = select(func.count()).select_from(model)
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(db.scalar(statement) or 0)


def statement_count(db: Session, statement: Any) -> int:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    return int(db.scalar(count_statement) or 0)


def change_snapshot(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = {
        key: {"from": before.get(key), "to": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
    return {"before": before, "after": after, "changes": changes}


def next_offset(total: int, offset: int, item_count: int) -> int | None:
    candidate = offset + item_count
    return candidate if candidate < total else None


def contains_pattern(value: str) -> str:
    escaped = value.replace("~", "~~").replace("%", "~%").replace("_", "~_")
    return f"%{escaped}%"


def naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def oldest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return min(items, key=naive_utc) if items else None


def latest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return max(items, key=naive_utc) if items else None
