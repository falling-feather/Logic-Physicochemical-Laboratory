import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.models.base import utc_now
from app.services.request_metadata import request_metadata


_AUDIT_CHAIN_VERSION = 1
_AUDIT_CHAIN_SESSION_KEY = "audit_chain_tail"


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
    snapshot_json = snapshot or {}
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
    db.add(audit_log)
    return audit_log


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
    with db.no_autoflush:
        return db.scalar(
            select(AuditLog.current_hash)
            .where(AuditLog.current_hash.is_not(None))
            .order_by(AuditLog.id.desc())
            .limit(1)
        )


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
