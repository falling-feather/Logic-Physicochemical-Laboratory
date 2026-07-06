from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.services.request_metadata import request_metadata


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
