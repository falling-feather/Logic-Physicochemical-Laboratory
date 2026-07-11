import csv
import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas.admin import (
    AuditLogActionReport,
    AuditLogChainVerification,
    AuditLogExport,
    AuditLogExportItem,
    AuditLogFrequencyCandidate,
    AuditLogFrequencyReport,
    AuditLogPage,
    AuditLogRead,
    AuditLogReport,
    AuditLogReportBucket,
    AuditLogRetentionPlan,
    AuditLogRetentionPolicy,
    AuditLogRetentionSummary,
)
from app.services.admin_common import next_offset, require_admin, statement_count
from app.services.audit import record_audit_log
from app.services.audit_chain import verify_audit_log_chain


router = APIRouter()


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
    require_admin(current_user)
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
    total = statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset, next_offset=next_offset(total, offset, len(items)))


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
    require_admin(current_user)
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
    total = statement_count(db, statement)
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
    require_admin(current_user)
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
    total = statement_count(db, statement)
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
    require_admin(current_user)
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
    require_admin(current_user)
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
    require_admin(current_user)
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
    require_admin(current_user)
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
    total = statement_count(db, statement)
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
    require_admin(current_user)
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




def _divide(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


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
