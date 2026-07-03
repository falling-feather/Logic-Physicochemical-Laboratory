from hashlib import sha256
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, User


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
    metadata = _request_metadata(request)
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
        snapshot_json=snapshot or {},
    )
    db.add(audit_log)
    return audit_log


def _request_metadata(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {
            "request_id": None,
            "client_ip_hash": None,
            "user_agent": None,
            "request_method": None,
            "request_path": None,
        }
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    user_agent = _trim(request.headers.get("user-agent"), 240)
    return {
        "request_id": _trim(request_id, 64),
        "client_ip_hash": _hash_client_ip(_client_ip(request)),
        "user_agent": user_agent,
        "request_method": _trim(request.method.upper(), 12),
        "request_path": _trim(str(request.url.path), 240),
    }


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",", 1)[0].strip()
        if first_ip:
            return first_ip
    if request.client is None:
        return None
    return request.client.host


def _hash_client_ip(client_ip: str | None) -> str | None:
    if not client_ip:
        return None
    salt = get_settings().audit_ip_hash_salt
    return sha256(f"{salt}:{client_ip}".encode("utf-8")).hexdigest()


def _trim(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:max_length]
