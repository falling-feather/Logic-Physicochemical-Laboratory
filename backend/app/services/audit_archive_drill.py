from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services.audit_chain import verify_audit_log_chain


ArchiveFormat = Literal["jsonl", "csv"]

VALID_ARCHIVE_FORMATS = {"jsonl", "csv"}
EXPORTED_AUDIT_ARCHIVE_FIELDS = (
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
    "created_at",
)
SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
    "private_key",
    "credential",
)
SENSITIVE_VALUE_MARKERS = (
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


def run_audit_archive_drill(
    db: Session,
    *,
    database_url: str,
    settings: Any,
    require_mysql: bool = False,
    archive_format: ArchiveFormat = "jsonl",
    output_dir: str | Path = "audit-archives",
    before_at: datetime | None = None,
    retention_days: int | None = None,
    warning_days: int = 30,
    limit: int = 5000,
    chain_limit: int = 5000,
    issue_limit: int = 50,
    bucket_limit: int = 20,
    action: str | None = None,
    resource_type: str | None = None,
    event_result: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only audit archive/retention production-drill report."""

    generated = generated_at or datetime.now(UTC)
    database = _database_report(database_url, require_mysql=require_mysql)
    parameters = _parameter_report(
        archive_format=archive_format,
        before_at=before_at,
        retention_days=retention_days,
        warning_days=warning_days,
        limit=limit,
        chain_limit=chain_limit,
        issue_limit=issue_limit,
        bucket_limit=bucket_limit,
        from_at=from_at,
        to_at=to_at,
    )
    if not parameters["ok"]:
        return {
            "ok": False,
            "status": "invalid_arguments",
            "generated_at": _datetime_value(generated),
            "mode": "read_only",
            "database": database,
            "parameters": parameters,
            "retention_plan": _not_run_section("invalid_arguments"),
            "archive_preview": _not_run_section("invalid_arguments"),
            "chain_integrity": _not_run_section("invalid_arguments"),
            "sensitive_field_scan": _not_run_section("invalid_arguments"),
            "operation_boundaries": _operation_boundaries_report(output_dir=output_dir),
            "evidence_required": _evidence_required(),
            "sensitive_values_returned": False,
        }

    cutoff_at, cutoff_source, effective_retention_days = _resolve_cutoff(
        before_at=before_at,
        retention_days=retention_days,
        configured_retention_days=int(settings.audit_log_retention_days),
        generated_at=generated,
    )
    filters = _filters(
        action=action,
        resource_type=resource_type,
        event_result=event_result,
        from_at=from_at,
        to_at=to_at,
    )
    base_statement = _audit_log_statement(
        action=action,
        resource_type=resource_type,
        event_result=event_result,
        from_at=from_at,
        to_at=to_at,
    )
    candidate_statement = (
        base_statement.where(AuditLog.created_at <= cutoff_at).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    )
    candidate_logs = list(db.scalars(candidate_statement.limit(limit)).all())
    chain_logs = list(db.scalars(candidate_statement.limit(chain_limit)).all())
    total_filtered = _statement_count(db, base_statement)
    total_candidates = _statement_count(db, candidate_statement)

    sections = {
        "retention_plan": _retention_plan_report(
            db,
            base_statement=base_statement,
            cutoff_at=cutoff_at,
            cutoff_source=cutoff_source,
            retention_days=effective_retention_days,
            warning_days=warning_days,
            filters=filters,
            total_filtered=total_filtered,
            total_candidates=total_candidates,
            bucket_limit=bucket_limit,
            generated_at=generated,
        ),
        "archive_preview": _archive_preview_report(
            candidate_logs,
            archive_format=archive_format,
            output_dir=output_dir,
            total_candidates=total_candidates,
            limit=limit,
            filters=filters,
        ),
        "chain_integrity": _chain_integrity_report(
            chain_logs,
            total_candidates=total_candidates,
            chain_limit=chain_limit,
            issue_limit=issue_limit,
            filters=filters,
        ),
        "sensitive_field_scan": _sensitive_field_scan_report(
            candidate_logs,
            total_candidates=total_candidates,
            scan_limit=limit,
            issue_limit=issue_limit,
        ),
        "operation_boundaries": _operation_boundaries_report(output_dir=output_dir),
    }
    ok = bool(database["ok"] and parameters["ok"] and all(section["ok"] for section in sections.values()))
    return {
        "ok": ok,
        "status": "ready_for_archive_evidence" if ok else "issues_found",
        "generated_at": _datetime_value(generated),
        "mode": "read_only",
        "database": database,
        "parameters": parameters,
        **sections,
        "evidence_required": _evidence_required(),
        "sensitive_values_returned": False,
    }


def _retention_plan_report(
    db: Session,
    *,
    base_statement: Any,
    cutoff_at: datetime,
    cutoff_source: str,
    retention_days: int | None,
    warning_days: int,
    filters: dict[str, Any],
    total_filtered: int,
    total_candidates: int,
    bucket_limit: int,
    generated_at: datetime,
) -> dict[str, Any]:
    source = base_statement.order_by(None).subquery()
    expiring_soon_cutoff_at = cutoff_at + timedelta(days=warning_days)
    expiring_soon = int(
        db.scalar(
            select(func.count())
            .select_from(source)
            .where(source.c.created_at > cutoff_at, source.c.created_at <= expiring_soon_cutoff_at)
        )
        or 0
    )
    oldest_at, newest_at = db.execute(
        select(func.min(source.c.created_at), func.max(source.c.created_at)).select_from(source)
    ).one()
    first_candidate = db.execute(
        select(source.c.id, source.c.prev_hash, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= cutoff_at)
        .order_by(source.c.created_at.asc(), source.c.id.asc())
        .limit(1)
    ).first()
    last_candidate = db.execute(
        select(source.c.id, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= cutoff_at)
        .order_by(source.c.created_at.desc(), source.c.id.desc())
        .limit(1)
    ).first()
    issues: list[dict[str, Any]] = []
    if total_candidates == 0:
        issues.append(_issue("no_archive_candidates", "info"))
    return _section_report(
        status="ready",
        counts={
            "total": total_filtered,
            "retained": max(total_filtered - total_candidates, 0),
            "archive_candidates": total_candidates,
            "expiring_soon": expiring_soon,
            "issues": len(issues),
        },
        issues=issues,
        policy={
            "source": cutoff_source,
            "retention_days": retention_days,
            "warning_days": warning_days,
            "cutoff_at": _datetime_value(cutoff_at),
            "expiring_soon_cutoff_at": _datetime_value(expiring_soon_cutoff_at),
            "generated_at": _datetime_value(generated_at),
        },
        filters=filters,
        oldest_at=_datetime_value(oldest_at),
        newest_at=_datetime_value(newest_at),
        first_candidate_id=int(first_candidate.id) if first_candidate is not None else None,
        last_candidate_id=int(last_candidate.id) if last_candidate is not None else None,
        chain_start_prev_hash=first_candidate.prev_hash if first_candidate is not None else None,
        chain_start_current_hash=first_candidate.current_hash if first_candidate is not None else None,
        chain_end_current_hash=last_candidate.current_hash if last_candidate is not None else None,
        buckets={
            "by_action": _candidate_buckets(db, source, cutoff_at, "action", bucket_limit),
            "by_resource_type": _candidate_buckets(db, source, cutoff_at, "resource_type", bucket_limit),
            "by_event_result": _candidate_buckets(db, source, cutoff_at, "event_result", bucket_limit),
        },
    )


def _archive_preview_report(
    logs: list[AuditLog],
    *,
    archive_format: str,
    output_dir: str | Path,
    total_candidates: int,
    limit: int,
    filters: dict[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if total_candidates > len(logs):
        issues.append(
            _issue(
                "archive_preview_truncated",
                "warning",
                total_candidates=total_candidates,
                previewed_count=len(logs),
                limit=limit,
            )
        )
    first = logs[0] if logs else None
    last = logs[-1] if logs else None
    return _section_report(
        status="ready",
        counts={
            "total_candidates": total_candidates,
            "previewed_count": len(logs),
            "truncated": total_candidates > len(logs),
            "issues": len(issues),
        },
        issues=issues,
        archive_format=archive_format,
        output_dir=str(output_dir),
        filename_pattern=f"audit-logs-archive-<UTC-stamp>.{archive_format}",
        manifest_pattern="audit-logs-archive-<UTC-stamp>.manifest.json",
        chain_scope=_chain_scope(filters),
        exported_fields=list(EXPORTED_AUDIT_ARCHIVE_FIELDS),
        include_snapshot_default=False,
        snapshot_export_requires_explicit_flag=True,
        would_write_files=False,
        would_delete_rows=False,
        first_id=first.id if first is not None else None,
        last_id=last.id if last is not None else None,
        chain_start_prev_hash=first.prev_hash if first is not None else None,
        chain_start_current_hash=first.current_hash if first is not None else None,
        chain_end_current_hash=last.current_hash if last is not None else None,
        capabilities={
            "jsonl": archive_format == "jsonl",
            "csv": archive_format == "csv",
            "manifest": True,
            "archive_sha256": True,
            "record_count_verify": True,
            "delete": False,
            "purge": False,
            "worm": False,
            "external_anchor": False,
        },
    )


def _chain_integrity_report(
    logs: list[AuditLog],
    *,
    total_candidates: int,
    chain_limit: int,
    issue_limit: int,
    filters: dict[str, Any],
) -> dict[str, Any]:
    chain = verify_audit_log_chain(logs, issue_limit=issue_limit)
    issues: list[dict[str, Any]] = []
    severity = "info"
    if chain["status"] == "invalid":
        severity = "critical"
        issues.append(
            _issue(
                "audit_chain_invalid",
                "critical",
                issue_count=chain["issue_count"],
                current_hash_mismatch_count=chain["current_hash_mismatch_count"],
                prev_hash_mismatch_count=chain["prev_hash_mismatch_count"],
            )
        )
    elif chain["status"] == "partial":
        severity = "warning"
        issues.append(_issue("audit_chain_partial", "warning", null_current_hash_count=chain["null_current_hash_count"]))
    if total_candidates > len(logs):
        issues.append(
            _issue(
                "audit_chain_scan_truncated",
                "warning",
                total_candidates=total_candidates,
                scanned_count=len(logs),
                limit=chain_limit,
            )
        )
    return _section_report(
        status="ready" if severity != "critical" else "issues_found",
        counts={
            "total_candidates": total_candidates,
            "scanned_count": len(logs),
            "truncated": total_candidates > len(logs),
            "issue_count": chain["issue_count"],
            "issues": len(issues),
        },
        issues=issues,
        algorithm=chain["algorithm"],
        chain_version=chain["chain_version"],
        chain_scope=_chain_scope(filters),
        chain_scope_warning=(
            "Filtered archive candidates prove only the exported subset order; run an unfiltered chain drill for global chain evidence."
            if filters
            else None
        ),
        chain_status=chain["status"],
        valid=chain["status"] == "valid" and total_candidates <= len(logs),
        issue_limit=issue_limit,
        issues_truncated=chain["issues_truncated"],
        null_current_hash_count=chain["null_current_hash_count"],
        current_hash_mismatch_count=chain["current_hash_mismatch_count"],
        prev_hash_mismatch_count=chain["prev_hash_mismatch_count"],
        sample_issues=chain["issues"],
    )


def _sensitive_field_scan_report(
    logs: list[AuditLog],
    *,
    total_candidates: int,
    scan_limit: int,
    issue_limit: int,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for log in logs:
        for issue in _sensitive_issues_for_log(log):
            counts[issue["code"]] += 1
            if len(issues) < issue_limit:
                issues.append(issue)
    if total_candidates > len(logs):
        issues.append(
            _issue(
                "sensitive_field_scan_truncated",
                "warning",
                total_candidates=total_candidates,
                scanned_count=len(logs),
                limit=scan_limit,
            )
        )
    return _section_report(
        status="ready" if not any(issue["severity"] == "critical" for issue in issues) else "issues_found",
        counts={
            "total_candidates": total_candidates,
            "scanned_count": len(logs),
            "truncated": total_candidates > len(logs),
            "critical": sum(1 for issue in issues if issue["severity"] == "critical"),
            "warning": sum(1 for issue in issues if issue["severity"] == "warning"),
            "issues": len(issues),
        },
        issues=issues,
        issue_counts_by_code=dict(counts),
        scanned_exported_fields=list(EXPORTED_AUDIT_ARCHIVE_FIELDS),
        snapshot_json_exported_by_default=False,
        raw_values_returned=False,
    )


def _operation_boundaries_report(*, output_dir: str | Path) -> dict[str, Any]:
    return _section_report(
        status="ready",
        counts={"issues": 0},
        issues=[],
        output_dir=str(output_dir),
        read_only=True,
        writes_archive_files=False,
        deletes_audit_rows=False,
        mutates_audit_rows=False,
        writes_audit_event=False,
        external_delivery=False,
        worm=False,
        external_timestamp=False,
        external_anchor=False,
        restore_drill=False,
        cleanup_proof=False,
        policy={
            "archive_script": "scripts.archive_audit_logs",
            "archive_script_default_include_snapshot": False,
            "archive_script_verify_manifest": True,
            "destructive_cleanup_supported": False,
        },
    )


def _sensitive_issues_for_log(log: AuditLog) -> Iterable[dict[str, Any]]:
    exported_values = {
        "resource": log.resource,
        "resource_id": log.resource_id,
        "failure_reason": log.failure_reason,
        "request_id": log.request_id,
        "user_agent": log.user_agent,
        "request_path": log.request_path,
    }
    for field, value in exported_values.items():
        if isinstance(value, str) and _looks_sensitive_value(value):
            yield _issue("exported_audit_field_may_contain_secret", "critical", log_id=log.id, field=field)
    for path in _sensitive_snapshot_paths(log.snapshot_json):
        yield _issue("audit_snapshot_contains_sensitive_key", "warning", log_id=log.id, path=path)


def _sensitive_snapshot_paths(value: Any, *, prefix: str = "snapshot_json") -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}"
            if _looks_sensitive_key(key_text):
                yield path
            yield from _sensitive_snapshot_paths(item, prefix=path)
    elif isinstance(value, list):
        for index, item in enumerate(value[:50]):
            yield from _sensitive_snapshot_paths(item, prefix=f"{prefix}[{index}]")


def _looks_sensitive_key(value: str) -> bool:
    text = value.lower().replace("-", "_")
    return any(marker in text for marker in SENSITIVE_KEY_MARKERS)


def _looks_sensitive_value(value: str) -> bool:
    text = value.lower()
    return any(marker in text for marker in SENSITIVE_VALUE_MARKERS)


def _audit_log_statement(
    *,
    action: str | None,
    resource_type: str | None,
    event_result: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
    statement = select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    if action is not None:
        statement = statement.where(AuditLog.action == action.strip())
    if resource_type is not None:
        statement = statement.where(AuditLog.resource_type == resource_type.strip())
    if event_result is not None:
        statement = statement.where(AuditLog.event_result == event_result.strip())
    if from_at is not None:
        statement = statement.where(AuditLog.created_at >= _ensure_utc(from_at))
    if to_at is not None:
        statement = statement.where(AuditLog.created_at <= _ensure_utc(to_at))
    return statement


def _chain_scope(filters: dict[str, Any]) -> str:
    return "filtered_candidate_subset" if filters else "global_candidate_window"


def _candidate_buckets(db: Session, source: Any, cutoff_at: datetime, column_name: str, bucket_limit: int) -> list[dict[str, Any]]:
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
    return [{"key": str(key) if key is not None else None, "total": int(total)} for key, total in rows]


def _statement_count(db: Session, statement: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)


def _resolve_cutoff(
    *,
    before_at: datetime | None,
    retention_days: int | None,
    configured_retention_days: int,
    generated_at: datetime,
) -> tuple[datetime, str, int | None]:
    if before_at is not None:
        return _ensure_utc(before_at), "before", None
    days = retention_days or configured_retention_days
    source = "query" if retention_days is not None else "config"
    return generated_at - timedelta(days=days), source, days


def _filters(
    *,
    action: str | None,
    resource_type: str | None,
    event_result: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if action is not None:
        filters["action"] = action.strip()
    if resource_type is not None:
        filters["resource_type"] = resource_type.strip()
    if event_result is not None:
        filters["event_result"] = event_result.strip()
    if from_at is not None:
        filters["from"] = _datetime_value(from_at)
    if to_at is not None:
        filters["to"] = _datetime_value(to_at)
    return filters


def _parameter_report(
    *,
    archive_format: str,
    before_at: datetime | None,
    retention_days: int | None,
    warning_days: int,
    limit: int,
    chain_limit: int,
    issue_limit: int,
    bucket_limit: int,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if archive_format not in VALID_ARCHIVE_FORMATS:
        issues.append(_issue("unsupported_archive_format", "critical", archive_format=archive_format))
    if before_at is not None and retention_days is not None:
        issues.append(_issue("before_and_retention_days_conflict", "critical"))
    if retention_days is not None and retention_days < 1:
        issues.append(_issue("invalid_retention_days", "critical", retention_days=retention_days))
    if warning_days < 0:
        issues.append(_issue("invalid_warning_days", "critical", warning_days=warning_days))
    if limit < 1:
        issues.append(_issue("invalid_archive_preview_limit", "critical", limit=limit))
    if chain_limit < 1:
        issues.append(_issue("invalid_chain_limit", "critical", chain_limit=chain_limit))
    if issue_limit < 0:
        issues.append(_issue("invalid_issue_limit", "critical", issue_limit=issue_limit))
    if bucket_limit < 1:
        issues.append(_issue("invalid_bucket_limit", "critical", bucket_limit=bucket_limit))
    if from_at is not None and to_at is not None and _ensure_utc(from_at) > _ensure_utc(to_at):
        issues.append(_issue("from_after_to", "critical"))
    return {
        "ok": not _has_critical_issue(issues),
        "status": "ready" if not _has_critical_issue(issues) else "issues_found",
        "archive_format": archive_format,
        "before_at": _datetime_value(before_at),
        "retention_days": retention_days,
        "warning_days": warning_days,
        "limit": limit,
        "chain_limit": chain_limit,
        "issue_limit": issue_limit,
        "bucket_limit": bucket_limit,
        "issue_counts_by_code": _counts(issues, "code"),
        "issue_counts_by_severity": _counts(issues, "severity"),
        "issues": issues,
    }


def _database_report(database_url: str, *, require_mysql: bool) -> dict[str, Any]:
    dialect = _database_dialect(database_url)
    mysql_ok = dialect == "mysql"
    ok = (not require_mysql) or mysql_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "mysql_required",
        "dialect": dialect,
        "require_mysql": require_mysql,
        "mysql": mysql_ok,
        "safe_database_url": _safe_database_url(database_url),
    }


def _section_report(status: str, *, counts: dict[str, Any], issues: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "ok": not _has_critical_issue(issues),
        "status": status if not _has_critical_issue(issues) else "issues_found",
        "counts": counts,
        "issue_counts_by_code": _counts(issues, "code"),
        "issue_counts_by_severity": _counts(issues, "severity"),
        "issues": issues,
        **extra,
    }


def _not_run_section(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "not_run",
        "reason": reason,
        "counts": {},
        "issues": [],
        "issue_counts_by_code": {},
        "issue_counts_by_severity": {},
    }


def _issue(code: str, severity: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, **extra}


def _has_critical_issue(issues: Iterable[dict[str, Any]]) -> bool:
    return any(issue.get("severity") == "critical" for issue in issues)


def _counts(items: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(item.get(key)) for item in items if item.get(key) is not None))


def _database_dialect(database_url: str) -> str:
    try:
        return make_url(database_url).get_backend_name()
    except ArgumentError:
        return "invalid"


def _safe_database_url(database_url: str) -> str:
    try:
        return str(make_url(database_url).render_as_string(hide_password=True))
    except ArgumentError:
        return "<invalid>"


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _ensure_utc(value).isoformat()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _evidence_required() -> list[str]:
    return [
        "脱敏 MySQL DSN、Alembic current/head、deploy_preflight/deploy_smoke 结果",
        "retention-plan 与 archive drill JSON 报告",
        "archive_audit_logs dry-run 与真实归档包 manifest",
        "manifest verify 输出、archive SHA-256、导出记录数复核",
        "归档包不含密码/token/密钥明文的抽样证据",
        "真实 MySQL 大表导出耗时、锁等待、磁盘空间和备份窗口观察",
        "WORM、对象存储、第三方时间戳或外部 hash 锚定后续方案",
    ]
