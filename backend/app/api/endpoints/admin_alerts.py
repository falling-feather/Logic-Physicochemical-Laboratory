from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.endpoints.admin_presenters import admin_alert_outbox_entry_read
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AdminAlertOutboxDispatchPlan, AdminAlertOutboxEntry, User
from app.schemas.admin import (
    AdminAlertOutboxBulkReviewRequest,
    AdminAlertOutboxBulkReviewResponse,
    AdminAlertOutboxDispatchDryRunItem,
    AdminAlertOutboxDispatchDryRunReport,
    AdminAlertOutboxDispatchDryRunRequest,
    AdminAlertOutboxDispatchPlanCreateRequest,
    AdminAlertOutboxDispatchPlanPage,
    AdminAlertOutboxDispatchPlanRead,
    AdminAlertOutboxDispatchPlanValidateRequest,
    AdminAlertOutboxDispatchPlanValidationReport,
    AdminAlertOutboxEntryRead,
    AdminAlertOutboxExternalDispatchItem,
    AdminAlertOutboxExternalDispatchReport,
    AdminAlertOutboxExternalDispatchRequest,
    AdminAlertOutboxPage,
    AdminAlertOutboxQueueItem,
    AdminAlertOutboxQueueReport,
    AdminAlertOutboxReviewRequest,
    AdminAlertOutboxStatusBucket,
)
from app.services.admin_common import (
    latest_datetime as _latest_datetime,
    naive_utc,
    next_offset,
    oldest_datetime as _oldest_datetime,
    require_admin,
    statement_count,
)
from app.services.alert_delivery import (
    AlertDeliveryError,
    alert_delivery_posture,
    build_alert_delivery_adapter,
    build_alert_delivery_envelope,
)
from app.services.audit import record_audit_log


router = APIRouter()


@router.get("/alert-outbox", response_model=AdminAlertOutboxPage)
def list_admin_alert_outbox(
    request: Request,
    source_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=24),
    action_hint: str | None = Query(default=None, max_length=40),
    event_code: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxPage:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(AdminAlertOutboxEntry)
    filters = {
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "status": status.strip() if status is not None and status.strip() else None,
        "severity": severity.strip() if severity is not None and severity.strip() else None,
        "action_hint": action_hint.strip() if action_hint is not None and action_hint.strip() else None,
        "event_code": event_code.strip() if event_code is not None and event_code.strip() else None,
        "from": from_at,
        "to": to_at,
    }
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if filters["status"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.status == filters["status"])
    if filters["severity"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.severity == filters["severity"])
    if filters["action_hint"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.action_hint == filters["action_hint"])
    if filters["event_code"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.event_code == filters["event_code"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    statement = statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())
    total = statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.list",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_list",
            "filters": {key: value for key, value in filters.items() if value is not None},
            "total": total,
            "item_count": len(items),
            "external_delivery": False,
        },
    )
    db.commit()
    return AdminAlertOutboxPage(
        items=[admin_alert_outbox_entry_read(entry) for entry in items],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/alert-outbox/queue", response_model=AdminAlertOutboxQueueReport)
def get_admin_alert_outbox_queue(
    request: Request,
    source_type: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None),
    stale_after_hours: int = Query(default=24, ge=1, le=720),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxQueueReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    generated_at = now_at or datetime.now(UTC)
    filters = {
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from": from_at,
        "to": to_at,
        "now_at": generated_at,
        "stale_after_hours": stale_after_hours,
        "item_limit": item_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    report = _admin_alert_outbox_queue_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        stale_after_hours=stale_after_hours,
        item_limit=item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.queue_report",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_queue_snapshot(report),
    )
    db.commit()
    return report


@router.post("/alert-outbox/dispatch-dry-run", response_model=AdminAlertOutboxDispatchDryRunReport)
def dry_run_admin_alert_outbox_dispatch(
    request_body: AdminAlertOutboxDispatchDryRunRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchDryRunReport:
    require_admin(current_user)
    if not request_body.confirm_dry_run:
        raise HTTPException(status_code=422, detail="confirm_dry_run must be true")
    if request_body.from_at is not None and request_body.to_at is not None and request_body.from_at > request_body.to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    unique_entry_ids: list[int] | None = None
    if request_body.entry_ids is not None:
        unique_entry_ids = list(dict.fromkeys(request_body.entry_ids))
        if len(unique_entry_ids) != len(request_body.entry_ids):
            raise HTTPException(status_code=422, detail="entry_ids must be unique")
    generated_at = request_body.now_at or datetime.now(UTC)
    filters = {
        "entry_ids": unique_entry_ids,
        "source_type": (
            request_body.source_type.strip()
            if request_body.source_type is not None and request_body.source_type.strip()
            else None
        ),
        "from_at": request_body.from_at,
        "to_at": request_body.to_at,
        "now_at": generated_at,
        "item_limit": request_body.item_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if unique_entry_ids is not None:
        statement = statement.where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if request_body.from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= request_body.from_at)
    if request_body.to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= request_body.to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    if unique_entry_ids is not None:
        found_ids = {entry.id for entry in entries}
        missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
            )
    report = _admin_alert_outbox_dispatch_dry_run_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        item_limit=request_body.item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_dry_run",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_dry_run_snapshot(report),
    )
    db.commit()
    return report


@router.post("/alert-outbox/dispatch-plans", response_model=AdminAlertOutboxDispatchPlanRead)
def create_admin_alert_outbox_dispatch_plan(
    request_body: AdminAlertOutboxDispatchPlanCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanRead:
    require_admin(current_user)
    if not request_body.confirm_create_plan:
        raise HTTPException(status_code=422, detail="confirm_create_plan must be true")
    entries, filters, generated_at = _admin_alert_outbox_dispatch_entries_for_request(
        db,
        entry_ids=request_body.entry_ids,
        source_type=request_body.source_type,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
        now_at=request_body.now_at,
        entry_limit=request_body.entry_limit,
    )
    report = _admin_alert_outbox_dispatch_dry_run_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        item_limit=request_body.entry_limit,
    )
    if report.ready_count == 0 and not request_body.allow_empty_plan:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "No ready alert outbox entries to plan",
                "dry_run_status": report.dry_run_status,
                "blocked_reason_counts": report.blocked_reason_counts,
            },
        )
    ready_entries = _sort_admin_alert_outbox_queue_items(
        [entry for entry in entries if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at)]
    )[: request_body.entry_limit]
    ready_entry_ids = [entry.id for entry in ready_entries]
    plan = AdminAlertOutboxDispatchPlan(
        plan_key=_admin_alert_outbox_dispatch_plan_key(generated_at),
        plan_status="created",
        dry_run_status=report.dry_run_status,
        source_type=filters.get("source_type"),
        filters_json={
            key: _admin_alert_outbox_snapshot_value(value)
            for key, value in {**report.filters, "entry_limit": request_body.entry_limit}.items()
        },
        policy_json={
            **report.policy,
            "writes_dispatch_plan": True,
            "writes_outbox_state": False,
            "ready_entry_id_limit": request_body.entry_limit,
            "allow_empty_plan": request_body.allow_empty_plan,
        },
        ready_entry_ids_json=ready_entry_ids,
        ready_entry_payload_hashes_json={str(entry.id): entry.payload_hash for entry in ready_entries},
        blocked_reason_counts_json=report.blocked_reason_counts,
        total_count=report.total_count,
        active_count=report.active_count,
        ready_count=report.ready_count,
        blocked_count=report.blocked_count,
        expired_count=report.expired_count,
        not_due_count=report.not_due_count,
        terminal_count=report.terminal_count,
        external_delivery_count=report.external_delivery_count,
        generated_at=generated_at,
        created_by_user_id=current_user.id,
    )
    db.add(plan)
    db.flush()
    response = _admin_alert_outbox_dispatch_plan_read(plan)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.create",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_plan_snapshot(response),
    )
    db.commit()
    return response


@router.get("/alert-outbox/dispatch-plans", response_model=AdminAlertOutboxDispatchPlanPage)
def list_admin_alert_outbox_dispatch_plans(
    request: Request,
    plan_status: str | None = Query(default=None, max_length=32),
    dry_run_status: str | None = Query(default=None, max_length=32),
    source_type: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanPage:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    statement = select(AdminAlertOutboxDispatchPlan).order_by(
        AdminAlertOutboxDispatchPlan.generated_at.desc(),
        AdminAlertOutboxDispatchPlan.id.desc(),
    )
    filters = {
        "plan_status": plan_status.strip() if plan_status is not None and plan_status.strip() else None,
        "dry_run_status": dry_run_status.strip() if dry_run_status is not None and dry_run_status.strip() else None,
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from_at": from_at,
        "to_at": to_at,
        "limit": limit,
        "offset": offset,
    }
    if filters["plan_status"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.plan_status == filters["plan_status"])
    if filters["dry_run_status"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.dry_run_status == filters["dry_run_status"])
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.generated_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.generated_at <= to_at)
    total = statement_count(db, statement)
    plans = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_alert_outbox_dispatch_plan_read(plan) for plan in plans]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.list",
        resource_type="admin_alert_outbox_dispatch_plan",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_dispatch_plan_list",
            "filters": {
                key: _admin_alert_outbox_snapshot_value(value)
                for key, value in filters.items()
                if value is not None
            },
            "total": total,
            "returned_count": len(items),
        },
    )
    db.commit()
    return AdminAlertOutboxDispatchPlanPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/alert-outbox/dispatch-plans/{plan_id}", response_model=AdminAlertOutboxDispatchPlanRead)
def get_admin_alert_outbox_dispatch_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanRead:
    require_admin(current_user)
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    response = _admin_alert_outbox_dispatch_plan_read(plan)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.read",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_dispatch_plan_read",
            "plan_id": plan.id,
            "plan_key": plan.plan_key,
            "plan_status": plan.plan_status,
            "dry_run_status": plan.dry_run_status,
            "ready_count": plan.ready_count,
            "blocked_count": plan.blocked_count,
            "expired_count": plan.expired_count,
            "not_due_count": plan.not_due_count,
            "terminal_count": plan.terminal_count,
        },
    )
    db.commit()
    return response


@router.post(
    "/alert-outbox/dispatch-plans/{plan_id}/validate",
    response_model=AdminAlertOutboxDispatchPlanValidationReport,
)
def validate_admin_alert_outbox_dispatch_plan(
    plan_id: int,
    request_body: AdminAlertOutboxDispatchPlanValidateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanValidationReport:
    require_admin(current_user)
    if not request_body.confirm_validate_plan:
        raise HTTPException(status_code=422, detail="confirm_validate_plan must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    generated_at = request_body.now_at or datetime.now(UTC)
    report = _admin_alert_outbox_dispatch_plan_validation_report(plan, db, generated_at)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.validate",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_plan_validation_snapshot(report),
    )
    db.commit()
    return report


@router.post(
    "/alert-outbox/dispatch-plans/{plan_id}/dispatch",
    response_model=AdminAlertOutboxExternalDispatchReport,
)
def dispatch_admin_alert_outbox_plan(
    plan_id: int,
    request_body: AdminAlertOutboxExternalDispatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxExternalDispatchReport:
    require_admin(current_user)
    if not request_body.confirm_external_dispatch:
        raise HTTPException(status_code=422, detail="confirm_external_dispatch must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    if plan.plan_status != "created":
        raise HTTPException(
            status_code=409,
            detail={"message": "Alert outbox dispatch plan is not dispatchable", "plan_status": plan.plan_status},
        )

    settings = get_settings()
    posture = alert_delivery_posture(settings)
    try:
        adapter = build_alert_delivery_adapter(settings)
    except AlertDeliveryError as exc:
        record_audit_log(
            db,
            actor=current_user,
            action="admin.alert_outbox.external_dispatch.blocked",
            resource_type="admin_alert_outbox_dispatch_plan",
            resource_id=plan.id,
            event_result="failure",
            failure_reason=exc.code,
            request=request,
            snapshot={
                "format": "admin_alert_outbox_external_dispatch_blocked",
                "plan_id": plan.id,
                "plan_key": plan.plan_key,
                "plan_status": plan.plan_status,
                "delivery_posture": posture,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={"message": "External alert delivery is unavailable", "code": exc.code, "posture": posture},
        ) from None

    started_at = datetime.now(UTC)
    validation = _admin_alert_outbox_dispatch_plan_validation_report(plan, db, started_at)
    if validation.validation_status != "valid" or not validation.ready_entry_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Alert outbox dispatch plan changed before dispatch",
                "validation_status": validation.validation_status,
                "blocked_reason_counts": validation.blocked_reason_counts,
            },
        )
    if len(validation.ready_entry_ids) > settings.alert_delivery_batch_limit:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Alert outbox dispatch plan exceeds configured batch limit",
                "ready_count": len(validation.ready_entry_ids),
                "batch_limit": settings.alert_delivery_batch_limit,
            },
        )
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.id.in_(validation.ready_entry_ids))
            .order_by(AdminAlertOutboxEntry.id.asc())
            .with_for_update()
        ).all()
    )
    if [entry.id for entry in entries] != sorted(validation.ready_entry_ids):
        raise HTTPException(status_code=409, detail="Alert outbox dispatch entries changed before claim")
    db.refresh(plan)
    planned_hashes = {str(key): str(value) for key, value in (plan.ready_entry_payload_hashes_json or {}).items()}
    if plan.plan_status != "created" or any(
        planned_hashes.get(str(entry.id)) != entry.payload_hash
        or not _admin_alert_outbox_entry_dispatch_ready(entry, started_at)
        for entry in entries
    ):
        raise HTTPException(status_code=409, detail="Alert outbox dispatch plan changed while claiming entries")

    plan.plan_status = "dispatching"
    for entry in entries:
        entry.status = "dispatching"
        entry.dispatch_mode = adapter.provider
        entry.delivery_target = adapter.delivery_target
        entry.external_delivery = True
        entry.attempt_count += 1
        entry.last_error_code = None
    db.commit()

    results: list[AdminAlertOutboxExternalDispatchItem] = []
    delivered_count = 0
    failed_count = 0
    for entry in entries:
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
            result = AdminAlertOutboxExternalDispatchItem(
                entry_id=entry.id,
                status="failed",
                attempt_count=entry.attempt_count,
                provider=adapter.provider,
                retryable=exc.retryable,
                last_error_code=exc.code,
            )
            record_audit_log(
                db,
                actor=current_user,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="failure",
                failure_reason=exc.code,
                request=request,
                snapshot={
                    "format": "admin_alert_outbox_external_dispatch_result",
                    "plan_id": plan.id,
                    "entry_id": entry.id,
                    "status": "failed",
                    "provider": adapter.provider,
                    "delivery_target": adapter.delivery_target,
                    "attempt_count": entry.attempt_count,
                    "retryable": exc.retryable,
                    "retry_available_at": entry.available_at.isoformat() if entry.available_at is not None else None,
                    "payload_hash_prefix": entry.payload_hash[:12],
                },
            )
        else:
            entry.status = "delivered"
            entry.last_error_code = None
            entry.available_at = None
            delivered_count += 1
            result = AdminAlertOutboxExternalDispatchItem(
                entry_id=entry.id,
                status="delivered",
                attempt_count=entry.attempt_count,
                provider=receipt.provider,
                retryable=False,
                receipt_hash_prefix=receipt.receipt_hash[:12],
            )
            record_audit_log(
                db,
                actor=current_user,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="success",
                request=request,
                snapshot={
                    "format": "admin_alert_outbox_external_dispatch_result",
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
        results.append(result)

    plan.plan_status = (
        "delivered"
        if delivered_count == len(entries)
        else "failed"
        if failed_count == len(entries)
        else "partial_failed"
    )
    completed_at = datetime.now(UTC)
    report = AdminAlertOutboxExternalDispatchReport(
        generated_at=completed_at,
        plan_id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        provider=adapter.provider,
        delivery_target=adapter.delivery_target,
        attempted_count=len(entries),
        delivered_count=delivered_count,
        failed_count=failed_count,
        policy={
            **posture,
            "explicit_confirmation": True,
            "automatic_dispatch": False,
            "idempotency_key_sent": True,
            "original_payload_included": False,
            "failure_affects_source_transaction": False,
            "failed_entry_manual_requeue": True,
        },
        items=results,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.external_dispatch_plan",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success" if failed_count == 0 else "failure",
        failure_reason="partial_or_total_delivery_failure" if failed_count else None,
        request=request,
        snapshot={
            "format": "admin_alert_outbox_external_dispatch_plan",
            "plan_id": report.plan_id,
            "plan_key": report.plan_key,
            "plan_status": report.plan_status,
            "provider": report.provider,
            "delivery_target": report.delivery_target,
            "attempted_count": report.attempted_count,
            "delivered_count": report.delivered_count,
            "failed_count": report.failed_count,
            "entry_ids": [item.entry_id for item in report.items],
            "policy": report.policy,
        },
    )
    db.commit()
    return report


@router.patch("/alert-outbox/reviews", response_model=AdminAlertOutboxBulkReviewResponse)
def review_admin_alert_outbox_entries(
    request_body: AdminAlertOutboxBulkReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxBulkReviewResponse:
    require_admin(current_user)
    if not request_body.confirm_manual_review:
        raise HTTPException(status_code=422, detail="confirm_manual_review must be true")
    unique_entry_ids = list(dict.fromkeys(request_body.entry_ids))
    if len(unique_entry_ids) != len(request_body.entry_ids):
        raise HTTPException(status_code=422, detail="entry_ids must be unique")
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
            .order_by(AdminAlertOutboxEntry.id.asc())
        ).all()
    )
    found_ids = {entry.id for entry in entries}
    missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
        )
    reviewed_at = datetime.now(UTC)
    note = request_body.note.strip() if request_body.note is not None and request_body.note.strip() else None
    previous_status_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    event_code_counts: dict[str, int] = {}
    for entry in entries:
        previous_status_counts[entry.status] = previous_status_counts.get(entry.status, 0) + 1
        source_type_counts[entry.source_type] = source_type_counts.get(entry.source_type, 0) + 1
        severity_counts[entry.severity] = severity_counts.get(entry.severity, 0) + 1
        event_code_counts[entry.event_code] = event_code_counts.get(entry.event_code, 0) + 1
        if request_body.status == "queued" and entry.status == "failed":
            entry.available_at = reviewed_at
        entry.status = request_body.status
        if request_body.status in {"planned", "queued"}:
            entry.dispatch_mode = "manual_review"
            entry.delivery_target = "admin_outbox"
            entry.external_delivery = False
        entry.reviewed_by_user_id = current_user.id
        entry.reviewed_at = reviewed_at
        entry.review_note = note
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.bulk_review",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_bulk_review",
            "entry_count": len(entries),
            "entry_ids": unique_entry_ids,
            "source_types": source_type_counts,
            "event_codes": event_code_counts,
            "severity_counts": severity_counts,
            "previous_status_counts": previous_status_counts,
            "status": request_body.status,
            "reviewed_by_user_id": current_user.id,
            "reviewed_at": reviewed_at.isoformat(),
            "note_provided": note is not None,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
            "external_delivery": False,
            "automatic_actions": False,
        },
    )
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return AdminAlertOutboxBulkReviewResponse(
        generated_at=reviewed_at,
        status=request_body.status,
        updated_count=len(entries),
        requested_count=len(unique_entry_ids),
        previous_status_counts=previous_status_counts,
        policy={
            "external_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
        },
        items=[_admin_alert_outbox_queue_item(entry) for entry in entries],
    )


@router.patch("/alert-outbox/{entry_id}", response_model=AdminAlertOutboxEntryRead)
def review_admin_alert_outbox_entry(
    entry_id: int,
    request_body: AdminAlertOutboxReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxEntryRead:
    require_admin(current_user)
    if not request_body.confirm_manual_review:
        raise HTTPException(status_code=422, detail="confirm_manual_review must be true")
    entry = db.get(AdminAlertOutboxEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Alert outbox entry not found")
    previous_status = entry.status
    reviewed_at = datetime.now(UTC)
    note = request_body.note.strip() if request_body.note is not None and request_body.note.strip() else None
    if request_body.status == "queued" and previous_status == "failed":
        entry.available_at = reviewed_at
    entry.status = request_body.status
    if request_body.status in {"planned", "queued"}:
        entry.dispatch_mode = "manual_review"
        entry.delivery_target = "admin_outbox"
        entry.external_delivery = False
    entry.reviewed_by_user_id = current_user.id
    entry.reviewed_at = reviewed_at
    entry.review_note = note
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.review",
        resource_type="admin_alert_outbox",
        resource_id=str(entry.id),
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_review",
            "entry_id": entry.id,
            "source_type": entry.source_type,
            "source_id": entry.source_id,
            "source_key": entry.source_key,
            "event_code": entry.event_code,
            "severity": entry.severity,
            "action_hint": entry.action_hint,
            "previous_status": previous_status,
            "status": entry.status,
            "dispatch_mode": entry.dispatch_mode,
            "delivery_target": entry.delivery_target,
            "external_delivery": entry.external_delivery,
            "reviewed_by_user_id": current_user.id,
            "reviewed_at": reviewed_at.isoformat(),
            "note_provided": note is not None,
            "automatic_actions": False,
        },
    )
    db.commit()
    db.refresh(entry)
    return admin_alert_outbox_entry_read(entry)




def _admin_alert_outbox_queue_report(
    entries: list[AdminAlertOutboxEntry],
    *,
    generated_at: datetime,
    filters: dict[str, Any],
    stale_after_hours: int,
    item_limit: int,
) -> AdminAlertOutboxQueueReport:
    stale_before = generated_at - timedelta(hours=stale_after_hours)
    pending_review = [entry for entry in entries if entry.status == "pending_review"]
    planned = [entry for entry in entries if entry.status == "planned"]
    queued = [entry for entry in entries if entry.status == "queued"]
    dispatching = [entry for entry in entries if entry.status == "dispatching"]
    delivered = [entry for entry in entries if entry.status == "delivered"]
    failed = [entry for entry in entries if entry.status == "failed"]
    suppressed = [entry for entry in entries if entry.status == "suppressed"]
    cancelled = [entry for entry in entries if entry.status == "cancelled"]
    stale_pending_review = [
        entry for entry in pending_review if naive_utc(entry.last_seen_at) <= naive_utc(stale_before)
    ]
    due_planned = [entry for entry in planned if _admin_alert_outbox_entry_due(entry, generated_at)]
    due_queued = [entry for entry in queued if _admin_alert_outbox_entry_due(entry, generated_at)]
    ready_entries = _sort_admin_alert_outbox_queue_items(due_queued + due_planned)
    active_count = len(pending_review) + len(planned) + len(queued) + len(dispatching) + len(failed)
    terminal_count = len(delivered) + len(suppressed) + len(cancelled)
    if ready_entries or dispatching:
        queue_status: Literal["empty", "review_required", "ready", "cleared"] = "ready"
    elif pending_review or failed:
        queue_status = "review_required"
    elif entries:
        queue_status = "cleared"
    else:
        queue_status = "empty"
    status_order = [
        "pending_review",
        "planned",
        "queued",
        "dispatching",
        "failed",
        "delivered",
        "suppressed",
        "cancelled",
    ]
    buckets = [
        _admin_alert_outbox_status_bucket(status, [entry for entry in entries if entry.status == status])
        for status in status_order
    ]
    filtered_snapshot_filters = {key: value for key, value in filters.items() if value is not None}
    return AdminAlertOutboxQueueReport(
        generated_at=generated_at,
        filters=filtered_snapshot_filters,
        policy={
            "external_delivery": bool(
                alert_delivery_posture(get_settings())["enabled"]
                and alert_delivery_posture(get_settings())["configured"]
            ),
            "delivery_posture": alert_delivery_posture(get_settings()),
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
            "stale_after_hours": stale_after_hours,
        },
        queue_status=queue_status,
        total_count=len(entries),
        active_count=active_count,
        pending_review_count=len(pending_review),
        planned_count=len(planned),
        queued_count=len(queued),
        dispatching_count=len(dispatching),
        delivered_count=len(delivered),
        failed_count=len(failed),
        suppressed_count=len(suppressed),
        cancelled_count=len(cancelled),
        terminal_count=terminal_count,
        stale_pending_review_count=len(stale_pending_review),
        due_planned_count=len(due_planned),
        due_queued_count=len(due_queued),
        external_delivery_count=sum(1 for entry in entries if entry.external_delivery),
        oldest_pending_review_at=_oldest_datetime(entry.last_seen_at for entry in pending_review),
        oldest_due_at=_oldest_datetime(
            (entry.available_at or entry.last_seen_at) for entry in due_planned + due_queued
        ),
        status_buckets=buckets,
        pending_review_items=[
            _admin_alert_outbox_queue_item(entry)
            for entry in _sort_admin_alert_outbox_queue_items(pending_review + failed)[:item_limit]
        ],
        ready_items=[_admin_alert_outbox_queue_item(entry) for entry in ready_entries[:item_limit]],
        terminal_items=[
            _admin_alert_outbox_queue_item(entry)
            for entry in _sort_admin_alert_outbox_queue_items(delivered + suppressed + cancelled)[:item_limit]
        ],
    )


def _admin_alert_outbox_queue_snapshot(report: AdminAlertOutboxQueueReport) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_queue",
        "queue_status": report.queue_status,
        "filters": {key: _admin_alert_outbox_snapshot_value(value) for key, value in report.filters.items()},
        "policy": report.policy,
        "total_count": report.total_count,
        "active_count": report.active_count,
        "pending_review_count": report.pending_review_count,
        "planned_count": report.planned_count,
        "queued_count": report.queued_count,
        "dispatching_count": report.dispatching_count,
        "delivered_count": report.delivered_count,
        "failed_count": report.failed_count,
        "suppressed_count": report.suppressed_count,
        "cancelled_count": report.cancelled_count,
        "terminal_count": report.terminal_count,
        "stale_pending_review_count": report.stale_pending_review_count,
        "due_planned_count": report.due_planned_count,
        "due_queued_count": report.due_queued_count,
        "external_delivery_count": report.external_delivery_count,
        "oldest_pending_review_at": report.oldest_pending_review_at.isoformat()
        if report.oldest_pending_review_at is not None
        else None,
        "oldest_due_at": report.oldest_due_at.isoformat() if report.oldest_due_at is not None else None,
        "status_buckets": {bucket.status: bucket.total for bucket in report.status_buckets},
        "automatic_actions": False,
        "external_delivery": report.policy["external_delivery"],
    }


def _admin_alert_outbox_dispatch_dry_run_report(
    entries: list[AdminAlertOutboxEntry],
    *,
    generated_at: datetime,
    filters: dict[str, Any],
    item_limit: int,
) -> AdminAlertOutboxDispatchDryRunReport:
    active_entries = [
        entry
        for entry in entries
        if entry.status in {"pending_review", "planned", "queued", "dispatching", "failed"}
    ]
    terminal_entries = [entry for entry in entries if entry.status in {"delivered", "suppressed", "cancelled"}]
    expired_entries = [
        entry for entry in active_entries if _admin_alert_outbox_entry_expired(entry, generated_at)
    ]
    ready_entries = [
        entry
        for entry in active_entries
        if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at)
    ]
    ready_entry_ids = {entry.id for entry in ready_entries}
    not_due_entries = [
        entry
        for entry in active_entries
        if _admin_alert_outbox_entry_dispatch_not_due(entry, generated_at)
    ]
    not_due_entry_ids = {entry.id for entry in not_due_entries}
    expired_entry_ids = {entry.id for entry in expired_entries}
    blocked_entries = [
        entry
        for entry in active_entries
        if entry.id not in ready_entry_ids
        and entry.id not in not_due_entry_ids
        and entry.id not in expired_entry_ids
    ]
    if ready_entries:
        dry_run_status: Literal["empty", "blocked", "expired", "ready", "cleared"] = "ready"
    elif blocked_entries or not_due_entries:
        dry_run_status = "blocked"
    elif expired_entries:
        dry_run_status = "expired"
    elif entries:
        dry_run_status = "cleared"
    else:
        dry_run_status = "empty"
    filtered_snapshot_filters = {key: value for key, value in filters.items() if value is not None}
    return AdminAlertOutboxDispatchDryRunReport(
        generated_at=generated_at,
        filters=filtered_snapshot_filters,
        policy={
            "dry_run": True,
            "writes_outbox_state": False,
            "increments_attempts": False,
            "external_delivery": False,
            "broker_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
        },
        dry_run_status=dry_run_status,
        total_count=len(entries),
        active_count=len(active_entries),
        pending_review_count=sum(1 for entry in active_entries if entry.status == "pending_review"),
        planned_count=sum(1 for entry in active_entries if entry.status == "planned"),
        queued_count=sum(1 for entry in active_entries if entry.status == "queued"),
        ready_count=len(ready_entries),
        blocked_count=len(blocked_entries),
        expired_count=len(expired_entries),
        not_due_count=len(not_due_entries),
        terminal_count=len(terminal_entries),
        external_delivery_count=sum(1 for entry in entries if entry.external_delivery),
        blocked_reason_counts=_admin_alert_outbox_dispatch_entry_reason_counts(blocked_entries, generated_at),
        ready_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(ready_entries)[:item_limit]
        ],
        blocked_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(blocked_entries)[:item_limit]
        ],
        expired_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(expired_entries)[:item_limit]
        ],
        not_due_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(not_due_entries)[:item_limit]
        ],
    )


def _admin_alert_outbox_dispatch_dry_run_snapshot(report: AdminAlertOutboxDispatchDryRunReport) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_dry_run",
        "dry_run_status": report.dry_run_status,
        "filters": {key: _admin_alert_outbox_snapshot_value(value) for key, value in report.filters.items()},
        "policy": report.policy,
        "total_count": report.total_count,
        "active_count": report.active_count,
        "pending_review_count": report.pending_review_count,
        "planned_count": report.planned_count,
        "queued_count": report.queued_count,
        "ready_count": report.ready_count,
        "blocked_count": report.blocked_count,
        "expired_count": report.expired_count,
        "not_due_count": report.not_due_count,
        "terminal_count": report.terminal_count,
        "external_delivery_count": report.external_delivery_count,
        "ready_entry_ids": [item.id for item in report.ready_items],
        "blocked_reason_counts": report.blocked_reason_counts,
        "expired_entry_ids": [item.id for item in report.expired_items],
        "not_due_entry_ids": [item.id for item in report.not_due_items],
    }


def _admin_alert_outbox_dispatch_entries_for_request(
    db: Session,
    *,
    entry_ids: list[int] | None,
    source_type: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    now_at: datetime | None,
    entry_limit: int,
) -> tuple[list[AdminAlertOutboxEntry], dict[str, Any], datetime]:
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    unique_entry_ids: list[int] | None = None
    if entry_ids is not None:
        unique_entry_ids = list(dict.fromkeys(entry_ids))
        if len(unique_entry_ids) != len(entry_ids):
            raise HTTPException(status_code=422, detail="entry_ids must be unique")
    generated_at = now_at or datetime.now(UTC)
    filters = {
        "entry_ids": unique_entry_ids,
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from_at": from_at,
        "to_at": to_at,
        "now_at": generated_at,
        "entry_limit": entry_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if unique_entry_ids is not None:
        statement = statement.where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    if unique_entry_ids is not None:
        found_ids = {entry.id for entry in entries}
        missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
            )
    return entries, filters, generated_at


def _admin_alert_outbox_dispatch_plan_key(generated_at: datetime) -> str:
    return sha256(f"{uuid4().hex}:{generated_at.isoformat()}".encode("utf-8")).hexdigest()


def _admin_alert_outbox_dispatch_plan_read(
    plan: AdminAlertOutboxDispatchPlan,
) -> AdminAlertOutboxDispatchPlanRead:
    ready_entry_ids = [int(entry_id) for entry_id in list(plan.ready_entry_ids_json or [])]
    return AdminAlertOutboxDispatchPlanRead(
        id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        generated_at=plan.generated_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        created_by_user_id=plan.created_by_user_id,
        source_type=plan.source_type,
        filters=plan.filters_json or {},
        policy=plan.policy_json or {},
        dry_run_status=plan.dry_run_status,  # type: ignore[arg-type]
        total_count=plan.total_count,
        active_count=plan.active_count,
        ready_count=plan.ready_count,
        blocked_count=plan.blocked_count,
        expired_count=plan.expired_count,
        not_due_count=plan.not_due_count,
        terminal_count=plan.terminal_count,
        external_delivery_count=plan.external_delivery_count,
        ready_entry_ids=ready_entry_ids,
        ready_entry_count=len(ready_entry_ids),
        truncated_ready_entry_ids=plan.ready_count > len(ready_entry_ids),
        blocked_reason_counts=plan.blocked_reason_counts_json or {},
    )


def _admin_alert_outbox_dispatch_plan_snapshot(plan: AdminAlertOutboxDispatchPlanRead) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_plan",
        "plan_id": plan.id,
        "plan_key": plan.plan_key,
        "plan_status": plan.plan_status,
        "dry_run_status": plan.dry_run_status,
        "filters": plan.filters,
        "policy": plan.policy,
        "total_count": plan.total_count,
        "active_count": plan.active_count,
        "ready_count": plan.ready_count,
        "blocked_count": plan.blocked_count,
        "expired_count": plan.expired_count,
        "not_due_count": plan.not_due_count,
        "terminal_count": plan.terminal_count,
        "external_delivery_count": plan.external_delivery_count,
        "ready_entry_ids": plan.ready_entry_ids,
        "ready_entry_count": plan.ready_entry_count,
        "truncated_ready_entry_ids": plan.truncated_ready_entry_ids,
        "blocked_reason_counts": plan.blocked_reason_counts,
    }


def _admin_alert_outbox_dispatch_plan_validation_report(
    plan: AdminAlertOutboxDispatchPlan,
    db: Session,
    generated_at: datetime,
) -> AdminAlertOutboxDispatchPlanValidationReport:
    planned_entry_ids = [int(entry_id) for entry_id in list(plan.ready_entry_ids_json or [])]
    planned_hashes = {str(key): str(value) for key, value in (plan.ready_entry_payload_hashes_json or {}).items()}
    if not planned_entry_ids:
        return AdminAlertOutboxDispatchPlanValidationReport(
            generated_at=generated_at,
            plan_id=plan.id,
            plan_key=plan.plan_key,
            plan_status=plan.plan_status,  # type: ignore[arg-type]
            validation_status="empty",
            policy=_admin_alert_outbox_dispatch_plan_validation_policy(plan),
            planned_ready_count=0,
            current_ready_count=0,
            missing_count=0,
            payload_hash_mismatch_count=0,
            payload_hash_snapshot_missing_count=0,
            blocked_count=0,
            expired_count=0,
            not_due_count=0,
            payload_hash_snapshot_available=True,
            ready_entry_ids=[],
            missing_entry_ids=[],
            payload_hash_mismatch_entry_ids=[],
            payload_hash_snapshot_missing_entry_ids=[],
            blocked_entry_ids=[],
            expired_entry_ids=[],
            not_due_entry_ids=[],
            blocked_reason_counts={},
        )
    entries = list(
        db.scalars(select(AdminAlertOutboxEntry).where(AdminAlertOutboxEntry.id.in_(planned_entry_ids))).all()
    )
    entry_by_id = {entry.id: entry for entry in entries}
    ready_entry_ids: list[int] = []
    missing_entry_ids: list[int] = []
    mismatch_entry_ids: list[int] = []
    snapshot_missing_entry_ids: list[int] = []
    blocked_entry_ids: list[int] = []
    expired_entry_ids: list[int] = []
    not_due_entry_ids: list[int] = []
    blocked_reason_counts: dict[str, int] = {}
    for entry_id in planned_entry_ids:
        entry = entry_by_id.get(entry_id)
        if entry is None:
            missing_entry_ids.append(entry_id)
            blocked_reason_counts["missing_entry"] = blocked_reason_counts.get("missing_entry", 0) + 1
            continue
        planned_hash = planned_hashes.get(str(entry_id))
        if planned_hash is None:
            snapshot_missing_entry_ids.append(entry_id)
            blocked_entry_ids.append(entry_id)
            reason = "payload_hash_snapshot_missing"
            blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
            continue
        if entry.payload_hash != planned_hash:
            mismatch_entry_ids.append(entry_id)
            blocked_entry_ids.append(entry_id)
            blocked_reason_counts["payload_hash_mismatch"] = blocked_reason_counts.get("payload_hash_mismatch", 0) + 1
            continue
        if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at):
            ready_entry_ids.append(entry_id)
            continue
        if _admin_alert_outbox_entry_expired(entry, generated_at):
            expired_entry_ids.append(entry_id)
            blocked_reason_counts["expired"] = blocked_reason_counts.get("expired", 0) + 1
            continue
        if _admin_alert_outbox_entry_dispatch_not_due(entry, generated_at):
            not_due_entry_ids.append(entry_id)
            blocked_reason_counts["queued_not_due"] = blocked_reason_counts.get("queued_not_due", 0) + 1
            continue
        reason = _admin_alert_outbox_dispatch_reason(entry, generated_at)
        blocked_entry_ids.append(entry_id)
        blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
    validation_status: Literal["valid", "changed", "empty"] = (
        "valid"
        if len(ready_entry_ids) == len(planned_entry_ids)
        and not missing_entry_ids
        and not mismatch_entry_ids
        and not snapshot_missing_entry_ids
        and not blocked_entry_ids
        and not expired_entry_ids
        and not not_due_entry_ids
        else "changed"
    )
    return AdminAlertOutboxDispatchPlanValidationReport(
        generated_at=generated_at,
        plan_id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        validation_status=validation_status,
        policy=_admin_alert_outbox_dispatch_plan_validation_policy(plan),
        planned_ready_count=len(planned_entry_ids),
        current_ready_count=len(ready_entry_ids),
        missing_count=len(missing_entry_ids),
        payload_hash_mismatch_count=len(mismatch_entry_ids),
        payload_hash_snapshot_missing_count=len(snapshot_missing_entry_ids),
        blocked_count=len(blocked_entry_ids),
        expired_count=len(expired_entry_ids),
        not_due_count=len(not_due_entry_ids),
        payload_hash_snapshot_available=not snapshot_missing_entry_ids,
        ready_entry_ids=ready_entry_ids,
        missing_entry_ids=missing_entry_ids,
        payload_hash_mismatch_entry_ids=mismatch_entry_ids,
        payload_hash_snapshot_missing_entry_ids=snapshot_missing_entry_ids,
        blocked_entry_ids=blocked_entry_ids,
        expired_entry_ids=expired_entry_ids,
        not_due_entry_ids=not_due_entry_ids,
        blocked_reason_counts=blocked_reason_counts,
    )


def _admin_alert_outbox_dispatch_plan_validation_policy(plan: AdminAlertOutboxDispatchPlan) -> dict[str, Any]:
    return {
        "dry_run": True,
        "validates_plan": True,
        "validates_payload_hashes": True,
        "writes_outbox_state": False,
        "increments_attempts": False,
        "external_delivery": False,
        "broker_delivery": False,
        "automatic_actions": False,
        "dispatch_mode": "manual_review",
        "delivery_target": "admin_outbox",
        "plan_id": plan.id,
        "plan_key": plan.plan_key,
    }


def _admin_alert_outbox_dispatch_plan_validation_snapshot(
    report: AdminAlertOutboxDispatchPlanValidationReport,
) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_plan_validation",
        "plan_id": report.plan_id,
        "plan_key": report.plan_key,
        "plan_status": report.plan_status,
        "validation_status": report.validation_status,
        "policy": report.policy,
        "planned_ready_count": report.planned_ready_count,
        "current_ready_count": report.current_ready_count,
        "missing_count": report.missing_count,
        "payload_hash_mismatch_count": report.payload_hash_mismatch_count,
        "payload_hash_snapshot_missing_count": report.payload_hash_snapshot_missing_count,
        "blocked_count": report.blocked_count,
        "expired_count": report.expired_count,
        "not_due_count": report.not_due_count,
        "payload_hash_snapshot_available": report.payload_hash_snapshot_available,
        "ready_entry_ids": report.ready_entry_ids,
        "missing_entry_ids": report.missing_entry_ids,
        "payload_hash_mismatch_entry_ids": report.payload_hash_mismatch_entry_ids,
        "payload_hash_snapshot_missing_entry_ids": report.payload_hash_snapshot_missing_entry_ids,
        "blocked_entry_ids": report.blocked_entry_ids,
        "expired_entry_ids": report.expired_entry_ids,
        "not_due_entry_ids": report.not_due_entry_ids,
        "blocked_reason_counts": report.blocked_reason_counts,
    }


def _admin_alert_outbox_snapshot_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _admin_alert_outbox_snapshot_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_admin_alert_outbox_snapshot_value(item) for item in value]
    return value


def _admin_alert_outbox_entry_due(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return entry.available_at is None or naive_utc(entry.available_at) <= naive_utc(now_at)


def _admin_alert_outbox_entry_expired(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return entry.expires_at is not None and naive_utc(entry.expires_at) <= naive_utc(now_at)


def _admin_alert_outbox_entry_dispatch_ready(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return (
        entry.status == "queued"
        and _admin_alert_outbox_entry_due(entry, now_at)
        and not _admin_alert_outbox_entry_expired(entry, now_at)
        and not entry.external_delivery
        and entry.dispatch_mode == "manual_review"
        and entry.delivery_target == "admin_outbox"
    )


def _admin_alert_outbox_entry_dispatch_not_due(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return (
        entry.status == "queued"
        and not _admin_alert_outbox_entry_due(entry, now_at)
        and not _admin_alert_outbox_entry_expired(entry, now_at)
        and not entry.external_delivery
        and entry.dispatch_mode == "manual_review"
        and entry.delivery_target == "admin_outbox"
    )


def _admin_alert_outbox_status_bucket(
    status: str,
    entries: list[AdminAlertOutboxEntry],
) -> AdminAlertOutboxStatusBucket:
    return AdminAlertOutboxStatusBucket(
        status=status,  # type: ignore[arg-type]
        total=len(entries),
        critical_count=sum(1 for entry in entries if entry.severity == "critical"),
        warning_count=sum(1 for entry in entries if entry.severity == "warning"),
        info_count=sum(1 for entry in entries if entry.severity == "info"),
        oldest_last_seen_at=_oldest_datetime(entry.last_seen_at for entry in entries),
        latest_last_seen_at=_latest_datetime(entry.last_seen_at for entry in entries),
        oldest_available_at=_oldest_datetime(entry.available_at for entry in entries if entry.available_at is not None),
        latest_reviewed_at=_latest_datetime(entry.reviewed_at for entry in entries if entry.reviewed_at is not None),
    )


def _admin_alert_outbox_dispatch_dry_run_item(
    entry: AdminAlertOutboxEntry,
    now_at: datetime,
) -> AdminAlertOutboxDispatchDryRunItem:
    return AdminAlertOutboxDispatchDryRunItem(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,  # type: ignore[arg-type]
        reason=_admin_alert_outbox_dispatch_reason(entry, now_at),
        dispatch_mode=entry.dispatch_mode,
        delivery_target=entry.delivery_target,
        external_delivery=entry.external_delivery,
        payload_hash_prefix=entry.payload_hash[:12],
        delivery_key=_admin_alert_outbox_delivery_key(entry),
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        expires_at=entry.expires_at,
        reviewed_at=entry.reviewed_at,
        attempt_count=entry.attempt_count,
    )


def _admin_alert_outbox_dispatch_reason(entry: AdminAlertOutboxEntry, now_at: datetime) -> str:
    if _admin_alert_outbox_entry_expired(entry, now_at):
        return "expired"
    if entry.status == "dispatching":
        return "dispatch_in_progress"
    if entry.status == "failed":
        return "failed_requires_manual_requeue"
    if entry.external_delivery:
        return "external_delivery_disabled"
    if entry.dispatch_mode != "manual_review":
        return "unsupported_dispatch_mode"
    if entry.delivery_target != "admin_outbox":
        return "unsupported_delivery_target"
    if entry.status == "pending_review":
        return "pending_review"
    if entry.status == "planned":
        return "planned_not_queued"
    if entry.status == "queued" and not _admin_alert_outbox_entry_due(entry, now_at):
        return "queued_not_due"
    if entry.status == "queued":
        return "queued_due"
    return "terminal"


def _admin_alert_outbox_delivery_key(entry: AdminAlertOutboxEntry) -> str:
    return sha256(f"{entry.id}:{entry.source_type}:{entry.event_code}:{entry.payload_hash}".encode("utf-8")).hexdigest()[
        :16
    ]


def _admin_alert_outbox_dispatch_entry_reason_counts(
    entries: list[AdminAlertOutboxEntry],
    now_at: datetime,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        reason = _admin_alert_outbox_dispatch_reason(entry, now_at)
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _admin_alert_outbox_queue_item(entry: AdminAlertOutboxEntry) -> AdminAlertOutboxQueueItem:
    return AdminAlertOutboxQueueItem(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,  # type: ignore[arg-type]
        external_delivery=entry.external_delivery,
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        reviewed_at=entry.reviewed_at,
        seen_count=entry.seen_count,
    )


def _sort_admin_alert_outbox_queue_items(entries: list[AdminAlertOutboxEntry]) -> list[AdminAlertOutboxEntry]:
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    status_order = {
        "queued": 0,
        "planned": 1,
        "dispatching": 2,
        "failed": 3,
        "pending_review": 4,
        "delivered": 5,
        "suppressed": 6,
        "cancelled": 7,
    }
    return sorted(
        entries,
        key=lambda entry: (
            status_order.get(entry.status, 99),
            severity_order.get(entry.severity, 99),
            naive_utc(entry.available_at or entry.last_seen_at),
            naive_utc(entry.last_seen_at),
            entry.id,
        ),
    )
