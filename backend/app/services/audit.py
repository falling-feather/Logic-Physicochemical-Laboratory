from typing import Any

from sqlalchemy.orm import Session

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
    snapshot: dict[str, Any] | None = None,
) -> AuditLog:
    resource_id_value = str(resource_id) if resource_id is not None else None
    resource = f"{resource_type}:{resource_id_value}" if resource_id_value is not None else resource_type
    audit_log = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        actor_role=actor.role if actor is not None else None,
        action=action,
        resource=resource,
        resource_type=resource_type,
        resource_id=resource_id_value,
        school_id=school_id,
        class_id=class_id,
        snapshot_json=snapshot or {},
    )
    db.add(audit_log)
    return audit_log
