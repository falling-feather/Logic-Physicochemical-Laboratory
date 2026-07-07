from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ContentScriptAsset, ContentScriptHostPolicy, User
from app.models.base import utc_now
from app.schemas.content import ContentPage
from app.services.content_script_assets import ContentScriptAssetMirrorError, external_script_references


CONTENT_SCRIPT_HOST_POLICY_STATUSES = {"trusted", "watch", "blocked"}


@dataclass(frozen=True)
class ContentScriptHostPolicyRow:
    source_host: str
    status: str
    configured_allowed: bool
    observed_asset_count: int
    observed_page_count: int
    last_observed_at: datetime | None
    policy_id: int | None = None
    reason: str | None = None
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ContentScriptHostPolicyPage:
    total: int
    items: list[ContentScriptHostPolicyRow]


def normalize_content_script_source_host(source_host: str) -> str:
    normalized = source_host.strip().lower().rstrip(".")
    if not normalized or len(normalized) > 255:
        raise ValueError("source_host must be 1-255 characters")
    if any(char in normalized for char in "/\\?#@:") or normalized != normalized.strip():
        raise ValueError("source_host must be a bare hostname")
    if any(part in {"", ".", ".."} for part in normalized.split(".")):
        raise ValueError("source_host must be a valid hostname")
    return normalized


def list_content_script_host_policy_rows(
    db: Session,
    *,
    allowed_hosts: list[str] | set[str],
    source_host: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ContentScriptHostPolicyPage:
    normalized_allowed_hosts = {host.strip().lower() for host in allowed_hosts if host.strip()}
    normalized_source_host = normalize_content_script_source_host(source_host) if source_host else None
    normalized_status = status.strip().lower() if status is not None and status.strip() else None
    if normalized_status is not None and normalized_status not in CONTENT_SCRIPT_HOST_POLICY_STATUSES | {"unreviewed"}:
        raise ValueError("Invalid content script host policy status")
    normalized_q = q.strip().lower() if q is not None and q.strip() else None

    policies = {
        policy.source_host: policy
        for policy in db.scalars(select(ContentScriptHostPolicy).order_by(ContentScriptHostPolicy.source_host)).all()
    }
    observed_stats = _content_script_host_observed_stats(db)
    hosts = sorted(set(policies) | set(observed_stats) | normalized_allowed_hosts)
    rows: list[ContentScriptHostPolicyRow] = []
    for host in hosts:
        if normalized_source_host is not None and host != normalized_source_host:
            continue
        policy = policies.get(host)
        row_status = policy.status if policy is not None else "unreviewed"
        if normalized_status is not None and row_status != normalized_status:
            continue
        if normalized_q is not None and normalized_q not in host and (
            policy is None or policy.reason is None or normalized_q not in policy.reason.lower()
        ):
            continue
        rows.append(
            _content_script_host_policy_row(
                host,
                policy=policy,
                observed=observed_stats.get(host),
                configured_allowed=host in normalized_allowed_hosts,
            )
        )
    return ContentScriptHostPolicyPage(total=len(rows), items=rows[offset : offset + limit])


def upsert_content_script_host_policy(
    db: Session,
    *,
    source_host: str,
    status: str,
    reason: str | None,
    reviewer: User,
) -> ContentScriptHostPolicy:
    normalized_host = normalize_content_script_source_host(source_host)
    normalized_status = status.strip().lower()
    if normalized_status not in CONTENT_SCRIPT_HOST_POLICY_STATUSES:
        raise ValueError("Invalid content script host policy status")
    policy = db.scalar(select(ContentScriptHostPolicy).where(ContentScriptHostPolicy.source_host == normalized_host))
    reviewed_at = utc_now()
    if policy is None:
        policy = ContentScriptHostPolicy(
            source_host=normalized_host,
            status=normalized_status,
            reason=_strip_optional(reason),
            reviewed_by_user_id=reviewer.id,
            reviewed_at=reviewed_at,
        )
        db.add(policy)
    else:
        policy.status = normalized_status
        policy.reason = _strip_optional(reason)
        policy.reviewed_by_user_id = reviewer.id
        policy.reviewed_at = reviewed_at
    return policy


def blocked_content_script_host_policies(
    db: Session,
    page_schema: ContentPage | dict[str, Any],
) -> list[ContentScriptHostPolicy]:
    try:
        hosts = {reference.source_host for reference in external_script_references(page_schema)}
    except ContentScriptAssetMirrorError:
        return []
    if not hosts:
        return []
    return list(
        db.scalars(
            select(ContentScriptHostPolicy)
            .where(
                ContentScriptHostPolicy.source_host.in_(hosts),
                ContentScriptHostPolicy.status == "blocked",
            )
            .order_by(ContentScriptHostPolicy.source_host)
        ).all()
    )


def content_script_host_policy_snapshot(policy: ContentScriptHostPolicy) -> dict[str, Any]:
    return {
        "source_host": policy.source_host,
        "status": policy.status,
        "reason": policy.reason,
        "reviewed_by_user_id": policy.reviewed_by_user_id,
        "reviewed_at": policy.reviewed_at.isoformat(),
    }


def _content_script_host_observed_stats(db: Session) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        select(
            ContentScriptAsset.source_host,
            func.count(ContentScriptAsset.id),
            func.count(func.distinct(ContentScriptAsset.slug)),
            func.max(ContentScriptAsset.published_at),
        ).group_by(ContentScriptAsset.source_host)
    ).all()
    return {
        str(source_host): {
            "asset_count": int(asset_count or 0),
            "page_count": int(page_count or 0),
            "last_observed_at": last_observed_at,
        }
        for source_host, asset_count, page_count, last_observed_at in rows
    }


def _content_script_host_policy_row(
    source_host: str,
    *,
    policy: ContentScriptHostPolicy | None,
    observed: dict[str, Any] | None,
    configured_allowed: bool,
) -> ContentScriptHostPolicyRow:
    return ContentScriptHostPolicyRow(
        policy_id=policy.id if policy is not None else None,
        source_host=source_host,
        status=policy.status if policy is not None else "unreviewed",
        reason=policy.reason if policy is not None else None,
        configured_allowed=configured_allowed,
        observed_asset_count=int((observed or {}).get("asset_count") or 0),
        observed_page_count=int((observed or {}).get("page_count") or 0),
        last_observed_at=(observed or {}).get("last_observed_at"),
        reviewed_by_user_id=policy.reviewed_by_user_id if policy is not None else None,
        reviewed_at=policy.reviewed_at if policy is not None else None,
        created_at=policy.created_at if policy is not None else None,
        updated_at=policy.updated_at if policy is not None else None,
    )


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
