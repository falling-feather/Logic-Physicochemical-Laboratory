import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdminAlertOutboxEntry, User


ALERT_OUTBOX_SOURCE_KNOWLEDGE_SNAPSHOT_RUN = "knowledge_snapshot_run_alert"
ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT = "content_script_asset_scan_run_alert"
ALERT_OUTBOX_STATUS_PENDING_REVIEW = "pending_review"
ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW = "manual_review"
ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX = "admin_outbox"


@dataclass(frozen=True)
class AdminAlertOutboxWriteResult:
    generated_at: datetime
    source_type: str
    status: str
    dispatch_mode: str
    delivery_target: str
    external_delivery: bool
    candidate_count: int
    created_count: int
    refreshed_count: int
    skipped_count: int
    entries: list[AdminAlertOutboxEntry]
    filters: dict[str, Any]
    policy: dict[str, Any]


def enqueue_knowledge_snapshot_alert_outbox(
    db: Session,
    *,
    report: Any,
    actor: User | None,
    status: str = ALERT_OUTBOX_STATUS_PENDING_REVIEW,
) -> AdminAlertOutboxWriteResult:
    generated_at = report.generated_at or datetime.now(UTC)
    entries: list[AdminAlertOutboxEntry] = []
    created_count = 0
    refreshed_count = 0
    skipped_count = 0

    for candidate in report.candidates:
        run_key = _text_or_none(getattr(candidate, "run_key", None))
        if run_key is None:
            skipped_count += 1
            continue
        payload = _knowledge_snapshot_candidate_payload(candidate)
        payload_hash = _hash_json(payload)
        dedupe_key = _knowledge_snapshot_candidate_dedupe_key(candidate)
        existing = db.scalar(
            select(AdminAlertOutboxEntry).where(AdminAlertOutboxEntry.dedupe_key == dedupe_key)
        )
        if existing is None:
            entry = AdminAlertOutboxEntry(
                source_type=ALERT_OUTBOX_SOURCE_KNOWLEDGE_SNAPSHOT_RUN,
                source_id=getattr(candidate, "run_id", None),
                source_key=run_key,
                event_code=candidate.code,
                severity=candidate.severity,
                action_hint=candidate.action_hint,
                status=status,
                dispatch_mode=ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
                delivery_target=ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
                external_delivery=False,
                dedupe_key=dedupe_key,
                payload_hash=payload_hash,
                payload_json=payload,
                first_seen_at=generated_at,
                last_seen_at=generated_at,
                available_at=generated_at,
                seen_count=1,
                attempt_count=0,
                created_by_user_id=actor.id if actor is not None else None,
            )
            db.add(entry)
            entries.append(entry)
            created_count += 1
            continue

        existing.severity = candidate.severity
        existing.action_hint = candidate.action_hint
        existing.payload_hash = payload_hash
        existing.payload_json = payload
        existing.last_seen_at = generated_at
        existing.available_at = existing.available_at or generated_at
        existing.seen_count += 1
        if existing.status in {"planned", "queued", ALERT_OUTBOX_STATUS_PENDING_REVIEW}:
            existing.status = status
        entries.append(existing)
        refreshed_count += 1

    return AdminAlertOutboxWriteResult(
        generated_at=generated_at,
        source_type=ALERT_OUTBOX_SOURCE_KNOWLEDGE_SNAPSHOT_RUN,
        status=status,
        dispatch_mode=ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
        delivery_target=ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
        external_delivery=False,
        candidate_count=getattr(report, "candidate_count", len(report.candidates)),
        created_count=created_count,
        refreshed_count=refreshed_count,
        skipped_count=skipped_count,
        entries=entries,
        filters=getattr(report, "filters", {}),
        policy={
            **getattr(report, "policy", {}),
            "external_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
            "delivery_target": ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
        },
    )


def enqueue_content_script_remote_drift_alert_outbox(
    db: Session,
    *,
    report: Any,
    actor: User | None,
    status: str = ALERT_OUTBOX_STATUS_PENDING_REVIEW,
) -> AdminAlertOutboxWriteResult:
    generated_at = report.generated_at or datetime.now(UTC)
    entries: list[AdminAlertOutboxEntry] = []
    created_count = 0
    refreshed_count = 0
    skipped_count = 0

    for candidate in report.candidates:
        run_key = _text_or_none(getattr(candidate, "run_key", None))
        if run_key is None:
            skipped_count += 1
            continue
        payload = _content_script_remote_drift_candidate_payload(candidate)
        payload_hash = _hash_json(payload)
        dedupe_key = _content_script_remote_drift_candidate_dedupe_key(candidate)
        existing = db.scalar(
            select(AdminAlertOutboxEntry).where(AdminAlertOutboxEntry.dedupe_key == dedupe_key)
        )
        if existing is None:
            entry = AdminAlertOutboxEntry(
                source_type=ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT,
                source_id=getattr(candidate, "run_id", None),
                source_key=run_key,
                event_code=candidate.code,
                severity=candidate.severity,
                action_hint=candidate.action_hint,
                status=status,
                dispatch_mode=ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
                delivery_target=ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
                external_delivery=False,
                dedupe_key=dedupe_key,
                payload_hash=payload_hash,
                payload_json=payload,
                first_seen_at=generated_at,
                last_seen_at=generated_at,
                available_at=generated_at,
                seen_count=1,
                attempt_count=0,
                created_by_user_id=actor.id if actor is not None else None,
            )
            db.add(entry)
            entries.append(entry)
            created_count += 1
            continue

        existing.severity = candidate.severity
        existing.action_hint = candidate.action_hint
        existing.payload_hash = payload_hash
        existing.payload_json = payload
        existing.last_seen_at = generated_at
        existing.available_at = existing.available_at or generated_at
        existing.seen_count += 1
        if existing.status in {"planned", "queued", ALERT_OUTBOX_STATUS_PENDING_REVIEW}:
            existing.status = status
        entries.append(existing)
        refreshed_count += 1

    return AdminAlertOutboxWriteResult(
        generated_at=generated_at,
        source_type=ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT,
        status=status,
        dispatch_mode=ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
        delivery_target=ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
        external_delivery=False,
        candidate_count=getattr(report, "candidate_count", len(report.candidates)),
        created_count=created_count,
        refreshed_count=refreshed_count,
        skipped_count=skipped_count,
        entries=entries,
        filters=getattr(report, "filters", {}),
        policy={
            **getattr(report, "policy", {}),
            "external_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
            "delivery_target": ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
        },
    )


def admin_alert_outbox_write_snapshot(result: AdminAlertOutboxWriteResult) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in result.entries:
        by_code[item.event_code] = by_code.get(item.event_code, 0) + 1
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
        by_action[item.action_hint] = by_action.get(item.action_hint, 0) + 1
        by_status[item.status] = by_status.get(item.status, 0) + 1
    return {
        "format": "admin_alert_outbox_write",
        "source_type": result.source_type,
        "status": result.status,
        "dispatch_mode": result.dispatch_mode,
        "delivery_target": result.delivery_target,
        "external_delivery": result.external_delivery,
        "candidate_count": result.candidate_count,
        "created_count": result.created_count,
        "refreshed_count": result.refreshed_count,
        "skipped_count": result.skipped_count,
        "entry_count": len(result.entries),
        "filters": result.filters,
        "policy": result.policy,
        "entry_codes": by_code,
        "entry_severities": by_severity,
        "entry_actions": by_action,
        "entry_statuses": by_status,
    }


def _knowledge_snapshot_candidate_payload(candidate: Any) -> dict[str, Any]:
    return {
        "source": {
            "type": ALERT_OUTBOX_SOURCE_KNOWLEDGE_SNAPSHOT_RUN,
            "candidate_source": candidate.source,
            "run_id": candidate.run_id,
            "run_key": candidate.run_key,
        },
        "event": {
            "code": candidate.code,
            "severity": candidate.severity,
            "action_hint": candidate.action_hint,
        },
        "run": {
            "granularity": candidate.granularity,
            "status": candidate.status,
            "trigger_source": candidate.trigger_source,
            "started_at": _datetime_token(candidate.started_at),
            "finished_at": _datetime_token(candidate.finished_at),
            "scheduler_lease_expires_at": _datetime_token(candidate.scheduler_lease_expires_at),
            "scheduler_heartbeat_at": _datetime_token(candidate.scheduler_heartbeat_at),
            "attempt_count": candidate.attempt_count,
        },
        "decision": {
            "health_flags": list(candidate.health_flags or []),
            "queue_reason": candidate.queue_reason,
            "retryable": candidate.retryable,
            "claimable": candidate.claimable,
            "cancellable": candidate.cancellable,
            "ready": candidate.ready,
        },
        "delivery": {
            "external_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
            "delivery_target": ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
        },
    }


def _content_script_remote_drift_candidate_payload(candidate: Any) -> dict[str, Any]:
    return _strip_none(
        {
            "source": {
                "type": ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT,
                "candidate_source": candidate.source,
                "run_id": candidate.run_id,
                "run_key": candidate.run_key,
            },
            "event": {
                "code": candidate.code,
                "severity": candidate.severity,
                "action_hint": candidate.action_hint,
            },
            "run": {
                "scan_type": candidate.scan_type,
                "trigger_source": candidate.trigger_source,
                "status": candidate.status,
                "alert_status": candidate.alert_status,
                "started_at": _datetime_token(candidate.started_at),
                "finished_at": _datetime_token(candidate.finished_at),
            },
            "asset": {
                "slug": candidate.slug,
                "page_id": candidate.page_id,
                "page_version_id": candidate.page_version_id,
                "sandbox_id": candidate.sandbox_id,
                "reference_key": candidate.reference_key,
                "reference_value_sha256": candidate.reference_value_sha256,
                "source_host": candidate.source_host,
                "source_url_sha256": candidate.source_url_sha256,
                "asset_id": candidate.asset_id,
                "asset_sha256": candidate.asset_sha256,
                "remote_asset_sha256": candidate.remote_asset_sha256,
                "remote_asset_size_bytes": candidate.remote_asset_size_bytes,
                "published_at": _datetime_token(candidate.published_at),
            },
            "delivery": {
                "external_delivery": False,
                "automatic_actions": False,
                "dispatch_mode": ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
                "delivery_target": ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
            },
        }
    )


def _knowledge_snapshot_candidate_dedupe_key(candidate: Any) -> str:
    raw = "|".join(
        [
            ALERT_OUTBOX_SOURCE_KNOWLEDGE_SNAPSHOT_RUN,
            str(candidate.run_key),
            str(candidate.source),
            str(candidate.code),
            str(candidate.action_hint),
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _content_script_remote_drift_candidate_dedupe_key(candidate: Any) -> str:
    raw = "|".join(
        [
            ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT,
            str(candidate.run_key),
            str(candidate.source),
            str(candidate.code),
            str(candidate.action_hint),
            str(candidate.page_id),
            str(candidate.page_version_id),
            str(candidate.sandbox_id),
            str(candidate.reference_value_sha256),
            str(candidate.source_host),
            str(candidate.source_url_sha256),
            str(candidate.asset_sha256),
            str(candidate.remote_asset_sha256),
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _hash_json(payload: dict[str, Any]) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_strip_none(item) for item in value if item is not None]
    return value


def _datetime_token(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
