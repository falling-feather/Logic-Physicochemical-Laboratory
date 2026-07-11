from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.models import AdminAlertOutboxEntry, ContentScriptAssetScanRun
from app.services.admin_alert_outbox import (
    ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
    ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
    ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT,
)
from app.services.content_script_asset_scan_runs import (
    CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    build_content_script_asset_scan_alert_report,
    build_content_script_asset_scan_queue_report,
)
from app.services.content_script_assets import audit_current_content_script_asset_mirrors
from app.services.content_script_host_policies import ContentScriptHostPolicyRow, list_content_script_host_policy_rows


VALID_SCAN_RUN_STATUSES = {"running", "success", "failed"}
VALID_ALERT_STATUSES = {"ok", "warning", "critical"}
TERMINAL_SCAN_RUN_STATUSES = {"success", "failed"}


def run_content_script_remote_drift_drill(
    db: Session,
    *,
    database_url: str,
    settings: Any,
    require_mysql: bool = False,
    expect_scheduler_enabled: bool = False,
    source_host: str | None = None,
    slug: str | None = None,
    recent_run_limit: int = 50,
    candidate_limit: int = 50,
    lease_expiring_seconds: int = 900,
    max_issues: int = 100,
    max_policy_hosts: int = 200,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only production drill report for content script remote drift observation."""

    generated = generated_at or datetime.now(UTC)
    database = _database_report(database_url, require_mysql=require_mysql)
    configuration = _configuration_report(settings, expect_scheduler_enabled=expect_scheduler_enabled)
    sections = {
        "host_policies": _host_policies_report(
            db,
            allowed_hosts=settings.content_script_allowed_host_list,
            source_host=source_host,
            max_policy_hosts=max_policy_hosts,
            max_issues=max_issues,
        ),
        "mirror_records": _mirror_records_report(
            db,
            slug=slug,
            source_host=source_host,
            max_issues=max_issues,
        ),
        "scan_runs": _scan_runs_report(
            db,
            source_host=source_host,
            slug=slug,
            max_runs=recent_run_limit,
            max_issues=max_issues,
        ),
        "queue": _queue_report(
            db,
            settings=settings,
            generated_at=generated,
            lease_expiring_seconds=lease_expiring_seconds,
        ),
        "alerts": _alerts_report(
            db,
            settings=settings,
            generated_at=generated,
            recent_run_limit=recent_run_limit,
            candidate_limit=candidate_limit,
            max_issues=max_issues,
        ),
    }
    sections["outbox"] = _outbox_report(
        db,
        alert_candidate_count=int(sections["alerts"]["counts"]["candidate_count"]),
        max_issues=max_issues,
    )
    sections["external_observation_evidence"] = _external_observation_evidence_report(database["dialect"])
    ok = bool(database["ok"] and configuration["ok"] and all(bool(section["ok"]) for section in sections.values()))
    return {
        "ok": ok,
        "status": "ready_for_observation_evidence" if ok else "issues_found",
        "generated_at": _datetime_value(generated),
        "mode": "read_only",
        "database": database,
        "configuration": configuration,
        **sections,
        "evidence_required": _evidence_required(),
        "sensitive_fields_returned": False,
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


def _configuration_report(settings: Any, *, expect_scheduler_enabled: bool) -> dict[str, Any]:
    enabled = bool(settings.content_script_remote_drift_scheduler_enabled)
    interval_seconds = int(settings.content_script_remote_drift_scheduler_interval_seconds)
    lease_seconds = int(settings.content_script_remote_drift_scheduler_lease_seconds)
    scan_limit = int(settings.content_script_remote_drift_scheduler_scan_limit)
    issues: list[dict[str, Any]] = []
    if expect_scheduler_enabled and not enabled:
        issues.append(_issue("remote_drift_scheduler_disabled_when_expected", "critical"))
    if interval_seconds > lease_seconds:
        issues.append(
            _issue(
                "remote_drift_interval_longer_than_lease",
                "warning",
                interval_seconds=interval_seconds,
                lease_seconds=lease_seconds,
            )
        )
    if scan_limit < 1:
        issues.append(_issue("remote_drift_scan_limit_disabled", "critical", scan_limit=scan_limit))
    return {
        "ok": not _has_critical_issue(issues),
        "status": "ready" if not _has_critical_issue(issues) else "issues_found",
        "scheduler_enabled": enabled,
        "expect_scheduler_enabled": expect_scheduler_enabled,
        "run_on_start": bool(settings.content_script_remote_drift_scheduler_run_on_start),
        "interval_seconds": interval_seconds,
        "lease_seconds": lease_seconds,
        "scan_limit": scan_limit,
        "source_host": settings.content_script_remote_drift_scheduler_source_host,
        "slug": settings.content_script_remote_drift_scheduler_slug,
        "actor_user_id": settings.content_script_remote_drift_scheduler_actor_user_id,
        "allowed_host_count": len(settings.content_script_allowed_host_list),
        "external_scan_confirmation_required": True,
        "production_default_policy": "scheduler remains disabled unless ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED=true",
        "issue_counts_by_code": _counts(issues, "code"),
        "issue_counts_by_severity": _counts(issues, "severity"),
        "issues": issues,
    }


def _host_policies_report(
    db: Session,
    *,
    allowed_hosts: list[str] | set[str],
    source_host: str | None,
    max_policy_hosts: int,
    max_issues: int,
) -> dict[str, Any]:
    page = list_content_script_host_policy_rows(
        db,
        allowed_hosts=allowed_hosts,
        source_host=source_host,
        limit=max_policy_hosts,
        offset=0,
    )
    rows = page.items
    issues: list[dict[str, Any]] = []
    for row in rows:
        if row.status == "unreviewed" and row.observed_asset_count > 0:
            issues.append(_issue("observed_host_unreviewed", "warning", host=row.source_host))
        if row.status == "watch" and row.observed_asset_count > 0:
            issues.append(_issue("observed_host_on_watch", "warning", host=row.source_host))
        if row.status == "blocked" and row.observed_asset_count > 0:
            issues.append(_issue("blocked_host_has_published_assets", "warning", host=row.source_host))
        if row.status == "blocked" and row.configured_allowed:
            issues.append(_issue("blocked_host_still_configured_allowed", "critical", host=row.source_host))
        if row.status == "trusted" and not row.configured_allowed:
            issues.append(_issue("trusted_host_not_in_allowed_config", "warning", host=row.source_host))
    by_status = Counter(row.status for row in rows)
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "total_hosts": page.total,
            "returned_hosts": len(rows),
            "trusted": by_status.get("trusted", 0),
            "watch": by_status.get("watch", 0),
            "blocked": by_status.get("blocked", 0),
            "unreviewed": by_status.get("unreviewed", 0),
            "configured_allowed": sum(1 for row in rows if row.configured_allowed),
            "observed_hosts": sum(1 for row in rows if row.observed_asset_count > 0),
            "blocked_observed_hosts": sum(1 for row in rows if row.status == "blocked" and row.observed_asset_count > 0),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        items=[_host_policy_summary(row) for row in rows[:50]],
        policy={
            "automatic_trust": False,
            "automatic_block": False,
            "blocked_hosts_fail_closed_at_publish": True,
            "blocked_hosts_fail_closed_at_render": True,
        },
    )


def _mirror_records_report(
    db: Session,
    *,
    slug: str | None,
    source_host: str | None,
    max_issues: int,
) -> dict[str, Any]:
    audit = audit_current_content_script_asset_mirrors(db, slug=slug, source_host=source_host)
    issues = [
        {
            "code": issue.code,
            "severity": issue.severity,
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
            "published_at": _datetime_value(issue.published_at),
        }
        for issue in audit.issues
    ]
    return _section_report(
        status="ready" if audit.total_issues == 0 else "issues_found",
        counts={
            "total_pages_scanned": audit.total_pages_scanned,
            "total_external_references": audit.total_external_references,
            "total_issues": audit.total_issues,
        },
        issues=issues,
        max_issues=max_issues,
        issue_counts_by_code=audit.issue_counts_by_code,
        issue_counts_by_severity=audit.issue_counts_by_severity,
        policy={
            "external_network": False,
            "cdn_scan": False,
            "repair": False,
            "external_alerts": False,
        },
    )


def _scan_runs_report(
    db: Session,
    *,
    source_host: str | None,
    slug: str | None,
    max_runs: int,
    max_issues: int,
) -> dict[str, Any]:
    statement = (
        select(ContentScriptAssetScanRun)
        .where(ContentScriptAssetScanRun.scan_type == CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT)
        .order_by(ContentScriptAssetScanRun.started_at.desc(), ContentScriptAssetScanRun.id.desc())
        .limit(max_runs)
    )
    runs = [
        run
        for run in db.scalars(statement).all()
        if _scan_run_matches_scope(run, source_host=source_host, slug=slug)
    ]
    issues: list[dict[str, Any]] = []
    for run in runs:
        issues.extend(_scan_run_issues(run))
    by_status = Counter(run.status for run in runs)
    by_alert_status = Counter(run.alert_status for run in runs)
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "runs_scanned": len(runs),
            "running": by_status.get("running", 0),
            "success": by_status.get("success", 0),
            "failed": by_status.get("failed", 0),
            "ok": by_alert_status.get("ok", 0),
            "warning": by_alert_status.get("warning", 0),
            "critical": by_alert_status.get("critical", 0),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        items=[_scan_run_summary(run) for run in runs[:20]],
        policy={
            "external_network": False,
            "mutation": False,
            "automatic_actions": False,
        },
    )


def _scan_run_issues(run: ContentScriptAssetScanRun) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if run.status not in VALID_SCAN_RUN_STATUSES:
        issues.append(_issue("invalid_scan_run_status", "critical", run=run, status=run.status))
    if run.alert_status not in VALID_ALERT_STATUSES:
        issues.append(_issue("invalid_scan_run_alert_status", "critical", run=run, alert_status=run.alert_status))
    if run.attempt_count < 0:
        issues.append(_issue("negative_attempt_count", "critical", run=run, attempt_count=run.attempt_count))
    if run.finished_at is not None and _as_naive_utc(run.finished_at) < _as_naive_utc(run.started_at):
        issues.append(_issue("finished_before_started", "critical", run=run))
    has_lease = _run_has_lease(run)
    if run.status == "running":
        if not has_lease:
            issues.append(_issue("running_missing_scheduler_lease", "critical", run=run))
        else:
            if not run.scheduler_lease_owner:
                issues.append(_issue("running_missing_lease_owner", "critical", run=run))
            if not run.scheduler_lease_token:
                issues.append(_issue("running_missing_lease_token", "critical", run=run))
            if run.scheduler_lease_expires_at is None:
                issues.append(_issue("running_missing_lease_expiry", "critical", run=run))
            if run.scheduler_heartbeat_at is None:
                issues.append(_issue("running_missing_heartbeat", "critical", run=run))
    elif run.status in TERMINAL_SCAN_RUN_STATUSES and has_lease:
        issues.append(_issue("terminal_scan_run_still_has_scheduler_lease", "critical", run=run))
    if run.status in TERMINAL_SCAN_RUN_STATUSES and run.finished_at is None:
        issues.append(_issue("terminal_scan_run_missing_finished_at", "critical", run=run))
    if run.status == "failed":
        issues.append(_issue("failed_scan_run_requires_review", "critical", run=run))
    if run.alert_status == "critical":
        issues.append(_issue("critical_remote_drift_issue_run", "critical", run=run))
    elif run.alert_status == "warning":
        issues.append(_issue("warning_remote_drift_issue_run", "warning", run=run))
    return issues


def _queue_report(
    db: Session,
    *,
    settings: Any,
    generated_at: datetime,
    lease_expiring_seconds: int,
) -> dict[str, Any]:
    report = build_content_script_asset_scan_queue_report(
        db,
        generated_at=generated_at,
        scheduler_enabled=bool(settings.content_script_remote_drift_scheduler_enabled),
        scheduler_interval_seconds=int(settings.content_script_remote_drift_scheduler_interval_seconds),
        scheduler_lease_seconds=int(settings.content_script_remote_drift_scheduler_lease_seconds),
        scheduler_scan_limit=int(settings.content_script_remote_drift_scheduler_scan_limit),
        scheduler_source_host=settings.content_script_remote_drift_scheduler_source_host,
        scheduler_slug=settings.content_script_remote_drift_scheduler_slug,
        scheduler_actor_user_id=settings.content_script_remote_drift_scheduler_actor_user_id,
        item_limit=20,
    )
    issues: list[dict[str, Any]] = []
    if report.manual_review_count:
        issues.append(_issue("remote_drift_queue_manual_review_backlog", "warning", count=report.manual_review_count))
    if report.blocked_count:
        issues.append(_issue("remote_drift_queue_blocked_runs", "warning", count=report.blocked_count))
    if report.active_running_count and report.next_lease_expires_at is None:
        issues.append(_issue("remote_drift_queue_active_running_without_lease_expiry", "warning"))
    return _section_report(
        status=report.queue_status,
        counts={
            "backlog_count": report.backlog_count,
            "ready_count": report.ready_count,
            "dispatchable_now_count": report.dispatchable_now_count,
            "claimable_by_lease_rule_count": report.claimable_by_lease_rule_count,
            "manual_review_count": report.manual_review_count,
            "blocked_count": report.blocked_count,
            "failed_count": report.failed_count,
            "stale_running_count": report.stale_running_count,
            "active_running_count": report.active_running_count,
            "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        },
        issues=issues,
        max_issues=20,
        items=[_queue_item_summary(item) for item in report.ready_jobs + report.manual_review_runs + report.blocked_runs],
        policy={
            **report.policy,
            "lease_expiring_seconds": lease_expiring_seconds,
            "external_network": False,
            "external_alerts": False,
            "automatic_actions": False,
        },
    )


def _alerts_report(
    db: Session,
    *,
    settings: Any,
    generated_at: datetime,
    recent_run_limit: int,
    candidate_limit: int,
    max_issues: int,
) -> dict[str, Any]:
    report = build_content_script_asset_scan_alert_report(
        db,
        generated_at=generated_at,
        recent_run_limit=recent_run_limit,
        candidate_limit=candidate_limit,
        lease_seconds=int(settings.content_script_remote_drift_scheduler_lease_seconds),
    )
    issues: list[dict[str, Any]] = []
    if report.critical_count:
        issues.append(_issue("critical_remote_drift_alert_candidates", "critical", count=report.critical_count))
    if report.warning_count:
        issues.append(_issue("warning_remote_drift_alert_candidates", "warning", count=report.warning_count))
    return _section_report(
        status=report.alert_status,
        counts={
            "candidate_count": report.candidate_count,
            "critical_count": report.critical_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
            "recent_run_count": report.recent_run_count,
            "issue_run_count": report.issue_run_count,
        },
        issues=issues,
        max_issues=max_issues,
        items=[_alert_candidate_summary(item) for item in report.candidates],
        policy={
            **report.policy,
            "external_alerts": False,
            "automatic_actions": False,
            "outbox_write": False,
        },
    )


def _outbox_report(
    db: Session,
    *,
    alert_candidate_count: int,
    max_issues: int,
) -> dict[str, Any]:
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.source_type == ALERT_OUTBOX_SOURCE_CONTENT_SCRIPT_REMOTE_DRIFT)
            .order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())
        ).all()
    )
    issues: list[dict[str, Any]] = []
    external_delivery_count = 0
    non_manual_count = 0
    non_admin_target_count = 0
    active_count = 0
    for entry in entries:
        if entry.status in {"pending_review", "planned", "queued"}:
            active_count += 1
        if entry.external_delivery:
            external_delivery_count += 1
            issues.append(_issue("outbox_external_delivery_enabled", "critical", entry=entry))
        if entry.dispatch_mode != ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW:
            non_manual_count += 1
            issues.append(_issue("outbox_non_manual_dispatch_mode", "critical", entry=entry))
        if entry.delivery_target != ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX:
            non_admin_target_count += 1
            issues.append(_issue("outbox_non_admin_delivery_target", "critical", entry=entry))
    if alert_candidate_count > 0 and active_count == 0:
        issues.append(_issue("alert_candidates_not_yet_in_local_outbox", "warning", count=alert_candidate_count))
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "entries": len(entries),
            "active_entries": active_count,
            "pending_review": sum(1 for entry in entries if entry.status == "pending_review"),
            "planned": sum(1 for entry in entries if entry.status == "planned"),
            "queued": sum(1 for entry in entries if entry.status == "queued"),
            "suppressed": sum(1 for entry in entries if entry.status == "suppressed"),
            "cancelled": sum(1 for entry in entries if entry.status == "cancelled"),
            "external_delivery": external_delivery_count,
            "non_manual_dispatch_mode": non_manual_count,
            "non_admin_delivery_target": non_admin_target_count,
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        items=[_outbox_entry_summary(entry) for entry in entries[:20]],
        policy={
            "external_delivery": False,
            "dispatch_mode": ALERT_OUTBOX_DISPATCH_MODE_MANUAL_REVIEW,
            "delivery_target": ALERT_OUTBOX_DELIVERY_TARGET_ADMIN_OUTBOX,
            "payload_returned": False,
            "mutation": False,
        },
    )


def _external_observation_evidence_report(dialect: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "external_evidence_required",
        "database_dialect": dialect,
        "read_only_drill": True,
        "required_checks": [
            "safe external script host sample selected and documented",
            "observe-only remote drift scan run with explicit external network confirmation",
            "trusted/watch/blocked/unreviewed host policy posture before and after scan",
            "mirror record and remote hash/size/SRI drift evidence",
            "alert candidate and local outbox pending_review evidence without external delivery",
            "audit log snapshots for scan, alert report and outbox enqueue",
        ],
        "policy": "this script reads stored observation posture; it does not fetch CDN bytes, mutate host policy or enqueue outbox entries",
    }


def _section_report(
    *,
    status: str,
    counts: dict[str, int],
    issues: list[dict[str, Any]],
    max_issues: int,
    items: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    issue_counts_by_code: dict[str, int] | None = None,
    issue_counts_by_severity: dict[str, int] | None = None,
) -> dict[str, Any]:
    report = {
        "ok": not _has_critical_issue(issues),
        "status": status,
        "counts": counts,
        "issue_counts_by_code": issue_counts_by_code or _counts(issues, "code"),
        "issue_counts_by_severity": issue_counts_by_severity or _counts(issues, "severity"),
        "issues": issues[:max_issues],
        "truncated": len(issues) > max_issues,
    }
    if items is not None:
        report["items"] = items
    if policy is not None:
        report["policy"] = policy
    return report


def _issue(
    code: str,
    severity: str,
    *,
    run: ContentScriptAssetScanRun | None = None,
    entry: AdminAlertOutboxEntry | None = None,
    host: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "run_id": run.id if run is not None else None,
        "run_key_sha256": _sha256_text(run.run_key) if run is not None else None,
        "scan_type": run.scan_type if run is not None else None,
        "trigger_source": run.trigger_source if run is not None else None,
        "status": run.status if run is not None else None,
        "alert_status": run.alert_status if run is not None else None,
        "entry_id": entry.id if entry is not None else None,
        "entry_status": entry.status if entry is not None else None,
        "event_code": entry.event_code if entry is not None else None,
        "source_host": host,
    }
    payload.update(extra)
    return {key: value for key, value in payload.items() if value is not None}


def _host_policy_summary(row: ContentScriptHostPolicyRow) -> dict[str, Any]:
    return {
        "source_host": row.source_host,
        "status": row.status,
        "configured_allowed": row.configured_allowed,
        "observed_asset_count": row.observed_asset_count,
        "observed_page_count": row.observed_page_count,
        "last_observed_at": _datetime_value(row.last_observed_at),
        "reviewed": row.policy_id is not None,
        "reviewed_at": _datetime_value(row.reviewed_at),
    }


def _scan_run_summary(run: ContentScriptAssetScanRun) -> dict[str, Any]:
    issue_codes = Counter(str(item.get("code")) for item in _issue_summary_items(run.issue_summary_json) if item.get("code"))
    return {
        "id": run.id,
        "run_key_sha256": _sha256_text(run.run_key),
        "scan_type": run.scan_type,
        "trigger_source": run.trigger_source,
        "status": run.status,
        "alert_status": run.alert_status,
        "started_at": _datetime_value(run.started_at),
        "finished_at": _datetime_value(run.finished_at),
        "created_by_user_id": run.created_by_user_id,
        "attempt_count": run.attempt_count,
        "scheduler_lease_owner_present": bool(run.scheduler_lease_owner),
        "lease_token_present": bool(run.scheduler_lease_token),
        "scheduler_lease_expires_at": _datetime_value(run.scheduler_lease_expires_at),
        "scheduler_heartbeat_at": _datetime_value(run.scheduler_heartbeat_at),
        "filters": _safe_scan_filters(run.filters_json),
        "totals": _safe_scan_totals(run.totals_json),
        "issue_counts": _safe_issue_counts(run.issue_counts_json),
        "issue_summary_count": len(_issue_summary_items(run.issue_summary_json)),
        "issue_codes": dict(issue_codes),
        "error_message_present": bool(run.error_message),
    }


def _queue_item_summary(item: Any) -> dict[str, Any]:
    return {
        "source": item.source,
        "reason": item.reason,
        "ready": item.ready,
        "claimable": item.claimable,
        "run_key_sha256": _sha256_text(item.run_key),
        "scan_type": item.scan_type,
        "status": item.status,
        "trigger_source": item.trigger_source,
        "run_id": item.run_id,
        "alert_status": item.alert_status,
        "started_at": _datetime_value(item.started_at),
        "finished_at": _datetime_value(item.finished_at),
        "scheduler_lease_owner_present": bool(item.scheduler_lease_owner),
        "scheduler_lease_expires_at": _datetime_value(item.scheduler_lease_expires_at),
        "scheduler_heartbeat_at": _datetime_value(item.scheduler_heartbeat_at),
        "attempt_count": item.attempt_count,
    }


def _alert_candidate_summary(item: Any) -> dict[str, Any]:
    return {
        "severity": item.severity,
        "code": item.code,
        "source": item.source,
        "action_hint": item.action_hint,
        "run_id": item.run_id,
        "run_key_sha256": _sha256_text(item.run_key),
        "scan_type": item.scan_type,
        "trigger_source": item.trigger_source,
        "status": item.status,
        "alert_status": item.alert_status,
        "started_at": _datetime_value(item.started_at),
        "finished_at": _datetime_value(item.finished_at),
        "slug": item.slug,
        "page_id": item.page_id,
        "page_version_id": item.page_version_id,
        "sandbox_id": item.sandbox_id,
        "reference_key": item.reference_key,
        "reference_value_sha256": item.reference_value_sha256,
        "source_host": item.source_host,
        "source_url_sha256": item.source_url_sha256,
        "asset_id": item.asset_id,
        "asset_sha256": item.asset_sha256,
        "remote_asset_sha256": item.remote_asset_sha256,
        "remote_asset_size_bytes": item.remote_asset_size_bytes,
        "published_at": _datetime_value(item.published_at),
    }


def _outbox_entry_summary(entry: AdminAlertOutboxEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "source_key_sha256": _sha256_text(entry.source_key),
        "event_code": entry.event_code,
        "severity": entry.severity,
        "action_hint": entry.action_hint,
        "status": entry.status,
        "dispatch_mode": entry.dispatch_mode,
        "delivery_target": entry.delivery_target,
        "external_delivery": entry.external_delivery,
        "payload_hash": entry.payload_hash,
        "first_seen_at": _datetime_value(entry.first_seen_at),
        "last_seen_at": _datetime_value(entry.last_seen_at),
        "available_at": _datetime_value(entry.available_at),
        "expires_at": _datetime_value(entry.expires_at),
        "seen_count": entry.seen_count,
        "attempt_count": entry.attempt_count,
        "last_error_code_present": bool(entry.last_error_code),
        "reviewed": entry.reviewed_at is not None,
    }


def _scan_run_matches_scope(
    run: ContentScriptAssetScanRun,
    *,
    source_host: str | None,
    slug: str | None,
) -> bool:
    filters = _safe_scan_filters(run.filters_json)
    if source_host is not None and filters.get("source_host") != source_host.strip().lower():
        return False
    if slug is not None and filters.get("slug") != slug.strip("/"):
        return False
    return True


def _safe_scan_filters(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed_keys = {"slug", "source_host", "issue_code", "severity", "limit", "offset", "confirm_external_network"}
    return {key: value[key] for key in sorted(allowed_keys) if key in value}


def _safe_scan_totals(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed_keys = {
        "total_pages_scanned",
        "total_external_references",
        "total_scanned_references",
        "total_remote_fetches",
        "total_skipped_references",
        "total_issues",
        "issue_summary_limit",
        "issue_summary_count",
        "issue_summary_truncated",
    }
    return {key: value[key] for key in sorted(allowed_keys) if key in value}


def _safe_issue_counts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"by_code": {}, "by_severity": {}}
    result: dict[str, Any] = {}
    for key in ("by_code", "by_severity"):
        nested = value.get(key)
        result[key] = nested if isinstance(nested, dict) else {}
    return result


def _issue_summary_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _run_has_lease(run: ContentScriptAssetScanRun) -> bool:
    return any(
        (
            run.scheduler_lease_owner,
            run.scheduler_lease_token,
            run.scheduler_lease_expires_at,
            run.scheduler_heartbeat_at,
        )
    )


def _database_dialect(database_url: str) -> str | None:
    try:
        return make_url(database_url).get_backend_name()
    except ArgumentError:
        return None


def _safe_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _has_critical_issue(issues: Iterable[dict[str, Any]]) -> bool:
    return any(issue.get("severity") == "critical" for issue in issues)


def _counts(items: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(item.get(key)) for item in items if item.get(key) is not None))


def _evidence_required() -> list[dict[str, str]]:
    return [
        {
            "code": "safe_host_observe_only_scan",
            "description": "Run the explicit remote drift scan against a documented safe host sample and capture the run id, run key hash and totals.",
        },
        {
            "code": "host_policy_posture",
            "description": "Capture trusted/watch/blocked/unreviewed host policy posture and prove blocked hosts fail closed at publish and render time.",
        },
        {
            "code": "drift_to_local_outbox",
            "description": "Capture alert candidates and local pending_review outbox entries without external delivery or automatic host policy mutation.",
        },
        {
            "code": "audit_and_redaction",
            "description": "Capture audit snapshots for scan, alert report and outbox enqueue while proving raw CDN URLs, SRI, bytes and exception text are redacted.",
        },
        {
            "code": "mysql_and_proxy_observation",
            "description": "Run the same observation flow on real MySQL and through the deployed reverse proxy before claiming production readiness.",
        },
    ]
