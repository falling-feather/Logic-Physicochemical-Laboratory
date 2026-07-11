from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AdminAlertOutboxDispatchPlan, AdminAlertOutboxEntry, User
from app.services.alert_delivery import (
    AlertDeliveryAdapter,
    AlertDeliveryError,
    build_alert_delivery_adapter,
    build_alert_delivery_envelope,
)
from app.services.audit import record_audit_log


@dataclass(frozen=True)
class AlertDispatchTaskResult:
    plan_id: int
    plan_status: str
    attempted_count: int
    delivered_count: int
    failed_count: int
    recovered_terminal_plan: bool = False


class AlertDispatchTaskError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def dispatch_alert_plan_from_background_task(
    db: Session,
    *,
    plan_id: int,
    settings: Settings,
    actor: User | None,
    heartbeat: Callable[[], bool] | None = None,
    adapter_factory: Callable[[Settings], AlertDeliveryAdapter] = build_alert_delivery_adapter,
) -> AlertDispatchTaskResult:
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise AlertDispatchTaskError("alert_plan_not_found", retryable=False)
    if plan.plan_status in {"delivered", "partial_failed", "failed"}:
        return AlertDispatchTaskResult(
            plan_id=plan.id,
            plan_status=plan.plan_status,
            attempted_count=0,
            delivered_count=0,
            failed_count=0,
            recovered_terminal_plan=True,
        )
    if plan.plan_status == "dispatching":
        raise AlertDispatchTaskError("alert_plan_ambiguous_dispatch", retryable=False)
    if plan.plan_status != "created":
        raise AlertDispatchTaskError("alert_plan_not_dispatchable", retryable=False)

    try:
        adapter = adapter_factory(settings)
    except AlertDeliveryError as exc:
        raise AlertDispatchTaskError(exc.code, retryable=exc.retryable) from None

    now_at = datetime.now(UTC)
    entry_ids = [int(entry_id) for entry_id in list(plan.ready_entry_ids_json or [])]
    if not entry_ids:
        raise AlertDispatchTaskError("alert_plan_empty", retryable=False)
    if len(entry_ids) > settings.alert_delivery_batch_limit:
        raise AlertDispatchTaskError("alert_plan_batch_limit_exceeded", retryable=False)
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.id.in_(entry_ids))
            .order_by(AdminAlertOutboxEntry.id.asc())
            .with_for_update()
        ).all()
    )
    if [entry.id for entry in entries] != sorted(entry_ids):
        raise AlertDispatchTaskError("alert_plan_entries_changed", retryable=False)
    planned_hashes = {str(key): str(value) for key, value in (plan.ready_entry_payload_hashes_json or {}).items()}
    if any(
        planned_hashes.get(str(entry.id)) != entry.payload_hash or not _entry_dispatch_ready(entry, now_at)
        for entry in entries
    ):
        raise AlertDispatchTaskError("alert_plan_entries_changed", retryable=False)
    if heartbeat is not None and not heartbeat():
        raise AlertDispatchTaskError("background_task_lease_lost", retryable=True)

    plan.plan_status = "dispatching"
    for entry in entries:
        entry.status = "dispatching"
        entry.dispatch_mode = adapter.provider
        entry.delivery_target = adapter.delivery_target
        entry.external_delivery = True
        entry.attempt_count += 1
        entry.last_error_code = None
    db.commit()

    delivered_count = 0
    failed_count = 0
    for entry in entries:
        if heartbeat is not None and not heartbeat():
            raise AlertDispatchTaskError("background_task_lease_lost", retryable=False)
        attempted_at = datetime.now(UTC)
        idempotency_key = sha256(
            f"astra-alert:{entry.id}:{entry.source_type}:{entry.event_code}:{entry.payload_hash}".encode("utf-8")
        ).hexdigest()
        try:
            receipt = adapter.deliver(
                build_alert_delivery_envelope(entry),
                idempotency_key=idempotency_key,
            )
        except AlertDeliveryError as exc:
            entry.status = "failed"
            entry.last_error_code = exc.code
            entry.available_at = (
                attempted_at + timedelta(seconds=settings.alert_delivery_retry_delay_seconds)
                if exc.retryable
                else None
            )
            failed_count += 1
            record_audit_log(
                db,
                actor=actor,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="failure",
                failure_reason=exc.code,
                snapshot={
                    "format": "background_task_alert_dispatch_result",
                    "plan_id": plan.id,
                    "entry_id": entry.id,
                    "status": "failed",
                    "provider": adapter.provider,
                    "delivery_target": adapter.delivery_target,
                    "attempt_count": entry.attempt_count,
                    "retryable": exc.retryable,
                    "payload_hash_prefix": entry.payload_hash[:12],
                },
            )
        else:
            entry.status = "delivered"
            entry.last_error_code = None
            entry.available_at = None
            delivered_count += 1
            record_audit_log(
                db,
                actor=actor,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="success",
                snapshot={
                    "format": "background_task_alert_dispatch_result",
                    "plan_id": plan.id,
                    "entry_id": entry.id,
                    "status": "delivered",
                    "provider": receipt.provider,
                    "delivery_target": adapter.delivery_target,
                    "attempt_count": entry.attempt_count,
                    "http_status": receipt.status_code,
                    "receipt_hash_prefix": receipt.receipt_hash[:12],
                    "payload_hash_prefix": entry.payload_hash[:12],
                },
            )
        db.commit()

    plan.plan_status = (
        "delivered"
        if delivered_count == len(entries)
        else "failed"
        if failed_count == len(entries)
        else "partial_failed"
    )
    record_audit_log(
        db,
        actor=actor,
        action="admin.alert_outbox.external_dispatch_plan",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success" if failed_count == 0 else "failure",
        failure_reason="partial_or_total_delivery_failure" if failed_count else None,
        snapshot={
            "format": "background_task_alert_dispatch_plan",
            "plan_id": plan.id,
            "plan_key": plan.plan_key,
            "plan_status": plan.plan_status,
            "provider": adapter.provider,
            "delivery_target": adapter.delivery_target,
            "attempted_count": len(entries),
            "delivered_count": delivered_count,
            "failed_count": failed_count,
            "automatic_dispatch": True,
            "idempotency_key_sent": True,
            "original_payload_included": False,
        },
    )
    db.commit()
    return AlertDispatchTaskResult(
        plan_id=plan.id,
        plan_status=plan.plan_status,
        attempted_count=len(entries),
        delivered_count=delivered_count,
        failed_count=failed_count,
    )


def _entry_dispatch_ready(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    due = entry.available_at is None or _naive_utc(entry.available_at) <= _naive_utc(now_at)
    expired = entry.expires_at is not None and _naive_utc(entry.expires_at) <= _naive_utc(now_at)
    return (
        entry.status == "queued"
        and due
        and not expired
        and not entry.external_delivery
        and entry.dispatch_mode == "manual_review"
        and entry.delivery_target == "admin_outbox"
    )


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
