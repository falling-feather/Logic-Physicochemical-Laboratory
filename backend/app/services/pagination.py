from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy.orm import Session


LEGACY_LIST_MAX_ITEMS = 200
LEGACY_LIST_PROBE_ITEMS = LEGACY_LIST_MAX_ITEMS + 1


def paged_endpoint_url(path: str, **filters: Any) -> str:
    query = urlencode([(key, value) for key, value in filters.items() if value is not None])
    return f"{path}?{query}" if query else path


def list_legacy_scalars(
    db: Session,
    statement: Any,
    *,
    paged_endpoint: str,
) -> list[Any]:
    items = list(db.scalars(statement.limit(LEGACY_LIST_PROBE_ITEMS)).all())
    return _require_legacy_list_within_limit(items, paged_endpoint=paged_endpoint)


def list_legacy_rows(
    db: Session,
    statement: Any,
    *,
    paged_endpoint: str,
) -> list[Any]:
    items = list(db.execute(statement.limit(LEGACY_LIST_PROBE_ITEMS)).all())
    return _require_legacy_list_within_limit(items, paged_endpoint=paged_endpoint)


def _require_legacy_list_within_limit(items: list[Any], *, paged_endpoint: str) -> list[Any]:
    if len(items) > LEGACY_LIST_MAX_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "legacy_list_limit_exceeded",
                "message": "This deprecated array response exceeds its compatibility limit; use the paged endpoint.",
                "max_items": LEGACY_LIST_MAX_ITEMS,
                "paged_endpoint": paged_endpoint,
            },
        )
    return items
