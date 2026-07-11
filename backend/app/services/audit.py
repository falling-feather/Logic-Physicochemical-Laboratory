import hashlib
import json
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from fastapi import Request
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import AuditChainHead, AuditLog, User
from app.models.base import utc_now
from app.services.request_metadata import request_metadata


_AUDIT_CHAIN_VERSION = 1
_AUDIT_CHAIN_SESSION_KEY = "audit_chain_tail"
_AUDIT_CHAIN_HEAD_SESSION_KEY = "audit_chain_head"
_AUDIT_SQLITE_LOCK_SESSION_KEY = "audit_sqlite_chain_lock"
_AUDIT_SQLITE_CHAIN_LOCK = Lock()
_AUDIT_REDACTION = {"redacted": True, "reason": "audit_snapshot_policy"}
_SENSITIVE_AUDIT_FIELD_NAMES = {
    "authorization",
    "bootstrap_token",
    "change_request_note",
    "content_bytes",
    "cookie",
    "dedupe_key",
    "error_message",
    "evidence",
    "exception",
    "external_issue_url",
    "feedback",
    "integrity",
    "metadata_json",
    "notes",
    "password",
    "password_hash",
    "payload_hash",
    "payload_json",
    "raw",
    "raw_content",
    "reset_token",
    "review_note",
    "scheduler_lease_owner",
    "scheduler_lease_token",
    "script_integrity",
    "script_review_note",
    "script_src",
    "script_url",
    "scriptsrc",
    "scripturl",
    "secret",
    "session_token",
    "source_url",
    "token",
    "token_hash",
    "value_preview",
}
_SENSITIVE_AUDIT_FIELD_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
    "_token_hash",
)
_SENSITIVE_AUDIT_FIELD_PREFIXES = (
    "password_",
    "secret_",
    "token_",
)
_SENSITIVE_AUDIT_VALUE_MARKERS = (
    "password=",
    "passwd=",
    "pwd=",
    "token=",
    "secret=",
    "api_key=",
    "apikey=",
    "authorization:",
    "bearer ",
    "set-cookie",
    "cookie:",
    "session=",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
)


def record_audit_log(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: int | str | None = None,
    actor: User | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    event_result: str | None = None,
    failure_reason: str | None = None,
    request: Request | None = None,
    snapshot: dict[str, Any] | None = None,
) -> AuditLog:
    resource_id_value = str(resource_id) if resource_id is not None else None
    resource = f"{resource_type}:{resource_id_value}" if resource_id_value is not None else resource_type
    metadata = request_metadata(request)
    timestamp = utc_now()
    if db.get_bind().dialect.name == "mysql":
        # MySQL DATETIME defaults to second precision. Hash the value that can
        # actually be persisted so a later chain verification is stable.
        timestamp = timestamp.replace(microsecond=0)
    snapshot_json = redact_audit_snapshot(snapshot)
    previous_hash = _previous_hash(db)
    audit_log = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        actor_role=actor.role if actor is not None else None,
        action=action,
        resource=resource,
        resource_type=resource_type,
        resource_id=resource_id_value,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=metadata["request_id"],
        client_ip_hash=metadata["client_ip_hash"],
        user_agent=metadata["user_agent"],
        request_method=metadata["request_method"],
        request_path=metadata["request_path"],
        prev_hash=previous_hash,
        created_at=timestamp,
        updated_at=timestamp,
        snapshot_json=snapshot_json,
    )
    audit_log.current_hash = audit_log_chain_hash(audit_log)
    db.info[_AUDIT_CHAIN_SESSION_KEY] = audit_log.current_hash
    chain_head = db.info.get(_AUDIT_CHAIN_HEAD_SESSION_KEY)
    if isinstance(chain_head, AuditChainHead):
        chain_head.current_hash = audit_log.current_hash
        chain_head.current_audit_log_id = None
    db.add(audit_log)
    db.flush([audit_log])
    if isinstance(chain_head, AuditChainHead):
        chain_head.current_audit_log_id = audit_log.id
    return audit_log


def redact_audit_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {}
    redacted = _redact_audit_value(snapshot)
    return redacted if isinstance(redacted, dict) else {"value": redacted}


def _redact_audit_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: dict(_AUDIT_REDACTION) if _audit_field_is_sensitive(str(key)) else _redact_audit_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_audit_value(item) for item in value]
    if isinstance(value, str) and _audit_value_is_sensitive(value):
        return dict(_AUDIT_REDACTION)
    return value


def _audit_field_is_sensitive(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in _SENSITIVE_AUDIT_FIELD_NAMES:
        return True
    if normalized.startswith(_SENSITIVE_AUDIT_FIELD_PREFIXES):
        return True
    return normalized.endswith(_SENSITIVE_AUDIT_FIELD_SUFFIXES)


def _audit_value_is_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_AUDIT_VALUE_MARKERS)


def audit_log_chain_hash(audit_log: AuditLog) -> str:
    payload = {
        "version": _AUDIT_CHAIN_VERSION,
        "algorithm": "sha256",
        "prev_hash": audit_log.prev_hash,
        "actor_user_id": audit_log.actor_user_id,
        "actor_role": audit_log.actor_role,
        "action": audit_log.action,
        "resource": audit_log.resource,
        "resource_type": audit_log.resource_type,
        "resource_id": audit_log.resource_id,
        "school_id": audit_log.school_id,
        "class_id": audit_log.class_id,
        "event_result": audit_log.event_result,
        "failure_reason": audit_log.failure_reason,
        "request_id": audit_log.request_id,
        "client_ip_hash": audit_log.client_ip_hash,
        "user_agent": audit_log.user_agent,
        "request_method": audit_log.request_method,
        "request_path": audit_log.request_path,
        "snapshot_json": audit_log.snapshot_json or {},
        "created_at": _datetime_token(audit_log.created_at),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _previous_hash(db: Session) -> str | None:
    in_session_hash = db.info.get(_AUDIT_CHAIN_SESSION_KEY)
    if isinstance(in_session_hash, str):
        return in_session_hash
    if db.get_bind().dialect.name == "sqlite" and not db.info.get(_AUDIT_SQLITE_LOCK_SESSION_KEY):
        _AUDIT_SQLITE_CHAIN_LOCK.acquire()
        db.info[_AUDIT_SQLITE_LOCK_SESSION_KEY] = True
    with db.no_autoflush:
        head = db.scalar(
            select(AuditChainHead)
            .where(AuditChainHead.id == 1)
            .with_for_update()
        )
        latest = db.execute(
            select(AuditLog.id, AuditLog.current_hash)
            .where(AuditLog.current_hash.is_not(None))
            .order_by(AuditLog.id.desc())
            .limit(1)
            .with_for_update()
        ).first()
        latest_id = int(latest.id) if latest is not None else None
        latest_hash = str(latest.current_hash) if latest is not None else None
        if head is None:
            head = AuditChainHead(
                id=1,
                current_audit_log_id=latest_id,
                current_hash=latest_hash,
            )
            db.add(head)
            db.flush()
        elif head.current_audit_log_id != latest_id or head.current_hash != latest_hash:
            head.current_audit_log_id = latest_id
            head.current_hash = latest_hash
        db.info[_AUDIT_CHAIN_HEAD_SESSION_KEY] = head
        return latest_hash


def _datetime_token(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


@event.listens_for(Session, "after_transaction_end")
def _clear_audit_chain_tail(session: Session, transaction: Any) -> None:
    if transaction.parent is None:
        session.info.pop(_AUDIT_CHAIN_SESSION_KEY, None)
        session.info.pop(_AUDIT_CHAIN_HEAD_SESSION_KEY, None)
        if session.info.pop(_AUDIT_SQLITE_LOCK_SESSION_KEY, False):
            _AUDIT_SQLITE_CHAIN_LOCK.release()
