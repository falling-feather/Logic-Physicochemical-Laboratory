from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any, Literal
import uuid

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ContentScriptAssetScanRun, User
from app.models.base import utc_now
from app.services.content_script_assets import (
    ContentScriptAssetRemoteDriftIssue,
    ContentScriptAssetRemoteDriftReport,
    scan_current_content_script_asset_remote_drift,
)


CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT = "remote_drift"
CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS = "success"
CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING = "running"
CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED = "failed"
CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_MANUAL = "manual"
CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCHEDULER = "scheduler"
CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCRIPT = "script"
CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT = 100


@dataclass(frozen=True)
class ContentScriptAssetRemoteDriftScanExecution:
    report: ContentScriptAssetRemoteDriftReport
    run: ContentScriptAssetScanRun


@dataclass(frozen=True)
class ContentScriptAssetScanJobLease:
    run_key: str
    lease_owner: str
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class ContentScriptAssetScanRunPage:
    items: list[ContentScriptAssetScanRun]
    total: int


@dataclass(frozen=True)
class ContentScriptAssetScanRunStatusBucket:
    status: str | None
    total: int


@dataclass(frozen=True)
class ContentScriptAssetScanHealthItem:
    id: int
    run_key: str
    scan_type: str
    trigger_source: str
    status: str
    alert_status: str
    started_at: datetime
    finished_at: datetime | None
    scheduler_lease_owner: str | None
    scheduler_lease_expires_at: datetime | None
    scheduler_heartbeat_at: datetime | None
    attempt_count: int
    error_message: str | None
    health_flags: list[str]
    retryable: bool
    claimable: bool
    lease_seconds_remaining: int | None = None


@dataclass(frozen=True)
class ContentScriptAssetScanHealthReport:
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    health_status: str
    total: int
    by_status: list[ContentScriptAssetScanRunStatusBucket]
    running_count: int
    active_running_count: int
    stale_running_count: int
    lease_expiring_count: int
    legacy_running_without_lease_count: int
    claimable_count: int
    success_count: int
    failed_count: int
    warning_run_count: int
    critical_run_count: int
    issue_run_count: int
    needs_attention_count: int
    problem_count: int
    problem_runs: list[ContentScriptAssetScanHealthItem]
    newest_finished_at: datetime | None = None
    oldest_running_started_at: datetime | None = None
    next_lease_expires_at: datetime | None = None


@dataclass(frozen=True)
class ContentScriptAssetScanQueueItem:
    source: str
    reason: str
    ready: bool
    claimable: bool
    run_key: str
    scan_type: str
    status: str
    trigger_source: str | None = None
    run_id: int | None = None
    alert_status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    scheduler_lease_owner: str | None = None
    scheduler_lease_expires_at: datetime | None = None
    scheduler_heartbeat_at: datetime | None = None
    attempt_count: int | None = None


@dataclass(frozen=True)
class ContentScriptAssetScanQueueReport:
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    queue_status: str
    backlog_count: int
    ready_count: int
    dispatchable_now_count: int
    claimable_by_lease_rule_count: int
    manual_review_count: int
    blocked_count: int
    failed_count: int
    stale_running_count: int
    active_running_count: int
    legacy_running_without_lease_count: int
    by_trigger_source: dict[str, int]
    ready_jobs: list[ContentScriptAssetScanQueueItem]
    manual_review_runs: list[ContentScriptAssetScanQueueItem]
    blocked_runs: list[ContentScriptAssetScanQueueItem]
    current_window: list[ContentScriptAssetScanQueueItem]
    oldest_ready_at: datetime | None = None
    oldest_manual_review_at: datetime | None = None
    next_lease_expires_at: datetime | None = None


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
    finished_at: datetime | None
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


def run_content_script_asset_remote_drift_scan(
    db: Session,
    *,
    creator: User | None,
    trigger_source: str,
    slug: str | None = None,
    source_host: str | None = None,
    issue_code: str | None = None,
    severity: str | None = None,
    scan_limit: int = 25,
    scan_offset: int = 0,
    generated_at: datetime | None = None,
) -> ContentScriptAssetRemoteDriftScanExecution:
    filters = content_script_asset_remote_drift_scan_filters(
        slug=slug,
        source_host=source_host,
        issue_code=issue_code,
        severity=severity,
        scan_limit=scan_limit,
        scan_offset=scan_offset,
        confirm_external_network=True,
    )
    report = scan_current_content_script_asset_remote_drift(
        db,
        slug=slug,
        source_host=source_host,
        issue_code=issue_code,
        severity=severity,
        scan_limit=scan_limit,
        scan_offset=scan_offset,
        generated_at=generated_at,
    )
    run = create_content_script_asset_remote_drift_scan_run(
        db,
        report=report,
        request_filters=filters,
        creator=creator,
        trigger_source=trigger_source,
    )
    db.flush()
    return ContentScriptAssetRemoteDriftScanExecution(report=report, run=run)


def create_content_script_asset_remote_drift_scan_run(
    db: Session,
    *,
    report: ContentScriptAssetRemoteDriftReport,
    request_filters: dict[str, Any],
    creator: User | None,
    trigger_source: str = CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_MANUAL,
) -> ContentScriptAssetScanRun:
    run = ContentScriptAssetScanRun(
        run_key=_remote_drift_run_key(report.generated_at, creator.id if creator is not None else None, trigger_source),
        scan_type=CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
        trigger_source=trigger_source,
        status=CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS,
        started_at=report.generated_at,
        finished_at=report.generated_at,
        created_by_user_id=creator.id if creator is not None else None,
        attempt_count=1,
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


def content_script_asset_remote_drift_scan_filters(
    *,
    slug: str | None = None,
    source_host: str | None = None,
    issue_code: str | None = None,
    severity: str | None = None,
    scan_limit: int = 25,
    scan_offset: int = 0,
    confirm_external_network: bool = True,
) -> dict[str, Any]:
    return _strip_empty_filter_values(
        {
            "slug": slug.strip("/") if slug is not None and slug.strip("/") else None,
            "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
            "issue_code": issue_code.strip().lower() if issue_code is not None and issue_code.strip() else None,
            "severity": severity,
            "limit": scan_limit,
            "offset": scan_offset,
            "confirm_external_network": bool(confirm_external_network),
        }
    )


def scheduled_content_script_remote_drift_run_key(
    *,
    scheduled_for: datetime,
    filters: dict[str, Any],
    interval_seconds: int,
) -> str:
    timestamp = _as_naive_utc(scheduled_for)
    bucket_seconds = max(interval_seconds, 60)
    epoch_bucket = int(timestamp.replace(tzinfo=UTC).timestamp()) // bucket_seconds
    scope_hash = hashlib.sha256(json.dumps(filters, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"content-script-remote-drift:scheduler:{epoch_bucket}:{scope_hash}"


def acquire_content_script_asset_scan_job_lease(
    db: Session,
    *,
    run_key: str,
    trigger_source: str,
    request_filters: dict[str, Any],
    lease_owner: str,
    lease_seconds: int,
    created_by_user_id: int | None = None,
    now: datetime | None = None,
) -> ContentScriptAssetScanJobLease | None:
    now_value = _as_naive_utc(now or utc_now())
    lease_expires_at = now_value + timedelta(seconds=lease_seconds)
    lease_token = uuid.uuid4().hex
    run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
    if run is None:
        run = ContentScriptAssetScanRun(
            run_key=run_key,
            scan_type=CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
            trigger_source=trigger_source,
            status=CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING,
            started_at=now_value,
            finished_at=None,
            created_by_user_id=created_by_user_id,
            attempt_count=1,
            scheduler_lease_owner=lease_owner,
            scheduler_lease_token=lease_token,
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now_value,
            filters_json=_strip_empty_filter_values(request_filters),
            totals_json={},
            issue_counts_json={"by_code": {}, "by_severity": {}},
            issue_summary_json=[],
            alert_status="ok",
            error_message=None,
        )
        db.add(run)
        try:
            db.commit()
            return ContentScriptAssetScanJobLease(
                run_key=run_key,
                lease_owner=lease_owner,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
            )
        except IntegrityError:
            db.rollback()
            return _claim_existing_content_script_asset_scan_job_lease(
                db,
                run_key=run_key,
                trigger_source=trigger_source,
                request_filters=request_filters,
                lease_owner=lease_owner,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                lease_seconds=lease_seconds,
                created_by_user_id=created_by_user_id,
                now=now_value,
            )
    return _claim_existing_content_script_asset_scan_job_lease(
        db,
        run_key=run_key,
        trigger_source=trigger_source,
        request_filters=request_filters,
        lease_owner=lease_owner,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
        lease_seconds=lease_seconds,
        created_by_user_id=created_by_user_id,
        now=now_value,
    )


def heartbeat_content_script_asset_scan_job_lease(
    db: Session,
    lease: ContentScriptAssetScanJobLease,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    now_value = _as_naive_utc(now or utc_now())
    lease_expires_at = now_value + timedelta(seconds=lease_seconds)
    result = db.execute(
        update(ContentScriptAssetScanRun)
        .where(
            ContentScriptAssetScanRun.run_key == lease.run_key,
            ContentScriptAssetScanRun.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING,
            ContentScriptAssetScanRun.scheduler_lease_owner == lease.lease_owner,
            ContentScriptAssetScanRun.scheduler_lease_token == lease.lease_token,
        )
        .values(
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now_value,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def finish_content_script_asset_scan_run_success(
    run: ContentScriptAssetScanRun,
    *,
    report: ContentScriptAssetRemoteDriftReport,
    finished_at: datetime | None = None,
) -> None:
    run.status = CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS
    run.finished_at = _as_naive_utc(finished_at or report.generated_at)
    run.totals_json = _remote_drift_report_totals(report)
    run.issue_counts_json = {
        "by_code": dict(report.issue_counts_by_code),
        "by_severity": dict(report.issue_counts_by_severity),
    }
    run.issue_summary_json = [
        _remote_drift_issue_summary(issue)
        for issue in report.issues[:CONTENT_SCRIPT_ASSET_SCAN_ISSUE_SUMMARY_LIMIT]
    ]
    run.alert_status = _alert_status_from_issue_counts(report.issue_counts_by_severity)
    run.error_message = None
    _clear_scheduler_lease(run)


def finish_content_script_asset_scan_run_failure(
    run: ContentScriptAssetScanRun,
    *,
    error: BaseException,
    finished_at: datetime | None = None,
) -> None:
    run.status = CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED
    run.finished_at = _as_naive_utc(finished_at or utc_now())
    run.alert_status = "critical"
    run.error_message = error.__class__.__name__
    _clear_scheduler_lease(run)


def _claim_existing_content_script_asset_scan_job_lease(
    db: Session,
    *,
    run_key: str,
    trigger_source: str,
    request_filters: dict[str, Any],
    lease_owner: str,
    lease_token: str,
    lease_expires_at: datetime,
    lease_seconds: int,
    created_by_user_id: int | None,
    now: datetime,
) -> ContentScriptAssetScanJobLease | None:
    stale_started_cutoff = now - timedelta(seconds=lease_seconds)
    claimable = or_(
        ContentScriptAssetScanRun.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED,
        and_(
            ContentScriptAssetScanRun.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING,
            or_(
                ContentScriptAssetScanRun.scheduler_lease_expires_at <= now,
                and_(
                    ContentScriptAssetScanRun.scheduler_lease_expires_at.is_(None),
                    ContentScriptAssetScanRun.started_at <= stale_started_cutoff,
                ),
            ),
        ),
    )
    result = db.execute(
        update(ContentScriptAssetScanRun)
        .where(ContentScriptAssetScanRun.run_key == run_key, claimable)
        .values(
            trigger_source=trigger_source,
            status=CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING,
            started_at=now,
            finished_at=None,
            created_by_user_id=created_by_user_id,
            attempt_count=ContentScriptAssetScanRun.attempt_count + 1,
            scheduler_lease_owner=lease_owner,
            scheduler_lease_token=lease_token,
            scheduler_lease_expires_at=lease_expires_at,
            scheduler_heartbeat_at=now,
            filters_json=_strip_empty_filter_values(request_filters),
            totals_json={},
            issue_counts_json={"by_code": {}, "by_severity": {}},
            issue_summary_json=[],
            alert_status="ok",
            error_message=None,
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return ContentScriptAssetScanJobLease(
        run_key=run_key,
        lease_owner=lease_owner,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
    )


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
        ContentScriptAssetScanRun.started_at.desc(),
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


def build_content_script_asset_scan_health_report(
    db: Session,
    *,
    scan_type: str = CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    trigger_source: str | None = None,
    alert_status: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    lease_seconds: int | None = None,
    lease_expiring_seconds: int = 900,
    problem_limit: int = 20,
    generated_at: datetime | None = None,
) -> ContentScriptAssetScanHealthReport:
    generated_at_value = generated_at or datetime.now(UTC)
    generated_at_naive = _as_naive_utc(generated_at_value)
    lease_expiring_cutoff = generated_at_naive + timedelta(seconds=lease_expiring_seconds)
    filters = _scan_run_filters(
        scan_type=scan_type,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
    )
    runs = list(db.scalars(_scan_run_statement(filters)).all())
    status_counts: dict[str | None, int] = {}
    running_count = 0
    active_running_count = 0
    stale_running_count = 0
    lease_expiring_count = 0
    legacy_running_without_lease_count = 0
    claimable_count = 0
    success_count = 0
    failed_count = 0
    warning_run_count = 0
    critical_run_count = 0
    issue_run_count = 0
    problem_runs: list[ContentScriptAssetScanHealthItem] = []
    newest_finished_at: datetime | None = None
    oldest_running_started_at: datetime | None = None
    next_lease_expires_at: datetime | None = None

    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        if run.finished_at is not None and (
            newest_finished_at is None or _as_naive_utc(run.finished_at) > _as_naive_utc(newest_finished_at)
        ):
            newest_finished_at = run.finished_at
        if _scan_run_has_issues(run):
            issue_run_count += 1
        if run.alert_status == "critical":
            critical_run_count += 1
        elif run.alert_status == "warning":
            warning_run_count += 1

        health_flags: list[str] = []
        retryable = False
        claimable = False
        lease_seconds_remaining: int | None = None
        if run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING:
            running_count += 1
            if oldest_running_started_at is None or _as_naive_utc(run.started_at) < _as_naive_utc(oldest_running_started_at):
                oldest_running_started_at = run.started_at
            if run.scheduler_lease_token is None:
                legacy_running_without_lease_count += 1
                health_flags.append("legacy_running_without_lease")
            lease_expires_at = _as_naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > generated_at_naive:
                lease_seconds_remaining = int((lease_expires_at - generated_at_naive).total_seconds())
                if next_lease_expires_at is None or lease_expires_at < _as_naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
                if lease_expires_at <= lease_expiring_cutoff:
                    lease_expiring_count += 1
                    health_flags.append("lease_expiring")
            if _scan_run_lease_expired(run, generated_at_value, lease_seconds):
                stale_running_count += 1
                claimable = True
                claimable_count += 1
                health_flags.append("stale_running")
            else:
                active_running_count += 1
        elif run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED:
            failed_count += 1
            retryable = True
            claimable = True
            claimable_count += 1
            health_flags.append("failed")
        elif run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_SUCCESS:
            success_count += 1
            if run.alert_status == "critical":
                health_flags.append("critical_issues")
            elif run.alert_status == "warning":
                health_flags.append("warning_issues")

        if health_flags:
            problem_runs.append(
                ContentScriptAssetScanHealthItem(
                    id=run.id,
                    run_key=run.run_key,
                    scan_type=run.scan_type,
                    trigger_source=run.trigger_source,
                    status=run.status,
                    alert_status=run.alert_status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    scheduler_lease_owner=run.scheduler_lease_owner,
                    scheduler_lease_expires_at=run.scheduler_lease_expires_at,
                    scheduler_heartbeat_at=run.scheduler_heartbeat_at,
                    attempt_count=run.attempt_count,
                    error_message=run.error_message,
                    health_flags=health_flags,
                    retryable=retryable,
                    claimable=claimable,
                    lease_seconds_remaining=lease_seconds_remaining,
                )
            )

    needs_attention_count = stale_running_count + failed_count + critical_run_count
    if needs_attention_count > 0:
        health_status = "attention"
    elif lease_expiring_count > 0 or warning_run_count > 0:
        health_status = "warning"
    else:
        health_status = "ok"
    return ContentScriptAssetScanHealthReport(
        generated_at=generated_at_value,
        filters=filters,
        policy={
            "lease_seconds": lease_seconds,
            "lease_expiring_seconds": lease_expiring_seconds,
            "problem_limit": problem_limit,
            "external_alerts": False,
            "automatic_actions": False,
        },
        health_status=health_status,
        total=len(runs),
        by_status=[
            ContentScriptAssetScanRunStatusBucket(status=status, total=total)
            for status, total in sorted(status_counts.items(), key=lambda item: str(item[0] or ""))
        ],
        running_count=running_count,
        active_running_count=active_running_count,
        stale_running_count=stale_running_count,
        lease_expiring_count=lease_expiring_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        claimable_count=claimable_count,
        success_count=success_count,
        failed_count=failed_count,
        warning_run_count=warning_run_count,
        critical_run_count=critical_run_count,
        issue_run_count=issue_run_count,
        needs_attention_count=needs_attention_count,
        problem_count=len(problem_runs),
        problem_runs=_sort_scan_health_items(problem_runs)[:problem_limit],
        newest_finished_at=newest_finished_at,
        oldest_running_started_at=oldest_running_started_at,
        next_lease_expires_at=next_lease_expires_at,
    )


def build_content_script_asset_scan_queue_report(
    db: Session,
    *,
    scan_type: str = CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    trigger_source: str | None = None,
    alert_status: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    generated_at: datetime | None = None,
    scheduler_enabled: bool = False,
    scheduler_interval_seconds: int = 3600,
    scheduler_lease_seconds: int | None = None,
    scheduler_scan_limit: int = 25,
    scheduler_source_host: str | None = None,
    scheduler_slug: str | None = None,
    scheduler_actor_user_id: int | None = None,
    item_limit: int = 20,
) -> ContentScriptAssetScanQueueReport:
    generated_at_value = generated_at or datetime.now(UTC)
    filters = _scan_run_filters(
        scan_type=scan_type,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
    )
    runs = list(db.scalars(_scan_run_statement(filters)).all())
    current_run_key = _current_content_script_scan_run_key(
        generated_at=generated_at_value,
        scheduler_interval_seconds=scheduler_interval_seconds,
        scheduler_scan_limit=scheduler_scan_limit,
        scheduler_source_host=scheduler_source_host,
        scheduler_slug=scheduler_slug,
    )
    current_run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == current_run_key))

    ready_jobs: list[ContentScriptAssetScanQueueItem] = []
    manual_review_runs: list[ContentScriptAssetScanQueueItem] = []
    blocked_runs: list[ContentScriptAssetScanQueueItem] = []
    current_window: list[ContentScriptAssetScanQueueItem] = []
    failed_count = 0
    stale_running_count = 0
    active_running_count = 0
    legacy_running_without_lease_count = 0
    claimable_by_lease_rule_count = 0
    next_lease_expires_at: datetime | None = None

    if scheduler_enabled:
        current_item = _content_script_current_window_queue_item(
            current_run,
            run_key=current_run_key,
            generated_at=generated_at_value,
            lease_seconds=scheduler_lease_seconds,
        )
        if _content_script_scan_queue_item_matches_filters(current_item, filters):
            current_window.append(current_item)
            if current_item.source == "failed":
                failed_count += 1
            elif current_item.source == "stale_running":
                stale_running_count += 1
            elif current_item.source == "active_running":
                active_running_count += 1
            elif current_item.source == "legacy_running":
                legacy_running_without_lease_count += 1
            if current_item.scheduler_lease_expires_at is not None:
                lease_expires_at = _as_naive_utc(current_item.scheduler_lease_expires_at)
                if lease_expires_at > _as_naive_utc(generated_at_value):
                    if next_lease_expires_at is None or lease_expires_at < _as_naive_utc(next_lease_expires_at):
                        next_lease_expires_at = current_item.scheduler_lease_expires_at
            if current_item.ready:
                ready_jobs.append(current_item)
                if current_item.claimable:
                    claimable_by_lease_rule_count += 1
            elif current_item.source in {"active_running", "legacy_running"}:
                blocked_runs.append(current_item)

    for run in runs:
        if run.run_key == current_run_key:
            continue
        if run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED:
            failed_count += 1
            manual_review_runs.append(
                _content_script_scan_run_queue_item(
                    run,
                    source="failed",
                    reason="failed_run_requires_investigation",
                    ready=False,
                    claimable=False,
                )
            )
        elif run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING:
            lease_expired = _scan_run_lease_expired(run, generated_at_value, scheduler_lease_seconds)
            if run.scheduler_lease_token is None:
                legacy_running_without_lease_count += 1
            lease_expires_at = _as_naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > _as_naive_utc(generated_at_value):
                if next_lease_expires_at is None or lease_expires_at < _as_naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
            if lease_expired:
                stale_running_count += 1
                manual_review_runs.append(
                    _content_script_scan_run_queue_item(
                        run,
                        source="stale_running",
                        reason="stale_run_requires_investigation",
                        ready=False,
                        claimable=False,
                    )
                )
            else:
                active_running_count += 1
                blocked_runs.append(
                    _content_script_scan_run_queue_item(
                        run,
                        source="active_running" if run.scheduler_lease_token is not None else "legacy_running",
                        reason="active_running_lease_not_expired"
                        if run.scheduler_lease_token is not None
                        else "legacy_running_without_scheduler_lease",
                        ready=False,
                        claimable=False,
                    )
                )

    ready_jobs = _sort_scan_queue_items(ready_jobs)[:item_limit]
    manual_review_runs = _sort_scan_queue_items(manual_review_runs)[:item_limit]
    blocked_runs = _sort_scan_queue_items(blocked_runs)[:item_limit]
    current_window = _sort_scan_queue_items(current_window)[:item_limit]
    ready_count = len(ready_jobs)
    manual_review_count = len(manual_review_runs)
    blocked_count = len(blocked_runs)
    backlog_count = ready_count + manual_review_count + blocked_count
    if ready_count > 0:
        queue_status = "ready"
    elif backlog_count > 0:
        queue_status = "backlog"
    elif not scheduler_enabled:
        queue_status = "disabled"
    else:
        queue_status = "empty"

    by_trigger_source: dict[str, int] = {}
    for item in ready_jobs + manual_review_runs + blocked_runs:
        source = item.trigger_source or "unknown"
        by_trigger_source[source] = by_trigger_source.get(source, 0) + 1

    return ContentScriptAssetScanQueueReport(
        generated_at=generated_at_value,
        filters={**filters, "now": generated_at_value.isoformat()},
        policy={
            "scheduler_enabled": scheduler_enabled,
            "scheduler_interval_seconds": scheduler_interval_seconds,
            "scheduler_lease_seconds": scheduler_lease_seconds,
            "scheduler_scan_limit": scheduler_scan_limit,
            "scheduler_source_host": scheduler_source_host,
            "scheduler_slug": scheduler_slug,
            "scheduler_actor_user_id": scheduler_actor_user_id,
            "item_limit": item_limit,
            "external_alerts": False,
            "automatic_actions": False,
        },
        queue_status=queue_status,
        backlog_count=backlog_count,
        ready_count=ready_count,
        dispatchable_now_count=ready_count,
        claimable_by_lease_rule_count=claimable_by_lease_rule_count,
        manual_review_count=manual_review_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        stale_running_count=stale_running_count,
        active_running_count=active_running_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        by_trigger_source=by_trigger_source,
        ready_jobs=ready_jobs,
        manual_review_runs=manual_review_runs,
        blocked_runs=blocked_runs,
        current_window=current_window,
        oldest_ready_at=_oldest_scan_queue_item_started_at(ready_jobs),
        oldest_manual_review_at=_oldest_scan_queue_item_started_at(manual_review_runs),
        next_lease_expires_at=next_lease_expires_at,
    )


def build_content_script_asset_scan_alert_report(
    db: Session,
    *,
    recent_run_limit: int = 20,
    candidate_limit: int = 20,
    generated_at: datetime | None = None,
    scan_type: str = CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
    trigger_source: str | None = None,
    alert_status: str | None = None,
    lease_seconds: int | None = None,
) -> ContentScriptAssetScanAlertReport:
    generated_at_value = generated_at or datetime.now(UTC)
    filters = {
        "scan_type": scan_type,
        "trigger_source": trigger_source.strip().lower() if trigger_source is not None and trigger_source.strip() else None,
        "alert_status": alert_status.strip().lower() if alert_status is not None and alert_status.strip() else None,
    }
    statement = select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.scan_type == scan_type).order_by(
        ContentScriptAssetScanRun.started_at.desc(),
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
        state_candidate = _alert_candidate_from_run_state(
            run,
            generated_at=generated_at_value,
            lease_seconds=lease_seconds,
        )
        if state_candidate is not None:
            candidates.append(state_candidate)
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
        generated_at=generated_at_value,
        filters={key: value for key, value in filters.items() if value is not None},
        policy={
            "recent_run_limit": recent_run_limit,
            "candidate_limit": candidate_limit,
            "source": "remote_drift_scan_runs",
            "lease_seconds": lease_seconds,
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
        "finished_at": run.finished_at.isoformat() if run.finished_at is not None else None,
        "created_by_user_id": run.created_by_user_id,
        "attempt_count": run.attempt_count,
        "scheduler_lease_owner": run.scheduler_lease_owner,
        "scheduler_lease_expires_at": (
            run.scheduler_lease_expires_at.isoformat() if run.scheduler_lease_expires_at is not None else None
        ),
        "scheduler_heartbeat_at": run.scheduler_heartbeat_at.isoformat() if run.scheduler_heartbeat_at is not None else None,
        "filters": run.filters_json,
        "totals": run.totals_json,
        "issue_counts": run.issue_counts_json,
        "issue_summary_count": len(_issue_summary_items(run.issue_summary_json)),
    }


def content_script_asset_scan_health_snapshot(report: ContentScriptAssetScanHealthReport) -> dict[str, Any]:
    return {
        "format": "content_script_asset_scan_health",
        "filters": report.filters,
        "policy": report.policy,
        "health_status": report.health_status,
        "total": report.total,
        "by_status": [bucket.__dict__ for bucket in report.by_status],
        "running_count": report.running_count,
        "stale_running_count": report.stale_running_count,
        "lease_expiring_count": report.lease_expiring_count,
        "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        "claimable_count": report.claimable_count,
        "failed_count": report.failed_count,
        "warning_run_count": report.warning_run_count,
        "critical_run_count": report.critical_run_count,
        "issue_run_count": report.issue_run_count,
        "needs_attention_count": report.needs_attention_count,
        "problem_count": report.problem_count,
    }


def content_script_asset_scan_queue_snapshot(report: ContentScriptAssetScanQueueReport) -> dict[str, Any]:
    return {
        "format": "content_script_asset_scan_queue",
        "filters": report.filters,
        "policy": report.policy,
        "queue_status": report.queue_status,
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
        "by_trigger_source": report.by_trigger_source,
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


def _remote_drift_run_key(generated_at: datetime, creator_id: int | None, trigger_source: str) -> str:
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    actor = f"user-{creator_id}" if creator_id is not None else trigger_source
    return f"content-script-remote-drift:{timestamp}:{actor}"


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


def _alert_candidate_from_run_state(
    run: ContentScriptAssetScanRun,
    *,
    generated_at: datetime,
    lease_seconds: int | None,
) -> ContentScriptAssetScanAlertCandidate | None:
    if run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED:
        return ContentScriptAssetScanAlertCandidate(
            severity="critical",
            code="scan_failed",
            source="remote_drift_scan_run",
            action_hint="investigate",
            run_id=run.id,
            run_key=run.run_key,
            scan_type=run.scan_type,
            trigger_source=run.trigger_source,
            status=run.status,
            alert_status=run.alert_status,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )
    if run.status != CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING:
        return None
    if not _scan_run_lease_expired(run, generated_at, lease_seconds):
        return None
    return ContentScriptAssetScanAlertCandidate(
        severity="critical",
        code="scan_run_stale",
        source="remote_drift_scan_run",
        action_hint="investigate",
        run_id=run.id,
        run_key=run.run_key,
        scan_type=run.scan_type,
        trigger_source=run.trigger_source,
        status=run.status,
        alert_status="critical",
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _scan_run_filters(
    *,
    scan_type: str,
    trigger_source: str | None,
    alert_status: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    return _strip_empty_filter_values(
        {
            "scan_type": scan_type.strip().lower(),
            "trigger_source": trigger_source.strip().lower()
            if trigger_source is not None and trigger_source.strip()
            else None,
            "alert_status": alert_status.strip().lower() if alert_status is not None and alert_status.strip() else None,
            "from": from_at.isoformat() if from_at is not None else None,
            "to": to_at.isoformat() if to_at is not None else None,
        }
    )


def _scan_run_statement(filters: dict[str, Any]):
    statement = select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.scan_type == filters["scan_type"]).order_by(
        ContentScriptAssetScanRun.started_at.desc(),
        ContentScriptAssetScanRun.id.desc(),
    )
    if filters.get("trigger_source") is not None:
        statement = statement.where(ContentScriptAssetScanRun.trigger_source == filters["trigger_source"])
    if filters.get("alert_status") is not None:
        statement = statement.where(ContentScriptAssetScanRun.alert_status == filters["alert_status"])
    if filters.get("from") is not None:
        statement = statement.where(ContentScriptAssetScanRun.started_at >= _optional_datetime(filters["from"]))
    if filters.get("to") is not None:
        statement = statement.where(ContentScriptAssetScanRun.started_at <= _optional_datetime(filters["to"]))
    return statement


def _scan_run_has_issues(run: ContentScriptAssetScanRun) -> bool:
    if _issue_summary_items(run.issue_summary_json):
        return True
    issue_counts = run.issue_counts_json if isinstance(run.issue_counts_json, dict) else {}
    by_code = issue_counts.get("by_code") if isinstance(issue_counts.get("by_code"), dict) else {}
    by_severity = issue_counts.get("by_severity") if isinstance(issue_counts.get("by_severity"), dict) else {}
    return any(int(value or 0) > 0 for value in list(by_code.values()) + list(by_severity.values()))


def _current_content_script_scan_run_key(
    *,
    generated_at: datetime,
    scheduler_interval_seconds: int,
    scheduler_scan_limit: int,
    scheduler_source_host: str | None,
    scheduler_slug: str | None,
) -> str:
    filters = content_script_asset_remote_drift_scan_filters(
        slug=scheduler_slug,
        source_host=scheduler_source_host,
        scan_limit=scheduler_scan_limit,
        scan_offset=0,
        confirm_external_network=True,
    )
    return scheduled_content_script_remote_drift_run_key(
        scheduled_for=generated_at,
        filters=filters,
        interval_seconds=scheduler_interval_seconds,
    )


def _content_script_current_window_queue_item(
    run: ContentScriptAssetScanRun | None,
    *,
    run_key: str,
    generated_at: datetime,
    lease_seconds: int | None,
) -> ContentScriptAssetScanQueueItem:
    if run is None:
        return ContentScriptAssetScanQueueItem(
            source="due",
            reason="scheduler_window_missing_run",
            ready=True,
            claimable=True,
            run_key=run_key,
            scan_type=CONTENT_SCRIPT_ASSET_SCAN_TYPE_REMOTE_DRIFT,
            status="missing",
            trigger_source=CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCHEDULER,
        )
    if run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_RUNNING:
        if _scan_run_lease_expired(run, generated_at, lease_seconds):
            return _content_script_scan_run_queue_item(
                run,
                source="stale_running",
                reason="scheduler_window_stale_running",
                ready=True,
                claimable=True,
            )
        return _content_script_scan_run_queue_item(
            run,
            source="active_running" if run.scheduler_lease_token is not None else "legacy_running",
            reason="scheduler_window_running_not_ready",
            ready=False,
            claimable=False,
        )
    if run.status == CONTENT_SCRIPT_ASSET_SCAN_RUN_STATUS_FAILED:
        return _content_script_scan_run_queue_item(
            run,
            source="failed",
            reason="scheduler_window_failed_claimable",
            ready=True,
            claimable=True,
        )
    return _content_script_scan_run_queue_item(
        run,
        source="current_window",
        reason=f"scheduler_window_{run.status}_not_ready",
        ready=False,
        claimable=False,
    )


def _content_script_scan_run_queue_item(
    run: ContentScriptAssetScanRun,
    *,
    source: str,
    reason: str,
    ready: bool,
    claimable: bool,
) -> ContentScriptAssetScanQueueItem:
    return ContentScriptAssetScanQueueItem(
        source=source,
        reason=reason,
        ready=ready,
        claimable=claimable,
        run_id=run.id,
        run_key=run.run_key,
        scan_type=run.scan_type,
        status=run.status,
        trigger_source=run.trigger_source,
        alert_status=run.alert_status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        attempt_count=run.attempt_count,
    )


def _content_script_scan_queue_item_matches_filters(
    item: ContentScriptAssetScanQueueItem,
    filters: dict[str, Any],
) -> bool:
    if filters.get("scan_type") is not None and item.scan_type != filters["scan_type"]:
        return False
    if filters.get("trigger_source") is not None and item.trigger_source != filters["trigger_source"]:
        return False
    if filters.get("alert_status") is not None and item.alert_status != filters["alert_status"]:
        return False
    if filters.get("from") is not None:
        if item.started_at is None or _as_naive_utc(item.started_at) < _as_naive_utc(_optional_datetime(filters["from"])):
            return False
    if filters.get("to") is not None:
        if item.started_at is None or _as_naive_utc(item.started_at) > _as_naive_utc(_optional_datetime(filters["to"])):
            return False
    return True


def _sort_scan_health_items(
    items: list[ContentScriptAssetScanHealthItem],
) -> list[ContentScriptAssetScanHealthItem]:
    flag_order = {
        "stale_running": 0,
        "failed": 1,
        "critical_issues": 2,
        "legacy_running_without_lease": 3,
        "lease_expiring": 4,
        "warning_issues": 5,
    }

    def sort_key(item: ContentScriptAssetScanHealthItem) -> tuple[int, datetime, int]:
        first_flag = item.health_flags[0] if item.health_flags else ""
        return (flag_order.get(first_flag, 99), _as_naive_utc(item.started_at), item.id)

    return sorted(items, key=sort_key)


def _sort_scan_queue_items(
    items: list[ContentScriptAssetScanQueueItem],
) -> list[ContentScriptAssetScanQueueItem]:
    source_order = {
        "due": 0,
        "stale_running": 1,
        "failed": 2,
        "active_running": 3,
        "legacy_running": 4,
        "current_window": 5,
    }

    def sort_key(item: ContentScriptAssetScanQueueItem) -> tuple[int, datetime, str, int]:
        base_time = item.started_at or item.finished_at or datetime.max
        return (source_order.get(item.source, 99), _as_naive_utc(base_time), item.run_key, item.run_id or 0)

    return sorted(items, key=sort_key)


def _oldest_scan_queue_item_started_at(items: list[ContentScriptAssetScanQueueItem]) -> datetime | None:
    started_values = [item.started_at for item in items if item.started_at is not None]
    if not started_values:
        return None
    return min(started_values, key=_as_naive_utc)


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
        sort_time = item.finished_at or item.started_at
        return (
            severity_order.get(item.severity, 99),
            action_order.get(item.action_hint, 99),
            -_naive_utc(sort_time).timestamp(),
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


def _scan_run_lease_expired(
    run: ContentScriptAssetScanRun,
    generated_at: datetime,
    lease_seconds: int | None,
) -> bool:
    now_value = _as_naive_utc(generated_at)
    if run.scheduler_lease_expires_at is not None:
        return _as_naive_utc(run.scheduler_lease_expires_at) <= now_value
    if lease_seconds is None:
        return False
    return _as_naive_utc(run.started_at) <= now_value - timedelta(seconds=lease_seconds)


def _clear_scheduler_lease(run: ContentScriptAssetScanRun) -> None:
    run.scheduler_lease_owner = None
    run.scheduler_lease_token = None
    run.scheduler_lease_expires_at = None
    run.scheduler_heartbeat_at = None


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


def _as_naive_utc(value: datetime) -> datetime:
    return _naive_utc(value)
