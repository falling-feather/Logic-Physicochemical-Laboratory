from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ContentScriptAssetScanRun, User
from app.services.content_script_assets import ContentScriptAssetRemoteDriftIssue, ContentScriptAssetRemoteDriftReport


CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT = "remote_drift"
CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS = "success"
CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_MANUAL = "manual"
CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT = 100


@dataclass(frozen=True)
class ContentScriptAssetScanRunPage:
    items: list[ContentScriptAssetScanRun]
    total: int


@dataclass(frozen=True)
class ContentScriptAssetScanAlertCandidate:
    severity: str
    code: str
    source: str
    action_hint: str
    run_id: int
    run_key: str
    scan_type: str
    trigger_source: str
    status: str
    alert_status: str
    started_at: datetime
    finished_at: datetime
    slug: str | None = None
    page_id: int | None = None
    page_version_id: int | None = None
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    remote_asset_sha256: str | None = None
    remote_asset_size_bytes: int | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class ContentScriptAssetScanAlertReport:
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    alert_status: str
    candidate_count: int
    critical_count: int
    warning_count: int
    info_count: int
    recent_run_count: int
    issue_run_count: int
    candidates: list[ContentScriptAssetScanAlertCandidate]


def create_content_script_asset_remote_drift_scan_run(
    db: Session,
    *,
    report: ContentScriptAssetRemoteDriftReport,
    request_filters: dict[str, Any],
    creator: User,
    trigger_source: str = CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_MANUAL,
) -> ContentScriptAssetScanRun:
    run = ContentScriptAssetScanRun(
        run_key=_remote_drift_run_key(report.generated_at, creator.id),
        scan_type=CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
        trigger_source=trigger_source,
        status=CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS,
        started_at=report.generated_at,
        finished_at=report.generated_at,
        created_by_user_id=creator.id,
        filters_json=_strip_empty_filter_values(request_filters),
        totals_json=_remote_drift_report_totals(report),
        issue_counts_json={
            "by_code": dict(report.issue_counts_by_code),
            "by_severity": dict(report.issue_counts_by_severity),
        },
        issue_summary_json=[
            _remote_drift_issue_summary(issue)
            for issue in report.issues[:CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT]
        ],
        alert_status=_alert_status_from_issue_counts(report.issue_counts_by_severity),
        error_message=None,
    )
    db.add(run)
    return run


def list_content_script_asset_scan_runs(
    db: Session,
    *,
    scan_type: str | None = CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    status: str | None = None,
    trigger_source: str | None = None,
    alert_status: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ContentScriptAssetScanRunPage:
    statement = select(ContentScriptAssetScanRun).order_by(
        ContentScriptAssetScanRun.finished_at.desc(),
        ContentScriptAssetScanRun.id.desc(),
    )
    count_statement = select(func.count()).select_from(ContentScriptAssetScanRun)
    filters = []
    if scan_type is not None:
        filters.append(ContentScriptAssetScanRun.scan_type == scan_type.strip().lower())
    if status is not None and status.strip():
        filters.append(ContentScriptAssetScanRun.status == status.strip().lower())
    if trigger_source is not None and trigger_source.strip():
        filters.append(ContentScriptAssetScanRun.trigger_source == trigger_source.strip().lower())
    if alert_status is not None and alert_status.strip():
        filters.append(ContentScriptAssetScanRun.alert_status == alert_status.strip().lower())
    if from_at is not None:
        filters.append(ContentScriptAssetScanRun.finished_at >= from_at)
    if to_at is not None:
        filters.append(ContentScriptAssetScanRun.finished_at <= to_at)
    for item in filters:
        statement = statement.where(item)
        count_statement = count_statement.where(item)
    total = int(db.scalar(count_statement) or 0)
    runs = list(db.scalars(statement.limit(limit).offset(offset)).all())
    return ContentScriptAssetScanRunPage(items=runs, total=total)


def build_content_script_asset_scan_alert_report(
    db: Session,
    *,
    recent_run_limit: int = 20,
    candidate_limit: int = 20,
    generated_at: datetime | None = None,
    scan_type: str = CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    trigger_source: str | None = None,
    alert_status: str | None = None,
) -> ContentScriptAssetScanAlertReport:
    filters = {
        "scan_type": scan_type,
        "trigger_source": trigger_source.strip().lower() if trigger_source is not None and trigger_source.strip() else None,
        "alert_status": alert_status.strip().lower() if alert_status is not None and alert_status.strip() else None,
    }
    statement = select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.scan_type == scan_type).order_by(
        ContentScriptAssetScanRun.finished_at.desc(),
        ContentScriptAssetScanRun.id.desc(),
    )
    if filters["trigger_source"] is not None:
        statement = statement.where(ContentScriptAssetScanRun.trigger_source == filters["trigger_source"])
    if filters["alert_status"] is not None:
        statement = statement.where(ContentScriptAssetScanRun.alert_status == filters["alert_status"])
    runs = list(db.scalars(statement.limit(recent_run_limit)).all())
    candidates: list[ContentScriptAssetScanAlertCandidate] = []
    issue_run_count = 0
    for run in runs:
        issue_summaries = _issue_summary_items(run.issue_summary_json)
        if issue_summaries:
            issue_run_count += 1
        for issue in issue_summaries:
            candidates.append(_alert_candidate_from_issue(run, issue))

    sorted_candidates = _sort_alert_candidates(candidates)
    critical_count = sum(1 for item in sorted_candidates if item.severity == "critical")
    warning_count = sum(1 for item in sorted_candidates if item.severity == "warning")
    info_count = sum(1 for item in sorted_candidates if item.severity == "info")
    return ContentScriptAssetScanAlertReport(
        generated_at=generated_at or datetime.now(UTC),
        filters={key: value for key, value in filters.items() if value is not None},
        policy={
            "recent_run_limit": recent_run_limit,
            "candidate_limit": candidate_limit,
            "source": "remote_drift_scan_runs",
            "external_alerts": False,
            "automatic_actions": False,
        },
        alert_status=_alert_status_from_counts(critical_count=critical_count, warning_count=warning_count),
        candidate_count=len(sorted_candidates),
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        recent_run_count=len(runs),
        issue_run_count=issue_run_count,
        candidates=sorted_candidates[:candidate_limit],
    )


def content_script_asset_scan_run_snapshot(run: ContentScriptAssetScanRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_key": run.run_key,
        "scan_type": run.scan_type,
        "trigger_source": run.trigger_source,
        "status": run.status,
        "alert_status": run.alert_status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
        "created_by_user_id": run.created_by_user_id,
        "filters": run.filters_json,
        "totals": run.totals_json,
        "issue_counts": run.issue_counts_json,
        "issue_summary_count": len(_issue_summary_items(run.issue_summary_json)),
    }


def content_script_asset_scan_alert_snapshot(report: ContentScriptAssetScanAlertReport) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_action: dict[str, int] = {}
    for item in report.candidates:
        by_code[item.code] = by_code.get(item.code, 0) + 1
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
        by_action[item.action_hint] = by_action.get(item.action_hint, 0) + 1
    return {
        "format": "content_script_asset_scan_alert_candidates",
        "filters": report.filters,
        "policy": report.policy,
        "alert_status": report.alert_status,
        "candidate_count": report.candidate_count,
        "critical_count": report.critical_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "recent_run_count": report.recent_run_count,
        "issue_run_count": report.issue_run_count,
        "candidate_codes": by_code,
        "candidate_severities": by_severity,
        "candidate_actions": by_action,
    }


def _remote_drift_report_totals(report: ContentScriptAssetRemoteDriftReport) -> dict[str, int]:
    return {
        "total_pages_scanned": report.total_pages_scanned,
        "total_external_references": report.total_external_references,
        "total_scanned_references": report.total_scanned_references,
        "total_remote_fetches": report.total_remote_fetches,
        "total_skipped_references": report.total_skipped_references,
        "total_issues": report.total_issues,
        "issue_summary_limit": CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT,
        "issue_summary_count": min(len(report.issues), CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT),
        "issue_summary_truncated": len(report.issues) > CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT,
    }


def _remote_drift_run_key(generated_at: datetime, creator_id: int) -> str:
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"content-script-remote-drift:{timestamp}:user-{creator_id}"


def _remote_drift_issue_summary(issue: ContentScriptAssetRemoteDriftIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "page_id": issue.page_id,
        "page_version_id": issue.page_version_id,
        "slug": issue.slug,
        "sandbox_id": issue.sandbox_id,
        "reference_key": issue.reference_key,
        "reference_value_sha256": issue.reference_value_sha256,
        "source_host": issue.source_host,
        "source_url_sha256": issue.source_url_sha256,
        "asset_id": issue.asset_id,
        "asset_sha256": issue.asset_sha256,
        "remote_asset_sha256": issue.remote_asset_sha256,
        "remote_asset_size_bytes": issue.remote_asset_size_bytes,
        "published_at": issue.published_at.isoformat() if issue.published_at is not None else None,
    }


def _alert_candidate_from_issue(
    run: ContentScriptAssetScanRun,
    issue: dict[str, Any],
) -> ContentScriptAssetScanAlertCandidate:
    return ContentScriptAssetScanAlertCandidate(
        severity=str(issue.get("severity") or "info"),
        code=str(issue.get("code") or "unknown"),
        source="remote_drift_scan",
        action_hint=_action_hint_for_issue_code(str(issue.get("code") or "")),
        run_id=run.id,
        run_key=run.run_key,
        scan_type=run.scan_type,
        trigger_source=run.trigger_source,
        status=run.status,
        alert_status=run.alert_status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        slug=_optional_str(issue.get("slug")),
        page_id=_optional_int(issue.get("page_id")),
        page_version_id=_optional_int(issue.get("page_version_id")),
        sandbox_id=_optional_str(issue.get("sandbox_id")),
        reference_key=_optional_str(issue.get("reference_key")),
        reference_value_sha256=_optional_str(issue.get("reference_value_sha256")),
        source_host=_optional_str(issue.get("source_host")),
        source_url_sha256=_optional_str(issue.get("source_url_sha256")),
        asset_id=_optional_int(issue.get("asset_id")),
        asset_sha256=_optional_str(issue.get("asset_sha256")),
        remote_asset_sha256=_optional_str(issue.get("remote_asset_sha256")),
        remote_asset_size_bytes=_optional_int(issue.get("remote_asset_size_bytes")),
        published_at=_optional_datetime(issue.get("published_at")),
    )


def _action_hint_for_issue_code(code: str) -> str:
    if code in {"remote_hash_mismatch", "remote_size_mismatch", "remote_sri_mismatch", "source_mismatch"}:
        return "review_host"
    if code in {"remote_asset_unavailable", "remote_asset_too_large", "invalid_integrity_metadata"}:
        return "investigate"
    if code in {"missing_mirror", "missing_current_version", "stale_binding", "integrity_mismatch"}:
        return "repair_mirror"
    if code == "duplicate_reference":
        return "monitor"
    return "investigate"


def _alert_status_from_issue_counts(counts: dict[str, int]) -> str:
    return _alert_status_from_counts(
        critical_count=int(counts.get("critical", 0)),
        warning_count=int(counts.get("warning", 0)),
    )


def _alert_status_from_counts(*, critical_count: int, warning_count: int) -> Literal["ok", "warning", "critical"]:
    if critical_count > 0:
        return "critical"
    if warning_count > 0:
        return "warning"
    return "ok"


def _sort_alert_candidates(
    candidates: list[ContentScriptAssetScanAlertCandidate],
) -> list[ContentScriptAssetScanAlertCandidate]:
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    action_order = {"review_host": 0, "repair_mirror": 1, "investigate": 2, "monitor": 3}

    def sort_key(item: ContentScriptAssetScanAlertCandidate) -> tuple[int, int, float, int, str]:
        return (
            severity_order.get(item.severity, 99),
            action_order.get(item.action_hint, 99),
            -_naive_utc(item.finished_at).timestamp(),
            -item.run_id,
            item.code,
        )

    return sorted(candidates, key=sort_key)


def _issue_summary_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strip_empty_filter_values(filters: dict[str, Any]) -> dict[str, Any]:
    stripped: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            stripped[key] = text
        else:
            stripped[key] = value
    return stripped


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _optional_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
