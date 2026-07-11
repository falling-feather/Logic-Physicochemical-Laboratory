import csv
import io
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.endpoints import admin_content, admin_organizations, admin_snapshot_tasks, admin_users
from app.api.endpoints.admin_presenters import (
    admin_alert_outbox_entry_read as _admin_alert_outbox_entry_read,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AdminAlertOutboxDispatchPlan,
    AdminAlertOutboxEntry,
    AuditLog,
    Assignment,
    BackgroundTask,
    BackgroundTaskAttempt,
    BugExternalSyncOperation,
    BugRecord,
    ClassGroup,
    ClassJoinRequest,
    ContentDraft,
    ContentPageRecord,
    ContentPageVersion,
    Course,
    CourseUnit,
    LearningEvent,
    PointLedger,
    School,
    Submission,
    User,
)
from app.schemas.admin import (
    AdminPendingSubmissionQueue,
    AdminPendingSubmissionRead,
    AdminStats,
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
    AdminAlertOutboxExternalDispatchItem,
    AdminAlertOutboxExternalDispatchReport,
    AdminAlertOutboxExternalDispatchRequest,
    AdminAlertOutboxEntryRead,
    AdminAlertOutboxPage,
    AdminAlertOutboxQueueItem,
    AdminAlertOutboxQueueReport,
    AdminAlertOutboxStatusBucket,
    AdminAlertOutboxReviewRequest,
    AdminBackgroundTaskActionRequest,
    AdminBackgroundTaskAttemptRead,
    AdminBackgroundTaskEnqueueRequest,
    AdminBackgroundTaskPage,
    AdminBackgroundTaskQueueReport,
    AdminBackgroundTaskRead,
    AdminContentScriptScanTaskEnqueueRequest,
    AdminKnowledgeSnapshotTaskEnqueueRequest,
    AuditLogExport,
    AuditLogExportItem,
    AuditLogChainVerification,
    AuditLogFrequencyCandidate,
    AuditLogFrequencyReport,
    AuditLogPage,
    AuditLogRead,
    AuditLogReport,
    AuditLogReportBucket,
    AuditLogRetentionPlan,
    AuditLogRetentionPolicy,
    AuditLogRetentionSummary,
    AuditLogActionReport,
    BugRecordCreate,
    BugExternalCommentSyncRequest,
    BugExternalSyncOperationPage,
    BugExternalSyncOperationRead,
    BugExternalSyncRequest,
    BugExternalSyncResponse,
    BugRecordPage,
    BugRecordRead,
    BugRecordUpdate,
)
from app.services.admin_common import (
    PENDING_SUBMISSION_STATUSES,
    change_snapshot as _change_snapshot,
    contains_pattern as _contains_pattern,
    count_rows as _count,
    naive_utc as _naive_utc,
    next_offset as _next_offset,
    require_admin as _require_admin,
    statement_count as _statement_count,
)
from app.services.audit import record_audit_log
from app.services.bug_external_sync import (
    BugExternalSyncError,
    BugExternalSyncResult,
    bug_external_sync_operation_read,
    create_external_issue_for_bug,
    sync_external_issue_comment_for_bug,
    sync_external_issue_status_for_bug,
)
from app.services.alert_delivery import (
    AlertDeliveryError,
    alert_delivery_posture,
    build_alert_delivery_adapter,
    build_alert_delivery_envelope,
)
from app.services.background_tasks import (
    cancel_background_task,
    enqueue_background_task,
    retry_background_task,
)
from app.services.external_issue_providers import (
    build_issue_provider_adapter,
    external_issue_sync_posture,
)
from app.services.backend_performance import build_backend_performance_report
from app.services.access_control import (
    require_class_teacher_or_admin_by_id,
    teacher_class_ids,
)
from app.services.audit_chain import verify_audit_log_chain
from app.services.text import require_trimmed_text
router = APIRouter()
router.include_router(admin_users.router)
router.include_router(admin_organizations.router)
router.include_router(admin_content.router)
_AUDIT_LOG_CSV_FIELDS = (
    "id",
    "actor_user_id",
    "actor_role",
    "action",
    "resource",
    "resource_type",
    "resource_id",
    "school_id",
    "class_id",
    "event_result",
    "failure_reason",
    "request_id",
    "client_ip_hash",
    "user_agent",
    "request_method",
    "request_path",
    "prev_hash",
    "current_hash",
    "snapshot_json",
    "created_at",
)
_AUDIT_LOG_REPORT_CSV_FIELDS = ("section", "key", "total", "success", "failure", "other", "latest_at")


@router.get("/stats", response_model=AdminStats)
def read_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminStats:
    _require_admin(current_user)
    users_by_role = {
        str(role): int(count)
        for role, count in db.execute(select(User.role, func.count()).group_by(User.role)).all()
    }
    return AdminStats(
        total_users=_count(db, User),
        active_users=_count(db, User, User.status == "active"),
        users_by_role=users_by_role,
        total_schools=_count(db, School),
        total_classes=_count(db, ClassGroup),
        pending_class_join_requests=_count(db, ClassJoinRequest, ClassJoinRequest.status == "pending"),
        total_content_pages=_count(db, ContentPageRecord),
        total_content_drafts=_count(db, ContentDraft),
        total_content_page_versions=_count(db, ContentPageVersion),
        pending_script_reviews=_count(db, ContentDraft, ContentDraft.script_review_status == "pending"),
        total_courses=_count(db, Course),
        total_assignments=_count(db, Assignment),
        total_learning_events=_count(db, LearningEvent),
        total_submissions=_count(db, Submission),
        total_point_ledger_entries=_count(db, PointLedger),
        total_bug_records=_count(db, BugRecord),
        open_bug_records=_count(db, BugRecord, BugRecord.status != "closed"),
        total_audit_logs=_count(db, AuditLog),
    )


@router.get("/performance/report")
def get_backend_performance_report(
    request: Request,
    include_explain: bool = Query(default=True),
    include_benchmark: bool = Query(default=True),
    require_mysql: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_admin(current_user)
    report = build_backend_performance_report(
        db,
        settings=get_settings(),
        include_explain=include_explain,
        include_benchmark=include_benchmark,
        require_mysql=require_mysql,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.performance.report",
        resource_type="backend_performance",
        event_result="success" if report["ok"] else "failure",
        failure_reason=None if report["ok"] else report["status"],
        request=request,
        snapshot={
            "status": report["status"],
            "dialect": report["dialect"],
            "require_mysql": require_mysql,
            "include_explain": include_explain,
            "include_benchmark": include_benchmark,
            "summary": report["summary"],
            "deferred_risk_codes": [item["code"] for item in report["deferred_risks"]],
            "sql_text_returned": False,
            "database_url_returned": False,
        },
    )
    db.commit()
    return report


router.include_router(admin_snapshot_tasks.router)


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
    _require_admin(current_user)
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
    total = _statement_count(db, statement)
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
        items=[_admin_alert_outbox_entry_read(entry) for entry in items],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    total = _statement_count(db, statement)
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
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/alert-outbox/dispatch-plans/{plan_id}", response_model=AdminAlertOutboxDispatchPlanRead)
def get_admin_alert_outbox_dispatch_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanRead:
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    _require_admin(current_user)
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
    return _admin_alert_outbox_entry_read(entry)


@router.post(
    "/background-tasks/alert-dispatch-plans/{plan_id}",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_alert_dispatch_plan_background_task(
    plan_id: int,
    request_body: AdminBackgroundTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    if plan.plan_status != "created":
        raise HTTPException(status_code=409, detail="Only created alert dispatch plans can be enqueued")
    result = enqueue_background_task(
        db,
        task_type="alert_outbox_dispatch_plan",
        idempotency_key=f"alert-dispatch-plan:{plan.id}:{plan.plan_key}",
        source_type="admin_alert_outbox_dispatch_plan",
        source_id=plan.id,
        payload={"plan_id": plan.id},
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "source_type": result.task.source_type,
            "source_id": result.task.source_id,
            "created": result.created,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/knowledge-snapshots",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_knowledge_snapshot_background_task(
    request_body: AdminKnowledgeSnapshotTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    result = enqueue_background_task(
        db,
        task_type="knowledge_snapshot_rebuild",
        idempotency_key=(
            f"knowledge-snapshot:{request_body.granularity}:{request_body.reference_date.isoformat()}"
        ),
        source_type="knowledge_snapshot_window",
        source_id=None,
        payload={
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
        },
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/content-script-scans",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_content_script_scan_background_task(
    request_body: AdminContentScriptScanTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    payload = {
        "slug": request_body.slug.strip("/") if request_body.slug and request_body.slug.strip("/") else None,
        "source_host": request_body.source_host.strip().lower()
        if request_body.source_host and request_body.source_host.strip()
        else None,
        "scan_limit": request_body.scan_limit,
        "scan_offset": request_body.scan_offset,
    }
    scope_hash = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    result = enqueue_background_task(
        db,
        task_type="content_script_asset_scan",
        idempotency_key=f"content-script-scan:{request_body.request_key.strip()}:{scope_hash}",
        source_type="content_script_asset_scan_request",
        source_id=None,
        payload=payload,
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "filters": payload,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.get("/background-tasks", response_model=AdminBackgroundTaskPage)
def list_background_tasks(
    task_type: str | None = Query(default=None, max_length=80),
    task_status: str | None = Query(default=None, alias="status", max_length=32),
    source_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskPage:
    _require_admin(current_user)
    statement = select(BackgroundTask).order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
    if task_type:
        statement = statement.where(BackgroundTask.task_type == task_type.strip())
    if task_status:
        statement = statement.where(BackgroundTask.status == task_status.strip())
    if source_type:
        statement = statement.where(BackgroundTask.source_type == source_type.strip())
    total = _statement_count(db, statement)
    tasks = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminBackgroundTaskPage(
        items=[_admin_background_task_read(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(tasks)),
    )


@router.get("/background-tasks/queue", response_model=AdminBackgroundTaskQueueReport)
def get_background_task_queue(
    now_at: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskQueueReport:
    _require_admin(current_user)
    generated_at = now_at or datetime.now(UTC)
    generated_at_value = _naive_utc(generated_at)
    by_status = {
        str(task_status): int(count)
        for task_status, count in db.execute(
            select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(BackgroundTask.status)
        ).all()
    }
    by_task_type = {
        str(task_type): int(count)
        for task_type, count in db.execute(
            select(BackgroundTask.task_type, func.count(BackgroundTask.id)).group_by(BackgroundTask.task_type)
        ).all()
    }
    ready_condition = and_(
        BackgroundTask.status.in_(["pending", "retry_wait"]),
        BackgroundTask.available_at <= generated_at_value,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    stale_condition = and_(
        BackgroundTask.status == "leased",
        BackgroundTask.lease_expires_at.is_not(None),
        BackgroundTask.lease_expires_at <= generated_at_value,
    )
    stale_claimable_condition = and_(
        stale_condition,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    ready_count = int(db.scalar(select(func.count()).select_from(BackgroundTask).where(ready_condition)) or 0)
    stale_lease_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_condition)) or 0
    )
    stale_claimable_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_claimable_condition)) or 0
    )
    oldest_pending_ready = db.scalar(select(func.min(BackgroundTask.available_at)).where(ready_condition))
    oldest_stale_ready = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(stale_claimable_condition)
    )
    next_available_at = db.scalar(
        select(func.min(BackgroundTask.available_at)).where(
            BackgroundTask.status.in_(["pending", "retry_wait"]),
            BackgroundTask.available_at > generated_at_value,
        )
    )
    next_lease_expires_at = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(
            BackgroundTask.status == "leased",
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at > generated_at_value,
        )
    )
    settings = get_settings()
    return AdminBackgroundTaskQueueReport(
        generated_at=generated_at,
        total_count=sum(by_status.values()),
        ready_count=ready_count + stale_claimable_count,
        leased_count=by_status.get("leased", 0),
        retry_wait_count=by_status.get("retry_wait", 0),
        succeeded_count=by_status.get("succeeded", 0),
        dead_letter_count=by_status.get("dead_letter", 0),
        cancelled_count=by_status.get("cancelled", 0),
        stale_lease_count=stale_lease_count,
        by_task_type=by_task_type,
        by_status=by_status,
        oldest_ready_at=_oldest_datetime([oldest_pending_ready, oldest_stale_ready]),
        next_available_at=next_available_at,
        next_lease_expires_at=next_lease_expires_at,
        policy={
            "queue_backend": "database",
            "execution_mode": "hybrid_domain_ledgers",
            "worker_enabled": settings.background_task_worker_enabled,
            "lease_seconds": settings.background_task_worker_lease_seconds,
            "batch_size": settings.background_task_worker_batch_size,
            "payload_redacted": True,
            "lease_token_returned": False,
        },
    )


@router.get("/background-tasks/{task_id}", response_model=AdminBackgroundTaskRead)
def get_background_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    return _admin_background_task_read(task)


@router.get("/background-tasks/{task_id}/attempts", response_model=list[AdminBackgroundTaskAttemptRead])
def list_background_task_attempts(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdminBackgroundTaskAttemptRead]:
    _require_admin(current_user)
    if db.get(BackgroundTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    attempts = list(
        db.scalars(
            select(BackgroundTaskAttempt)
            .where(BackgroundTaskAttempt.task_id == task_id)
            .order_by(BackgroundTaskAttempt.attempt_number.desc())
        ).all()
    )
    return [_admin_background_task_attempt_read(attempt) for attempt in attempts]


@router.post("/background-tasks/{task_id}/retry", response_model=AdminBackgroundTaskRead)
def retry_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = retry_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.retry",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
            "attempt_count": task.attempt_count,
            "max_attempts": task.max_attempts,
        },
    )
    db.commit()
    return _admin_background_task_read(task)


@router.post("/background-tasks/{task_id}/cancel", response_model=AdminBackgroundTaskRead)
def cancel_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = cancel_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.cancel",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
        },
    )
    db.commit()
    return _admin_background_task_read(task)


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.get("/audit-logs/export", response_model=AuditLogExport)
def export_audit_logs(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    include_snapshot: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogExport:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    items = [_audit_log_export_item(log, include_snapshot=include_snapshot) for log in logs]
    truncated = total > len(logs)
    exported_at = datetime.now(UTC)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.export",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_export_snapshot(
            export_format="json",
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
            include_snapshot=include_snapshot,
            limit=limit,
            total=total,
            exported_count=len(logs),
            truncated=truncated,
            exported_at=exported_at,
        ),
    )
    db.commit()
    return AuditLogExport(
        items=items,
        total=total,
        limit=limit,
        truncated=truncated,
        include_snapshot=include_snapshot,
        exported_at=exported_at,
    )


@router.get("/audit-logs/export.csv")
def export_audit_logs_csv(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    include_snapshot: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    items = [_audit_log_export_item(log, include_snapshot=include_snapshot) for log in logs]
    truncated = total > len(logs)
    exported_at = datetime.now(UTC)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.export",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_export_snapshot(
            export_format="csv",
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
            include_snapshot=include_snapshot,
            limit=limit,
            total=total,
            exported_count=len(logs),
            truncated=truncated,
            exported_at=exported_at,
        ),
    )
    db.commit()
    return Response(
        content=_audit_log_csv(items),
        media_type="text/csv; charset=utf-8",
        headers=_audit_log_csv_headers(
            total=total,
            limit=limit,
            truncated=truncated,
            include_snapshot=include_snapshot,
            exported_at=exported_at,
        ),
    )


@router.get("/audit-logs/report", response_model=AuditLogReport)
def report_audit_logs(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogReport:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    generated_at = datetime.now(UTC)
    report = _audit_log_report(
        db,
        statement=statement,
        filters=_audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.report",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_report_snapshot(report, report_format="json"),
    )
    db.commit()
    return report


@router.get("/audit-logs/report.csv")
def report_audit_logs_csv(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    generated_at = datetime.now(UTC)
    report = _audit_log_report(
        db,
        statement=statement,
        filters=_audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.report",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_report_snapshot(report, report_format="csv"),
    )
    db.commit()
    return Response(
        content=_audit_log_report_csv(report),
        media_type="text/csv; charset=utf-8",
        headers=_audit_log_report_csv_headers(report),
    )


@router.get("/audit-logs/retention-plan", response_model=AuditLogRetentionPlan)
def plan_audit_log_retention(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    before_at: datetime | None = Query(default=None, alias="before"),
    retention_days: int | None = Query(default=None, ge=1, le=3650),
    warning_days: int = Query(default=30, ge=0, le=3650),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogRetentionPlan:
    _require_admin(current_user)
    if before_at is not None and retention_days is not None:
        raise HTTPException(status_code=422, detail="before and retention_days cannot be used together")
    settings = get_settings()
    generated_at = datetime.now(UTC)
    policy_retention_days = retention_days or settings.audit_log_retention_days
    if before_at is not None:
        cutoff_at = before_at
        policy_source: Literal["config", "query", "before"] = "before"
        policy_days: int | None = None
    else:
        cutoff_at = generated_at - timedelta(days=policy_retention_days)
        policy_source = "query" if retention_days is not None else "config"
        policy_days = policy_retention_days
    expiring_soon_cutoff_at = cutoff_at + timedelta(days=warning_days)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _audit_log_filters(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    plan = _audit_log_retention_plan(
        db,
        statement=statement,
        filters=filters,
        policy=AuditLogRetentionPolicy(
            retention_days=policy_days,
            warning_days=warning_days,
            cutoff_at=cutoff_at,
            expiring_soon_cutoff_at=expiring_soon_cutoff_at,
            source=policy_source,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.retention_plan",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_retention_snapshot(plan),
    )
    db.commit()
    return plan


@router.get("/audit-logs/chain-integrity", response_model=AuditLogChainVerification)
def verify_audit_log_chain_integrity(
    request: Request,
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=5000, ge=1, le=20000),
    issue_limit: int = Query(default=50, ge=0, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogChainVerification:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=None,
        action=None,
        resource_type=None,
        resource_id=None,
        school_id=None,
        class_id=None,
        event_result=None,
        failure_reason=None,
        request_id=None,
        from_at=from_at,
        to_at=to_at,
    ).order_by(None)
    statement = statement.order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    generated_at = datetime.now(UTC)
    report = _audit_log_chain_verification(
        logs=logs,
        total=total,
        filters=_audit_log_filters(
            actor_user_id=None,
            action=None,
            resource_type=None,
            resource_id=None,
            school_id=None,
            class_id=None,
            event_result=None,
            failure_reason=None,
            request_id=None,
            from_at=from_at,
            to_at=to_at,
        ),
        limit=limit,
        issue_limit=issue_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.chain_integrity",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_chain_verification_snapshot(report),
    )
    db.commit()
    return report


@router.get("/audit-logs/high-frequency", response_model=AuditLogFrequencyReport)
def report_audit_log_high_frequency(
    request: Request,
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    window_hours: int = Query(default=24, ge=1, le=24 * 31),
    min_count: int = Query(default=10, ge=1, le=10000),
    min_failure_count: int = Query(default=3, ge=0, le=10000),
    min_failure_ratio: float = Query(default=0.5, ge=0, le=1),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogFrequencyReport:
    _require_admin(current_user)
    generated_at = datetime.now(UTC)
    effective_to = to_at or generated_at
    effective_from = from_at or effective_to - timedelta(hours=window_hours)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=effective_from,
        to_at=effective_to,
    )
    filters = _audit_log_filters(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    report = _audit_log_frequency_report(
        db,
        statement=statement,
        filters=filters,
        effective_from=effective_from,
        effective_to=effective_to,
        window_hours=window_hours,
        min_count=min_count,
        min_failure_count=min_failure_count,
        min_failure_ratio=min_failure_ratio,
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.high_frequency",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_frequency_snapshot(report),
    )
    db.commit()
    return report


@router.get("/submissions/pending", response_model=AdminPendingSubmissionQueue)
def list_pending_submissions(
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    assignment_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    status_filter: Literal["submitted", "returned", "graded"] | None = Query(default=None, alias="status"),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    order_by: Literal["submitted_at", "graded_at", "due_at"] = Query(default="submitted_at"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminPendingSubmissionQueue:
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    scoped_class_ids: list[int] | None = None
    if current_user.role == "admin":
        _validate_pending_submission_filters(db, school_id, class_id, course_id, assignment_id)
    elif current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Pending submissions require class teacher scope")
    elif status_filter == "graded":
        raise HTTPException(status_code=403, detail="Graded submission queue requires admin role")
    elif class_id is not None:
        require_class_teacher_or_admin_by_id(
            db,
            current_user,
            class_id,
            detail="Pending submissions require class teacher scope",
        )
        scoped_class_ids = [class_id]
    else:
        scoped_class_ids = teacher_class_ids(db, current_user.id)

    criteria = _pending_submission_criteria(
        school_id=school_id,
        class_id=class_id,
        scoped_class_ids=scoped_class_ids,
        course_id=course_id,
        assignment_id=assignment_id,
        student_id=student_id,
        status_filter=status_filter,
        from_at=from_at,
        to_at=to_at,
    )
    total = _pending_submission_total(db, criteria)
    order_column = {
        "submitted_at": Submission.submitted_at,
        "graded_at": Submission.graded_at,
        "due_at": Assignment.due_at,
    }[order_by]
    order_clause = order_column.desc() if order == "desc" else order_column.asc()
    rows = db.execute(
        select(Submission, Assignment, Course, ClassGroup, User)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .outerjoin(ClassGroup, ClassGroup.id == Submission.class_id)
        .join(User, User.id == Submission.student_id)
        .where(*criteria)
        .order_by(order_clause, Submission.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    items = [
        AdminPendingSubmissionRead(
            id=submission.id,
            assignment_id=assignment.id,
            assignment_title=assignment.title,
            student_id=student.id,
            student_username=student.username,
            student_display_name=student.display_name,
            class_id=submission.class_id,
            class_name=class_group.name if class_group is not None else None,
            school_id=course.school_id,
            course_id=course.id,
            course_title=course.title,
            status=submission.status,
            score=submission.score,
            submitted_at=submission.submitted_at,
            graded_at=submission.graded_at,
            due_at=assignment.due_at,
        )
        for submission, assignment, course, class_group, student in rows
    ]
    next_offset = _next_offset(total, offset, len(items))
    return AdminPendingSubmissionQueue(items=items, total=total, limit=limit, offset=offset, next_offset=next_offset)


@router.get("/bugs", response_model=BugRecordPage)
def list_bug_records(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecordPage:
    _require_admin(current_user)
    statement = select(BugRecord).order_by(BugRecord.id)
    if status_filter is not None:
        statement = statement.where(BugRecord.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = _contains_pattern(q)
        statement = statement.where(
            or_(
                BugRecord.title.ilike(pattern, escape="~"),
                BugRecord.category.ilike(pattern, escape="~"),
                BugRecord.source.ilike(pattern, escape="~"),
                BugRecord.external_issue_provider.ilike(pattern, escape="~"),
                BugRecord.external_issue_id.ilike(pattern, escape="~"),
                BugRecord.external_issue_url.ilike(pattern, escape="~"),
                BugRecord.evidence.ilike(pattern, escape="~"),
                BugRecord.notes.ilike(pattern, escape="~"),
            )
        )
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return BugRecordPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.post("/bugs", response_model=BugRecordRead, status_code=status.HTTP_201_CREATED)
def create_bug_record(
    payload: BugRecordCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecord:
    _require_admin(current_user)
    title = require_trimmed_text(payload.title, "Bug title is required")
    category = require_trimmed_text(payload.category, "Bug category is required")
    bug = BugRecord(
        title=title,
        category=category,
        severity=payload.severity,
        status=payload.status,
        source=_strip_optional(payload.source),
        external_issue_provider=_normalize_issue_provider(payload.external_issue_provider),
        external_issue_id=_strip_optional(payload.external_issue_id),
        external_issue_url=_strip_optional(payload.external_issue_url),
        evidence=_strip_optional(payload.evidence),
        notes=_strip_optional(payload.notes),
    )
    db.add(bug)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="admin.bug.create",
        resource_type="bug_record",
        resource_id=bug.id,
        event_result="success",
        request=request,
        snapshot={"after": _bug_snapshot(bug)},
    )
    db.commit()
    db.refresh(bug)
    return bug


@router.patch("/bugs/{bug_id}", response_model=BugRecordRead)
def update_bug_record(
    bug_id: int,
    payload: BugRecordUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecord:
    _require_admin(current_user)
    bug = db.get(BugRecord, bug_id)
    if bug is None:
        raise HTTPException(status_code=404, detail="Bug record not found")

    before = _bug_snapshot(bug)
    authoritative_before = _bug_authority_snapshot(bug)
    for field in (
        "title",
        "category",
        "source",
        "external_issue_provider",
        "external_issue_id",
        "external_issue_url",
        "evidence",
        "notes",
    ):
        value = getattr(payload, field)
        if value is not None:
            if field == "title":
                value = require_trimmed_text(value, "Bug title is required")
            elif field == "category":
                value = require_trimmed_text(value, "Bug category is required")
            elif field == "external_issue_provider":
                value = _normalize_issue_provider(value)
            else:
                value = _strip_optional(value)
            setattr(bug, field, value)
    if payload.severity is not None:
        bug.severity = payload.severity
    if payload.status is not None:
        bug.status = payload.status
    if _bug_authority_snapshot(bug) != authoritative_before:
        bug.external_sync_revision += 1

    after = _bug_snapshot(bug)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.bug.update",
        resource_type="bug_record",
        resource_id=bug.id,
        event_result="success",
        request=request,
        snapshot=_change_snapshot(before, after),
    )
    db.commit()
    db.refresh(bug)
    return bug


@router.get("/bugs/external-sync/posture")
def get_bug_external_sync_posture(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_admin(current_user)
    return external_issue_sync_posture(get_settings())


@router.get(
    "/bugs/{bug_id}/external-sync-operations",
    response_model=BugExternalSyncOperationPage,
)
def list_bug_external_sync_operations(
    bug_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncOperationPage:
    _require_admin(current_user)
    if db.get(BugRecord, bug_id) is None:
        raise HTTPException(status_code=404, detail="Bug record not found")
    statement = (
        select(BugExternalSyncOperation)
        .where(BugExternalSyncOperation.bug_record_id == bug_id)
        .order_by(BugExternalSyncOperation.id.desc())
    )
    total = _statement_count(db, statement)
    operations = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return BugExternalSyncOperationPage(
        items=[BugExternalSyncOperationRead(**bug_external_sync_operation_read(item)) for item in operations],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(operations)),
    )


@router.post("/bugs/{bug_id}/external-sync/create", response_model=BugExternalSyncResponse)
def create_bug_external_issue(
    bug_id: int,
    payload: BugExternalSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="create",
        execute=lambda: create_external_issue_for_bug(
            db,
            bug_id=bug_id,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


@router.post("/bugs/{bug_id}/external-sync/status", response_model=BugExternalSyncResponse)
def sync_bug_external_issue_status(
    bug_id: int,
    payload: BugExternalSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="status",
        execute=lambda: sync_external_issue_status_for_bug(
            db,
            bug_id=bug_id,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


@router.post("/bugs/{bug_id}/external-sync/comments", response_model=BugExternalSyncResponse)
def sync_bug_external_issue_comment(
    bug_id: int,
    payload: BugExternalCommentSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    normalized_comment = payload.comment.strip()
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="comment",
        audit_context={
            "comment_sha256": sha256(normalized_comment.encode("utf-8")).hexdigest(),
            "comment_length": len(normalized_comment),
        },
        execute=lambda: sync_external_issue_comment_for_bug(
            db,
            bug_id=bug_id,
            comment=normalized_comment,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


def _run_bug_external_sync_action(
    db: Session,
    *,
    bug_id: int,
    actor: User,
    request: Request,
    operation: str,
    execute: Any,
    audit_context: dict[str, Any] | None = None,
) -> BugExternalSyncResponse:
    action = f"admin.bug.external_sync.{operation}"
    try:
        result: BugExternalSyncResult = execute()
    except BugExternalSyncError as exc:
        db.rollback()
        if exc.code == "bug_record_not_found":
            raise HTTPException(status_code=404, detail="Bug record not found") from None
        record_audit_log(
            db,
            actor=actor,
            action=action,
            resource_type="bug_record",
            resource_id=bug_id,
            event_result="failure",
            failure_reason=exc.code,
            request=request,
            snapshot={
                "operation": operation,
                "operation_id": exc.operation_id,
                "retryable": exc.retryable,
                "ambiguous": exc.ambiguous,
                **(audit_context or {}),
            },
        )
        db.commit()
        raise HTTPException(
            status_code=_bug_external_sync_error_status(exc),
            detail={
                "code": exc.code,
                "retryable": exc.retryable,
                "ambiguous": exc.ambiguous,
                "operation_id": exc.operation_id,
                "posture": external_issue_sync_posture(get_settings()),
            },
        ) from None
    operation_read = bug_external_sync_operation_read(result.operation)
    record_audit_log(
        db,
        actor=actor,
        action=action,
        resource_type="bug_record",
        resource_id=bug_id,
        event_result="success",
        request=request,
        snapshot={
            "operation": operation,
            "operation_id": result.operation.id,
            "operation_status": result.operation.status,
            "provider": result.operation.provider,
            "external_issue_id": result.operation.external_issue_id,
            "external_state": result.operation.external_state,
            "recovered": result.recovered,
            **(audit_context or {}),
        },
    )
    db.commit()
    db.refresh(result.bug)
    return BugExternalSyncResponse(
        bug=result.bug,
        operation=BugExternalSyncOperationRead(**operation_read),
        recovered=result.recovered,
        posture=external_issue_sync_posture(get_settings()),
    )


def _bug_external_sync_error_status(error: BugExternalSyncError) -> int:
    if error.code in {
        "external_issue_comment_empty",
        "external_issue_comment_sensitive",
        "external_issue_title_sensitive",
    }:
        return 422
    if error.ambiguous or error.code in {
        "external_issue_already_bound",
        "external_issue_binding_invalid",
        "external_issue_not_bound",
        "external_issue_provider_mismatch",
        "external_issue_sync_ambiguous",
        "external_issue_sync_disabled",
        "external_issue_sync_not_configured",
    }:
        return 409
    return 502


def _get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _admin_background_task_read(task: BackgroundTask) -> AdminBackgroundTaskRead:
    now_at = datetime.now(UTC)
    lease_active = (
        task.status == "leased"
        and task.lease_expires_at is not None
        and _naive_utc(task.lease_expires_at) > _naive_utc(now_at)
    )
    return AdminBackgroundTaskRead(
        id=task.id,
        task_type=task.task_type,
        source_type=task.source_type,
        source_id=task.source_id,
        status=task.status,
        priority=task.priority,
        idempotency_key_prefix=task.idempotency_key[:12],
        payload_redacted=True,
        result_summary=dict(task.result_summary_json or {}),
        available_at=task.available_at,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        last_error_code=task.last_error_code,
        lease_owner=task.lease_owner,
        lease_active=lease_active,
        lease_expires_at=task.lease_expires_at,
        heartbeat_at=task.heartbeat_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_by_user_id=task.created_by_user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _admin_background_task_attempt_read(
    attempt: BackgroundTaskAttempt,
) -> AdminBackgroundTaskAttemptRead:
    return AdminBackgroundTaskAttemptRead(
        id=attempt.id,
        task_id=attempt.task_id,
        attempt_number=attempt.attempt_number,
        worker_id=attempt.worker_id,
        status=attempt.status,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_code=attempt.error_code,
        retryable=attempt.retryable,
        result_summary=dict(attempt.result_summary_json or {}),
    )


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
        entry for entry in pending_review if _naive_utc(entry.last_seen_at) <= _naive_utc(stale_before)
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
    return entry.available_at is None or _naive_utc(entry.available_at) <= _naive_utc(now_at)


def _admin_alert_outbox_entry_expired(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return entry.expires_at is not None and _naive_utc(entry.expires_at) <= _naive_utc(now_at)


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
            _naive_utc(entry.available_at or entry.last_seen_at),
            _naive_utc(entry.last_seen_at),
            entry.id,
        ),
    )


def _oldest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return min(items, key=_naive_utc) if items else None


def _latest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return max(items, key=_naive_utc) if items else None


def _pending_submission_criteria(
    *,
    school_id: int | None,
    class_id: int | None,
    scoped_class_ids: list[int] | None = None,
    course_id: int | None,
    assignment_id: int | None,
    student_id: int | None,
    status_filter: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> list[Any]:
    criteria: list[Any] = []
    if status_filter is None:
        criteria.append(Submission.status.in_(PENDING_SUBMISSION_STATUSES))
    else:
        criteria.append(Submission.status == status_filter)
    if school_id is not None:
        criteria.append(Course.school_id == school_id)
    if class_id is not None:
        criteria.append(Submission.class_id == class_id)
    if scoped_class_ids is not None:
        criteria.append(Submission.class_id.in_(scoped_class_ids))
    if course_id is not None:
        criteria.append(Course.id == course_id)
    if assignment_id is not None:
        criteria.append(Submission.assignment_id == assignment_id)
    if student_id is not None:
        criteria.append(Submission.student_id == student_id)
    if from_at is not None:
        criteria.append(Submission.submitted_at >= from_at)
    if to_at is not None:
        criteria.append(Submission.submitted_at <= to_at)
    return criteria


def _pending_submission_total(db: Session, criteria: list[Any]) -> int:
    return int(
        db.scalar(
            select(func.count(Submission.id))
            .select_from(Submission)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
            .join(Course, Course.id == CourseUnit.course_id)
            .where(*criteria)
        )
        or 0
    )


def _validate_pending_submission_filters(
    db: Session,
    school_id: int | None,
    class_id: int | None,
    course_id: int | None,
    assignment_id: int | None,
) -> None:
    if school_id is not None:
        _get_school(db, school_id)
    class_group = _get_class(db, class_id) if class_id is not None else None
    course = db.get(Course, course_id) if course_id is not None else None
    if course_id is not None and course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    assignment_course_id = None
    assignment_school_id = None
    if assignment_id is not None:
        assignment_course_id, assignment_school_id = _assignment_course_refs(db, assignment_id)

    if class_group is not None and school_id is not None and class_group.school_id != school_id:
        raise HTTPException(status_code=422, detail="Class does not belong to requested school")
    if course is not None and school_id is not None and course.school_id != school_id:
        raise HTTPException(status_code=422, detail="Course does not belong to requested school")
    if course is not None and class_group is not None and course.school_id != class_group.school_id:
        raise HTTPException(status_code=422, detail="Course does not belong to requested class school")
    if assignment_school_id is not None and school_id is not None and assignment_school_id != school_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested school")
    if assignment_course_id is not None and course_id is not None and assignment_course_id != course_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested course")
    if assignment_school_id is not None and class_group is not None and assignment_school_id != class_group.school_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested class school")


def _assignment_course_refs(db: Session, assignment_id: int) -> tuple[int, int]:
    row = db.execute(
        select(Course.id.label("course_id"), Course.school_id.label("school_id"))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .where(Assignment.id == assignment_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return int(row.course_id), int(row.school_id)


def _divide(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _percent(numerator: int | float, denominator: int | float) -> float:
    return round(_divide(numerator, denominator) * 100, 2)


def _audit_log_statement(
    *,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if actor_user_id is not None:
        statement = statement.where(AuditLog.actor_user_id == actor_user_id)
    if action is not None:
        statement = statement.where(AuditLog.action == action.strip())
    if resource_type is not None:
        statement = statement.where(AuditLog.resource_type == resource_type.strip())
    if resource_id is not None:
        statement = statement.where(AuditLog.resource_id == resource_id.strip())
    if school_id is not None:
        statement = statement.where(AuditLog.school_id == school_id)
    if class_id is not None:
        statement = statement.where(AuditLog.class_id == class_id)
    if event_result is not None:
        statement = statement.where(AuditLog.event_result == event_result.strip())
    if failure_reason is not None:
        statement = statement.where(AuditLog.failure_reason == failure_reason.strip())
    if request_id is not None:
        statement = statement.where(AuditLog.request_id == request_id.strip())
    if from_at is not None:
        statement = statement.where(AuditLog.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(AuditLog.created_at <= to_at)
    return statement


def _audit_log_export_item(log: AuditLog, *, include_snapshot: bool) -> AuditLogExportItem:
    data = AuditLogRead.model_validate(log).model_dump()
    if not include_snapshot:
        data["snapshot_json"] = None
    return AuditLogExportItem(**data)


def _audit_log_csv(items: list[AuditLogExportItem]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_AUDIT_LOG_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        data = item.model_dump(mode="json")
        writer.writerow({field: _audit_log_csv_value(data.get(field)) for field in _AUDIT_LOG_CSV_FIELDS})
    return buffer.getvalue()


def _audit_log_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{text}"
    return text


def _audit_log_csv_headers(
    *,
    total: int,
    limit: int,
    truncated: bool,
    include_snapshot: bool,
    exported_at: datetime,
) -> dict[str, str]:
    exported_at_text = exported_at.isoformat()
    filename_stamp = exported_at.strftime("%Y%m%dT%H%M%SZ")
    return {
        "Content-Disposition": f'attachment; filename="audit-logs-{filename_stamp}.csv"',
        "X-Audit-Export-Total": str(total),
        "X-Audit-Export-Limit": str(limit),
        "X-Audit-Export-Truncated": str(truncated).lower(),
        "X-Audit-Export-Include-Snapshot": str(include_snapshot).lower(),
        "X-Audit-Exported-At": exported_at_text,
    }


def _audit_log_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogReport:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    return AuditLogReport(
        total=total,
        bucket_limit=bucket_limit,
        generated_at=generated_at,
        filters=filters,
        by_action=_audit_log_action_report(db, source, bucket_limit),
        by_resource_type=_audit_log_report_buckets(db, source, "resource_type", bucket_limit),
        by_actor_role=_audit_log_report_buckets(db, source, "actor_role", bucket_limit),
        by_event_result=_audit_log_report_buckets(db, source, "event_result", bucket_limit),
        by_failure_reason=_audit_log_report_buckets(db, source, "failure_reason", bucket_limit),
    )


def _audit_log_action_report(db: Session, source: Any, bucket_limit: int) -> list[AuditLogActionReport]:
    rows = db.execute(
        select(
            source.c.action,
            source.c.event_result,
            func.count().label("total"),
            func.max(source.c.created_at).label("latest_at"),
        ).group_by(source.c.action, source.c.event_result)
    ).all()
    buckets: dict[str, dict[str, Any]] = {}
    for action, event_result, total, latest_at in rows:
        action_key = str(action)
        bucket = buckets.setdefault(
            action_key,
            {"total": 0, "success": 0, "failure": 0, "other": 0, "latest_at": None},
        )
        count = int(total)
        bucket["total"] += count
        if event_result == "success":
            bucket["success"] += count
        elif event_result == "failure":
            bucket["failure"] += count
        else:
            bucket["other"] += count
        if latest_at is not None and (bucket["latest_at"] is None or latest_at > bucket["latest_at"]):
            bucket["latest_at"] = latest_at

    ordered = sorted(buckets.items(), key=lambda item: (-int(item[1]["total"]), item[0]))[:bucket_limit]
    return [
        AuditLogActionReport(
            action=action,
            total=int(values["total"]),
            success=int(values["success"]),
            failure=int(values["failure"]),
            other=int(values["other"]),
            latest_at=values["latest_at"],
        )
        for action, values in ordered
    ]


def _audit_log_report_buckets(db: Session, source: Any, column_name: str, bucket_limit: int) -> list[AuditLogReportBucket]:
    column = getattr(source.c, column_name)
    count_expr = func.count().label("total")
    rows = db.execute(
        select(column, count_expr).group_by(column).order_by(count_expr.desc(), column).limit(bucket_limit)
    ).all()
    return [AuditLogReportBucket(key=str(key) if key is not None else None, total=int(total)) for key, total in rows]


def _audit_log_report_csv(report: AuditLogReport) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_AUDIT_LOG_REPORT_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in report.by_action:
        writer.writerow(
            {
                "section": "action",
                "key": _audit_log_csv_value(item.action),
                "total": item.total,
                "success": item.success,
                "failure": item.failure,
                "other": item.other,
                "latest_at": item.latest_at.isoformat() if item.latest_at is not None else "",
            }
        )
    for section, buckets in {
        "resource_type": report.by_resource_type,
        "actor_role": report.by_actor_role,
        "event_result": report.by_event_result,
        "failure_reason": report.by_failure_reason,
    }.items():
        for bucket in buckets:
            writer.writerow(
                {
                    "section": section,
                    "key": _audit_log_csv_value(bucket.key),
                    "total": bucket.total,
                    "success": "",
                    "failure": "",
                    "other": "",
                    "latest_at": "",
                }
            )
    return buffer.getvalue()


def _audit_log_report_csv_headers(report: AuditLogReport) -> dict[str, str]:
    filename_stamp = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    return {
        "Content-Disposition": f'attachment; filename="audit-log-report-{filename_stamp}.csv"',
        "X-Audit-Report-Total": str(report.total),
        "X-Audit-Report-Bucket-Limit": str(report.bucket_limit),
        "X-Audit-Report-Generated-At": report.generated_at.isoformat(),
    }


def _audit_log_report_snapshot(report: AuditLogReport, *, report_format: Literal["json", "csv"]) -> dict[str, Any]:
    return {
        "format": report_format,
        "filters": report.filters,
        "total": report.total,
        "bucket_limit": report.bucket_limit,
        "action_bucket_count": len(report.by_action),
        "resource_type_bucket_count": len(report.by_resource_type),
        "actor_role_bucket_count": len(report.by_actor_role),
        "event_result_bucket_count": len(report.by_event_result),
        "failure_reason_bucket_count": len(report.by_failure_reason),
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_retention_plan(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    policy: AuditLogRetentionPolicy,
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogRetentionPlan:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    archive_candidates = int(
        db.scalar(select(func.count()).select_from(source).where(source.c.created_at <= policy.cutoff_at)) or 0
    )
    expiring_soon = int(
        db.scalar(
            select(func.count())
            .select_from(source)
            .where(source.c.created_at > policy.cutoff_at, source.c.created_at <= policy.expiring_soon_cutoff_at)
        )
        or 0
    )
    oldest_at, newest_at = db.execute(
        select(func.min(source.c.created_at), func.max(source.c.created_at)).select_from(source)
    ).one()
    first_candidate = db.execute(
        select(source.c.id, source.c.prev_hash, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= policy.cutoff_at)
        .order_by(source.c.created_at.asc(), source.c.id.asc())
        .limit(1)
    ).first()
    last_candidate = db.execute(
        select(source.c.id, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= policy.cutoff_at)
        .order_by(source.c.created_at.desc(), source.c.id.desc())
        .limit(1)
    ).first()
    return AuditLogRetentionPlan(
        generated_at=generated_at,
        filters=filters,
        capabilities={
            "archive_export": False,
            "delete": False,
            "worm": False,
            "external_anchor": False,
        },
        policy=policy,
        summary=AuditLogRetentionSummary(
            total=total,
            retained=max(total - archive_candidates, 0),
            archive_candidates=archive_candidates,
            expiring_soon=expiring_soon,
            oldest_at=oldest_at,
            newest_at=newest_at,
            first_candidate_id=int(first_candidate.id) if first_candidate is not None else None,
            last_candidate_id=int(last_candidate.id) if last_candidate is not None else None,
            chain_start_prev_hash=first_candidate.prev_hash if first_candidate is not None else None,
            chain_start_current_hash=first_candidate.current_hash if first_candidate is not None else None,
            chain_end_current_hash=last_candidate.current_hash if last_candidate is not None else None,
        ),
        bucket_limit=bucket_limit,
        by_action=_audit_log_retention_buckets(db, source, policy.cutoff_at, "action", bucket_limit),
        by_resource_type=_audit_log_retention_buckets(db, source, policy.cutoff_at, "resource_type", bucket_limit),
        by_event_result=_audit_log_retention_buckets(db, source, policy.cutoff_at, "event_result", bucket_limit),
    )


def _audit_log_retention_buckets(
    db: Session,
    source: Any,
    cutoff_at: datetime,
    column_name: str,
    bucket_limit: int,
) -> list[AuditLogReportBucket]:
    column = getattr(source.c, column_name)
    count_expr = func.count().label("total")
    rows = db.execute(
        select(column, count_expr)
        .select_from(source)
        .where(source.c.created_at <= cutoff_at)
        .group_by(column)
        .order_by(count_expr.desc(), column)
        .limit(bucket_limit)
    ).all()
    return [AuditLogReportBucket(key=str(key) if key is not None else None, total=int(total)) for key, total in rows]


def _audit_log_retention_snapshot(plan: AuditLogRetentionPlan) -> dict[str, Any]:
    return {
        "format": "retention_plan",
        "filters": plan.filters,
        "capabilities": plan.capabilities,
        "policy": plan.policy.model_dump(mode="json"),
        "total": plan.summary.total,
        "archive_candidates": plan.summary.archive_candidates,
        "expiring_soon": plan.summary.expiring_soon,
        "bucket_limit": plan.bucket_limit,
        "action_bucket_count": len(plan.by_action),
        "resource_type_bucket_count": len(plan.by_resource_type),
        "event_result_bucket_count": len(plan.by_event_result),
        "first_candidate_id": plan.summary.first_candidate_id,
        "last_candidate_id": plan.summary.last_candidate_id,
        "chain_start_prev_hash": plan.summary.chain_start_prev_hash,
        "chain_start_current_hash": plan.summary.chain_start_current_hash,
        "chain_end_current_hash": plan.summary.chain_end_current_hash,
        "generated_at": plan.generated_at.isoformat(),
    }


def _audit_log_chain_verification(
    *,
    logs: list[AuditLog],
    total: int,
    filters: dict[str, Any],
    limit: int,
    issue_limit: int,
    generated_at: datetime,
) -> AuditLogChainVerification:
    chain_report = verify_audit_log_chain(logs, issue_limit=issue_limit)
    first = logs[0] if logs else None
    last = logs[-1] if logs else None
    truncated = total > chain_report["scanned_count"]
    status = chain_report["status"]
    if truncated and status == "valid":
        status = "partial"
    return AuditLogChainVerification(
        generated_at=generated_at,
        filters=filters,
        capabilities={
            "repair": False,
            "delete": False,
            "worm": False,
            "external_anchor": False,
        },
        algorithm=chain_report["algorithm"],
        chain_version=chain_report["chain_version"],
        status=status,
        valid=status == "valid",
        total=total,
        scanned_count=chain_report["scanned_count"],
        limit=limit,
        truncated=truncated,
        issue_limit=issue_limit,
        issue_count=chain_report["issue_count"],
        issues_truncated=chain_report["issues_truncated"],
        null_current_hash_count=chain_report["null_current_hash_count"],
        current_hash_mismatch_count=chain_report["current_hash_mismatch_count"],
        prev_hash_mismatch_count=chain_report["prev_hash_mismatch_count"],
        first_id=first.id if first is not None else None,
        last_id=last.id if last is not None else None,
        chain_start_prev_hash=first.prev_hash if first is not None else None,
        chain_start_current_hash=first.current_hash if first is not None else None,
        chain_end_current_hash=last.current_hash if last is not None else None,
        issues=chain_report["issues"],
    )


def _audit_log_chain_verification_snapshot(report: AuditLogChainVerification) -> dict[str, Any]:
    return {
        "format": "chain_integrity",
        "filters": report.filters,
        "capabilities": report.capabilities,
        "status": report.status,
        "valid": report.valid,
        "total": report.total,
        "scanned_count": report.scanned_count,
        "limit": report.limit,
        "truncated": report.truncated,
        "issue_count": report.issue_count,
        "issues_truncated": report.issues_truncated,
        "null_current_hash_count": report.null_current_hash_count,
        "current_hash_mismatch_count": report.current_hash_mismatch_count,
        "prev_hash_mismatch_count": report.prev_hash_mismatch_count,
        "first_id": report.first_id,
        "last_id": report.last_id,
        "chain_start_prev_hash": report.chain_start_prev_hash,
        "chain_start_current_hash": report.chain_start_current_hash,
        "chain_end_current_hash": report.chain_end_current_hash,
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_frequency_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    effective_from: datetime,
    effective_to: datetime,
    window_hours: int,
    min_count: int,
    min_failure_count: int,
    min_failure_ratio: float,
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogFrequencyReport:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    minimum_activity = max(1, min(min_count, min_failure_count or min_count))
    candidates: list[AuditLogFrequencyCandidate] = []
    for dimension, columns in _audit_log_frequency_dimensions(source):
        candidates.extend(
            _audit_log_frequency_candidates(
                db,
                source=source,
                dimension=dimension,
                columns=columns,
                minimum_activity=minimum_activity,
                min_count=min_count,
                min_failure_count=min_failure_count,
                min_failure_ratio=min_failure_ratio,
            )
        )
    candidates.sort(
        key=lambda candidate: (
            -candidate.total,
            -candidate.failure,
            candidate.dimension,
            candidate.key or "",
            candidate.action or "",
        )
    )
    candidates = candidates[:bucket_limit]
    return AuditLogFrequencyReport(
        total=total,
        generated_at=generated_at,
        filters=filters,
        window={
            "from": effective_from.isoformat(),
            "to": effective_to.isoformat(),
            "window_hours": window_hours,
        },
        thresholds={
            "min_count": min_count,
            "min_failure_count": min_failure_count,
            "min_failure_ratio": min_failure_ratio,
            "bucket_limit": bucket_limit,
        },
        candidates=candidates,
    )


def _audit_log_frequency_dimensions(source: Any) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("action", {"key": source.c.action, "action": source.c.action}),
        (
            "actor_action",
            {
                "key": source.c.actor_user_id,
                "actor_user_id": source.c.actor_user_id,
                "actor_role": source.c.actor_role,
                "action": source.c.action,
            },
        ),
        (
            "ip_action",
            {
                "key": source.c.client_ip_hash,
                "action": source.c.action,
            },
        ),
        (
            "resource_action",
            {
                "key": source.c.resource,
                "resource_type": source.c.resource_type,
                "resource_id": source.c.resource_id,
                "school_id": source.c.school_id,
                "class_id": source.c.class_id,
                "action": source.c.action,
            },
        ),
        (
            "failure_reason",
            {
                "key": source.c.failure_reason,
                "failure_reason": source.c.failure_reason,
            },
        ),
    ]


def _audit_log_frequency_candidates(
    db: Session,
    *,
    source: Any,
    dimension: str,
    columns: dict[str, Any],
    minimum_activity: int,
    min_count: int,
    min_failure_count: int,
    min_failure_ratio: float,
) -> list[AuditLogFrequencyCandidate]:
    count_expr = func.count().label("total")
    success_expr = func.coalesce(func.sum(case((source.c.event_result == "success", 1), else_=0)), 0).label("success")
    failure_expr = func.coalesce(func.sum(case((source.c.event_result == "failure", 1), else_=0)), 0).label("failure")
    group_columns = list(dict.fromkeys(columns.values()))
    rows = db.execute(
        select(
            *[column.label(name) for name, column in columns.items()],
            count_expr,
            success_expr,
            failure_expr,
            func.count(func.distinct(source.c.actor_user_id)).label("distinct_actors"),
            func.count(func.distinct(source.c.client_ip_hash)).label("distinct_ip_hashes"),
            func.count(func.distinct(source.c.request_id)).label("distinct_request_ids"),
            func.min(source.c.created_at).label("first_at"),
            func.max(source.c.created_at).label("latest_at"),
        )
        .group_by(*group_columns)
        .having(count_expr >= minimum_activity)
    ).mappings()
    candidates: list[AuditLogFrequencyCandidate] = []
    for row in rows:
        total = int(row["total"])
        success = int(row["success"] or 0)
        failure = int(row["failure"] or 0)
        failure_ratio = _divide(failure, total)
        reasons: list[str] = []
        if total >= min_count:
            reasons.append("count_threshold")
        if min_failure_count > 0 and failure >= min_failure_count:
            reasons.append("failure_count_threshold")
        if min_failure_count > 0 and failure >= min_failure_count and failure_ratio >= min_failure_ratio:
            reasons.append("failure_ratio_threshold")
        if not reasons:
            continue
        candidates.append(
            AuditLogFrequencyCandidate(
                dimension=dimension,
                key=str(row["key"]) if row["key"] is not None else None,
                action=str(row["action"]) if row.get("action") is not None else None,
                actor_user_id=row.get("actor_user_id"),
                actor_role=row.get("actor_role"),
                resource_type=row.get("resource_type"),
                resource_id=row.get("resource_id"),
                school_id=row.get("school_id"),
                class_id=row.get("class_id"),
                failure_reason=row.get("failure_reason"),
                total=total,
                success=success,
                failure=failure,
                other=max(total - success - failure, 0),
                failure_ratio=failure_ratio,
                distinct_actors=int(row["distinct_actors"] or 0),
                distinct_ip_hashes=int(row["distinct_ip_hashes"] or 0),
                distinct_request_ids=int(row["distinct_request_ids"] or 0),
                first_at=row["first_at"],
                latest_at=row["latest_at"],
                reasons=reasons,
            )
        )
    return candidates


def _audit_log_frequency_snapshot(report: AuditLogFrequencyReport) -> dict[str, Any]:
    dimension_counts: dict[str, int] = {}
    for candidate in report.candidates:
        dimension_counts[candidate.dimension] = dimension_counts.get(candidate.dimension, 0) + 1
    return {
        "format": "high_frequency",
        "filters": report.filters,
        "window": report.window,
        "thresholds": report.thresholds,
        "total": report.total,
        "candidate_count": len(report.candidates),
        "dimension_counts": dimension_counts,
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_filters(
    *,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in {
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "school_id": school_id,
        "class_id": class_id,
        "event_result": event_result,
        "failure_reason": failure_reason,
        "request_id": request_id,
    }.items():
        if value is not None:
            filters[key] = value.strip() if isinstance(value, str) else value
    if from_at is not None:
        filters["from"] = from_at.isoformat()
    if to_at is not None:
        filters["to"] = to_at.isoformat()
    return filters


def _audit_log_export_snapshot(
    *,
    export_format: Literal["json", "csv"],
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    include_snapshot: bool,
    limit: int,
    total: int,
    exported_count: int,
    truncated: bool,
    exported_at: datetime,
) -> dict[str, Any]:
    return {
        "format": export_format,
        "filters": _audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        "include_snapshot": include_snapshot,
        "limit": limit,
        "total": total,
        "exported_count": exported_count,
        "truncated": truncated,
        "exported_at": exported_at.isoformat(),
    }


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalize_issue_provider(value: str | None) -> str | None:
    normalized = _strip_optional(value)
    if normalized is None:
        return None
    return normalized.lower()


def _bug_snapshot(bug: BugRecord) -> dict[str, Any]:
    return {
        "title": bug.title,
        "category": bug.category,
        "severity": bug.severity,
        "status": bug.status,
        "source": bug.source,
        "external_issue_provider": bug.external_issue_provider,
        "external_issue_id": bug.external_issue_id,
        "external_issue_url": bug.external_issue_url,
        "external_issue_state": bug.external_issue_state,
        "external_issue_synced_at": bug.external_issue_synced_at.isoformat()
        if bug.external_issue_synced_at is not None
        else None,
        "external_sync_revision": bug.external_sync_revision,
        "evidence": bug.evidence,
        "notes": bug.notes,
    }


def _bug_authority_snapshot(bug: BugRecord) -> tuple[str | None, ...]:
    return (
        bug.title,
        bug.category,
        bug.severity,
        bug.status,
        bug.source,
        bug.external_issue_provider,
        bug.external_issue_id,
        bug.external_issue_url,
    )
