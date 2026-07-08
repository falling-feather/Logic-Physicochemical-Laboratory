from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.models import ClassKnowledgeSnapshot, KnowledgeSnapshotRun, UserKnowledgeSnapshot
from app.services.knowledge_snapshot_runs import snapshot_run_key
from app.services.knowledge_snapshot_scheduler import SnapshotScheduleConfig, due_snapshot_jobs, pending_snapshot_jobs


VALID_RUN_STATUSES = {"pending", "running", "success", "failed", "cancelled"}
TERMINAL_RUN_STATUSES = {"success", "failed", "cancelled"}
DEFAULT_REQUEST_ID = "astra-knowledge-snapshot-scheduler-drill"


def run_knowledge_snapshot_scheduler_drill(
    db: Session,
    *,
    database_url: str,
    settings: Any,
    require_mysql: bool = False,
    expect_scheduler_enabled: bool = False,
    now: datetime | None = None,
    lease_expiring_seconds: int = 600,
    max_issues: int = 100,
    max_runs: int = 500,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only production drill report for knowledge snapshot scheduling."""

    generated = generated_at or datetime.now(UTC)
    now_value = _as_naive_utc(now or generated)
    schedule_config = _schedule_config(settings)
    database = _database_report(database_url, require_mysql=require_mysql)
    configuration = _configuration_report(
        settings,
        expect_scheduler_enabled=expect_scheduler_enabled,
    )
    runs = _load_runs(db, max_runs=max_runs)
    sections = {
        "run_ledger": _run_ledger_report(
            db,
            runs,
            retry_attempts=int(settings.knowledge_snapshot_retry_attempts),
            lease_seconds=int(settings.knowledge_snapshot_scheduler_lease_seconds),
            lease_expiring_seconds=lease_expiring_seconds,
            now=now_value,
            max_issues=max_issues,
        ),
        "queue": _queue_report(
            db,
            schedule_config=schedule_config,
            retry_attempts=int(settings.knowledge_snapshot_retry_attempts),
            lease_seconds=int(settings.knowledge_snapshot_scheduler_lease_seconds),
            now=now_value,
            max_issues=max_issues,
        ),
        "snapshot_outputs": _snapshot_outputs_report(
            db,
            runs,
            max_issues=max_issues,
        ),
        "mysql_concurrency_evidence": _mysql_concurrency_evidence_report(database["dialect"]),
    }
    ok = bool(database["ok"] and configuration["ok"] and all(bool(section["ok"]) for section in sections.values()))
    return {
        "ok": ok,
        "status": "ready_for_mysql_evidence" if ok else "issues_found",
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
    enabled = bool(settings.knowledge_snapshot_scheduler_enabled)
    interval_seconds = int(settings.knowledge_snapshot_scheduler_interval_seconds)
    lease_seconds = int(settings.knowledge_snapshot_scheduler_lease_seconds)
    heartbeat_seconds = int(settings.knowledge_snapshot_scheduler_heartbeat_seconds)
    retry_attempts = int(settings.knowledge_snapshot_retry_attempts)
    issues: list[dict[str, Any]] = []
    if expect_scheduler_enabled and not enabled:
        issues.append(_issue("scheduler_disabled_when_expected", "critical"))
    if heartbeat_seconds >= lease_seconds:
        issues.append(
            _issue(
                "heartbeat_not_shorter_than_lease",
                "critical",
                heartbeat_seconds=heartbeat_seconds,
                lease_seconds=lease_seconds,
            )
        )
    if interval_seconds > lease_seconds:
        issues.append(
            _issue(
                "interval_longer_than_lease",
                "warning",
                interval_seconds=interval_seconds,
                lease_seconds=lease_seconds,
            )
        )
    if retry_attempts < 1:
        issues.append(_issue("retry_attempts_disabled", "warning", retry_attempts=retry_attempts))
    daily_enabled = bool(settings.knowledge_snapshot_daily_enabled)
    weekly_enabled = bool(settings.knowledge_snapshot_weekly_enabled)
    if not daily_enabled and not weekly_enabled:
        issues.append(_issue("all_periodic_jobs_disabled", "warning"))
    ok = not _has_critical_issue(issues)
    return {
        "ok": ok,
        "status": "ready" if ok else "issues_found",
        "scheduler_enabled": enabled,
        "expect_scheduler_enabled": expect_scheduler_enabled,
        "run_on_start": bool(settings.knowledge_snapshot_scheduler_run_on_start),
        "interval_seconds": interval_seconds,
        "lease_seconds": lease_seconds,
        "heartbeat_seconds": heartbeat_seconds,
        "retry_attempts": retry_attempts,
        "daily_enabled": daily_enabled,
        "daily_hour": int(settings.knowledge_snapshot_daily_hour),
        "weekly_enabled": weekly_enabled,
        "weekly_weekday": int(settings.knowledge_snapshot_weekly_weekday),
        "weekly_hour": int(settings.knowledge_snapshot_weekly_hour),
        "production_default_policy": "scheduler remains disabled unless ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED=true",
        "issue_counts_by_code": _counts(issues, "code"),
        "issue_counts_by_severity": _counts(issues, "severity"),
        "issues": issues,
    }


def _run_ledger_report(
    db: Session,
    runs: list[KnowledgeSnapshotRun],
    *,
    retry_attempts: int,
    lease_seconds: int,
    lease_expiring_seconds: int,
    now: datetime,
    max_issues: int,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for run in runs:
        issues.extend(
            _run_ledger_issues(
                db,
                run,
                retry_attempts=retry_attempts,
                lease_seconds=lease_seconds,
                lease_expiring_seconds=lease_expiring_seconds,
                now=now,
            )
        )
    by_status = dict(Counter(run.status for run in runs))
    active_running = [
        run
        for run in runs
        if run.status == "running" and not _run_lease_expired(run, now, lease_seconds)
    ]
    stale_running = [
        run
        for run in runs
        if run.status == "running" and _run_lease_expired(run, now, lease_seconds)
    ]
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "runs_scanned": len(runs),
            "pending": by_status.get("pending", 0),
            "running": by_status.get("running", 0),
            "active_running": len(active_running),
            "stale_running": len(stale_running),
            "success": by_status.get("success", 0),
            "failed": by_status.get("failed", 0),
            "cancelled": by_status.get("cancelled", 0),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        latest_runs=[_run_summary(run, now=now, lease_seconds=lease_seconds) for run in runs[:20]],
    )


def _run_ledger_issues(
    db: Session,
    run: KnowledgeSnapshotRun,
    *,
    retry_attempts: int,
    lease_seconds: int,
    lease_expiring_seconds: int,
    now: datetime,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if run.status not in VALID_RUN_STATUSES:
        issues.append(_issue("invalid_run_status", "critical", run=run, status=run.status))
    if _as_naive_utc(run.period_start) > _as_naive_utc(run.period_end):
        issues.append(_issue("invalid_snapshot_window", "critical", run=run))
    expected_key = snapshot_run_key(run.granularity, run.period_start, run.period_end)
    if run.run_key != expected_key:
        issues.append(_issue("run_key_window_mismatch", "critical", run=run, expected_run_key_sha256=_sha256_text(expected_key)))
    if run.attempt_count < 0:
        issues.append(_issue("negative_attempt_count", "critical", run=run, attempt_count=run.attempt_count))
    if run.user_snapshot_count < 0 or run.class_snapshot_count < 0:
        issues.append(
            _issue(
                "negative_snapshot_count",
                "critical",
                run=run,
                user_snapshot_count=run.user_snapshot_count,
                class_snapshot_count=run.class_snapshot_count,
            )
        )
    if run.finished_at is not None and _as_naive_utc(run.finished_at) < _as_naive_utc(run.started_at):
        issues.append(_issue("finished_before_started", "critical", run=run))

    has_lease = _run_has_lease(run)
    if run.status == "running":
        if not has_lease:
            issues.append(_issue("running_missing_scheduler_lease", "critical", run=run))
        else:
            if run.scheduler_lease_expires_at is None:
                issues.append(_issue("running_missing_lease_expiry", "critical", run=run))
            if run.scheduler_heartbeat_at is None:
                issues.append(_issue("running_missing_heartbeat", "critical", run=run))
            if _run_lease_expired(run, now, lease_seconds):
                issues.append(_issue("stale_running_lease_expired", "warning", run=run))
            elif _run_lease_expiring(run, now, lease_expiring_seconds):
                issues.append(_issue("lease_expiring_soon", "warning", run=run))
            if (
                run.scheduler_heartbeat_at is not None
                and run.scheduler_lease_expires_at is not None
                and _as_naive_utc(run.scheduler_heartbeat_at) > _as_naive_utc(run.scheduler_lease_expires_at)
            ):
                issues.append(_issue("heartbeat_after_lease_expiry", "critical", run=run))
    elif run.status in TERMINAL_RUN_STATUSES and has_lease:
        issues.append(_issue("terminal_run_still_has_scheduler_lease", "critical", run=run))

    if run.status in TERMINAL_RUN_STATUSES and run.finished_at is None:
        issues.append(_issue("terminal_run_missing_finished_at", "critical", run=run))
    if run.status == "success" and run.error_message:
        issues.append(_issue("success_run_has_error_message", "critical", run=run))
    if run.status == "failed":
        if not run.error_message:
            issues.append(_issue("failed_run_missing_error_code", "warning", run=run))
        if run.attempt_count >= retry_attempts:
            issues.append(_issue("exhausted_failed_run", "critical", run=run, retry_attempts=retry_attempts))
        else:
            issues.append(_issue("retryable_failed_run", "warning", run=run, retry_attempts=retry_attempts))
    if run.status == "pending":
        issues.append(_issue("pending_run_waiting_for_dispatch", "warning", run=run))

    if run.status == "success":
        output_counts = _snapshot_counts_for_run(db, run)
        if output_counts["user_snapshot_count"] != run.user_snapshot_count:
            issues.append(
                _issue(
                    "user_snapshot_count_mismatch",
                    "warning",
                    run=run,
                    recorded_count=run.user_snapshot_count,
                    observed_count=output_counts["user_snapshot_count"],
                )
            )
        if output_counts["class_snapshot_count"] != run.class_snapshot_count:
            issues.append(
                _issue(
                    "class_snapshot_count_mismatch",
                    "warning",
                    run=run,
                    recorded_count=run.class_snapshot_count,
                    observed_count=output_counts["class_snapshot_count"],
                )
            )
    return issues


def _queue_report(
    db: Session,
    *,
    schedule_config: SnapshotScheduleConfig,
    retry_attempts: int,
    lease_seconds: int,
    now: datetime,
    max_issues: int,
) -> dict[str, Any]:
    due_jobs = due_snapshot_jobs(now, schedule_config)
    pending_jobs = pending_snapshot_jobs(db)
    seen_jobs = {(job.granularity, job.reference_date) for job in due_jobs}
    combined_jobs = list(due_jobs)
    for job in pending_jobs:
        key = (job.granularity, job.reference_date)
        if key not in seen_jobs:
            combined_jobs.append(job)
            seen_jobs.add(key)
    issues: list[dict[str, Any]] = []
    dispatchable = 0
    blocked = 0
    fulfilled = 0
    for job in combined_jobs:
        run = _run_for_job(db, job)
        if run is None:
            dispatchable += 1
            continue
        if run.status == "pending":
            dispatchable += 1
        elif run.status == "failed" and run.attempt_count < retry_attempts:
            dispatchable += 1
        elif run.status == "running" and _run_lease_expired(run, now, lease_seconds):
            dispatchable += 1
        elif run.status == "success":
            fulfilled += 1
        else:
            blocked += 1
            issues.append(_issue("due_job_blocked_by_existing_run", "warning", run=run))
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "due_jobs": len(due_jobs),
            "pending_jobs": len(pending_jobs),
            "combined_jobs": len(combined_jobs),
            "dispatchable_jobs": dispatchable,
            "fulfilled_jobs": fulfilled,
            "blocked_jobs": blocked,
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        jobs=[_job_summary(job, db) for job in combined_jobs[:20]],
    )


def _snapshot_outputs_report(
    db: Session,
    runs: list[KnowledgeSnapshotRun],
    *,
    max_issues: int,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    latest_success_by_window: dict[tuple[str, datetime, datetime], KnowledgeSnapshotRun] = {}
    for run in runs:
        if run.status != "success":
            continue
        key = (run.granularity, _as_naive_utc(run.period_start), _as_naive_utc(run.period_end))
        current = latest_success_by_window.get(key)
        if current is None or _as_naive_utc(current.started_at) < _as_naive_utc(run.started_at):
            latest_success_by_window[key] = run
    for run in latest_success_by_window.values():
        output_counts = _snapshot_counts_for_run(db, run)
        if output_counts["user_snapshot_count"] != run.user_snapshot_count:
            issues.append(
                _issue(
                    "latest_success_user_snapshot_count_mismatch",
                    "warning",
                    run=run,
                    recorded_count=run.user_snapshot_count,
                    observed_count=output_counts["user_snapshot_count"],
                )
            )
        if output_counts["class_snapshot_count"] != run.class_snapshot_count:
            issues.append(
                _issue(
                    "latest_success_class_snapshot_count_mismatch",
                    "warning",
                    run=run,
                    recorded_count=run.class_snapshot_count,
                    observed_count=output_counts["class_snapshot_count"],
                )
            )
    user_total = int(db.scalar(select(func.count()).select_from(UserKnowledgeSnapshot)) or 0)
    class_total = int(db.scalar(select(func.count()).select_from(ClassKnowledgeSnapshot)) or 0)
    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "user_snapshots": user_total,
            "class_snapshots": class_total,
            "latest_success_windows": len(latest_success_by_window),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
    )


def _mysql_concurrency_evidence_report(dialect: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "external_evidence_required",
        "database_dialect": dialect,
        "read_only_drill": True,
        "required_checks": [
            "single scheduler instance day/week/full rebuild report",
            "two-worker same-window lease contention under MySQL",
            "heartbeat extension and stale-token finish guard",
            "admin cancel running run with lease and old worker heartbeat failure",
            "admin requeue failed/cancelled/stale running run and successful reclaim",
            "snapshot row counts before-after without duplicate effective windows",
            "connection pool and lock wait observation during rebuild",
        ],
        "policy": "this script verifies scheduler ledger posture; real MySQL lease contention evidence must be captured separately",
    }


def _section_report(
    *,
    status: str,
    counts: dict[str, int],
    issues: list[dict[str, Any]],
    max_issues: int,
    latest_runs: list[dict[str, Any]] | None = None,
    jobs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = {
        "ok": not _has_critical_issue(issues),
        "status": status,
        "counts": counts,
        "issue_counts_by_code": _counts(issues, "code"),
        "issue_counts_by_severity": _counts(issues, "severity"),
        "issues": issues[:max_issues],
        "truncated": len(issues) > max_issues,
    }
    if latest_runs is not None:
        report["latest_runs"] = latest_runs
    if jobs is not None:
        report["jobs"] = jobs
    return report


def _issue(
    code: str,
    severity: str,
    *,
    run: KnowledgeSnapshotRun | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "run_id": run.id if run is not None else None,
        "run_key_sha256": _sha256_text(run.run_key) if run is not None else None,
        "granularity": run.granularity if run is not None else None,
        "status": run.status if run is not None else None,
        "period_start": _datetime_value(run.period_start) if run is not None else None,
        "period_end": _datetime_value(run.period_end) if run is not None else None,
    }
    payload.update(extra)
    return {key: value for key, value in payload.items() if value is not None}


def _load_runs(db: Session, *, max_runs: int) -> list[KnowledgeSnapshotRun]:
    return list(
        db.scalars(
            select(KnowledgeSnapshotRun)
            .order_by(KnowledgeSnapshotRun.started_at.desc(), KnowledgeSnapshotRun.id.desc())
            .limit(max_runs)
        ).all()
    )


def _snapshot_counts_for_run(db: Session, run: KnowledgeSnapshotRun) -> dict[str, int]:
    user_count = int(
        db.scalar(
            select(func.count())
            .select_from(UserKnowledgeSnapshot)
            .where(
                UserKnowledgeSnapshot.granularity == run.granularity,
                UserKnowledgeSnapshot.period_start == run.period_start,
                UserKnowledgeSnapshot.period_end == run.period_end,
            )
        )
        or 0
    )
    class_count = int(
        db.scalar(
            select(func.count())
            .select_from(ClassKnowledgeSnapshot)
            .where(
                ClassKnowledgeSnapshot.granularity == run.granularity,
                ClassKnowledgeSnapshot.period_start == run.period_start,
                ClassKnowledgeSnapshot.period_end == run.period_end,
            )
        )
        or 0
    )
    return {
        "user_snapshot_count": user_count,
        "class_snapshot_count": class_count,
    }


def _run_for_job(db: Session, job: Any) -> KnowledgeSnapshotRun | None:
    period_start, period_end = _job_window(job)
    key = snapshot_run_key(job.granularity, period_start, period_end)
    return db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == key))


def _job_summary(job: Any, db: Session) -> dict[str, Any]:
    period_start, period_end = _job_window(job)
    run = _run_for_job(db, job)
    return {
        "granularity": job.granularity,
        "reference_date": job.reference_date.isoformat(),
        "period_start": _datetime_value(period_start),
        "period_end": _datetime_value(period_end),
        "run_exists": run is not None,
        "run_id": run.id if run is not None else None,
        "run_status": run.status if run is not None else None,
        "run_key_sha256": _sha256_text(snapshot_run_key(job.granularity, period_start, period_end)),
    }


def _job_window(job: Any) -> tuple[datetime, datetime]:
    from app.services.knowledge_snapshot_runs import snapshot_window

    return snapshot_window(job.granularity, job.reference_date)


def _run_summary(run: KnowledgeSnapshotRun, *, now: datetime, lease_seconds: int) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_key_sha256": _sha256_text(run.run_key),
        "granularity": run.granularity,
        "status": run.status,
        "period_start": _datetime_value(run.period_start),
        "period_end": _datetime_value(run.period_end),
        "trigger_source": run.trigger_source,
        "attempt_count": run.attempt_count,
        "user_snapshot_count": run.user_snapshot_count,
        "class_snapshot_count": run.class_snapshot_count,
        "started_at": _datetime_value(run.started_at),
        "finished_at": _datetime_value(run.finished_at),
        "scheduler_lease_owner_present": bool(run.scheduler_lease_owner),
        "lease_token_present": bool(run.scheduler_lease_token),
        "scheduler_lease_expires_at": _datetime_value(run.scheduler_lease_expires_at),
        "scheduler_heartbeat_at": _datetime_value(run.scheduler_heartbeat_at),
        "lease_expired": run.status == "running" and _run_lease_expired(run, now, lease_seconds),
        "error_message_present": bool(run.error_message),
        "metadata_present": bool(run.metadata_json),
    }


def _run_has_lease(run: KnowledgeSnapshotRun) -> bool:
    return any(
        (
            run.scheduler_lease_owner,
            run.scheduler_lease_token,
            run.scheduler_lease_expires_at,
            run.scheduler_heartbeat_at,
        )
    )


def _run_lease_expired(run: KnowledgeSnapshotRun, now: datetime, lease_seconds: int) -> bool:
    if run.scheduler_lease_expires_at is not None:
        return _as_naive_utc(run.scheduler_lease_expires_at) <= now
    return _as_naive_utc(run.started_at) <= now - timedelta(seconds=lease_seconds)


def _run_lease_expiring(run: KnowledgeSnapshotRun, now: datetime, lease_expiring_seconds: int) -> bool:
    if run.scheduler_lease_expires_at is None:
        return False
    expires_at = _as_naive_utc(run.scheduler_lease_expires_at)
    return now <= expires_at <= now + timedelta(seconds=lease_expiring_seconds)


def _schedule_config(settings: Any) -> SnapshotScheduleConfig:
    return SnapshotScheduleConfig(
        daily_enabled=bool(settings.knowledge_snapshot_daily_enabled),
        daily_hour=int(settings.knowledge_snapshot_daily_hour),
        weekly_enabled=bool(settings.knowledge_snapshot_weekly_enabled),
        weekly_weekday=int(settings.knowledge_snapshot_weekly_weekday),
        weekly_hour=int(settings.knowledge_snapshot_weekly_hour),
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


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _has_critical_issue(issues: Iterable[dict[str, Any]]) -> bool:
    return any(issue.get("severity") == "critical" for issue in issues)


def _counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(item.get(key)) for item in items if item.get(key) is not None))


def _evidence_required() -> list[dict[str, str]]:
    return [
        {
            "code": "mysql_lease_contention",
            "description": "真实 MySQL 下两个 worker 对同一 day/week run_key 抢租约，只有一个成功，另一个 lease_unavailable。",
        },
        {
            "code": "heartbeat_and_finish_guard",
            "description": "真实 MySQL 下 heartbeat 能续租；旧 token finish success/failure 会被拒绝并保留当前 run。",
        },
        {
            "code": "cancel_requeue_flow",
            "description": "管理员取消 running/pending、重排 failed/cancelled/stale running 后，队列和 outbox 候选状态可追踪。",
        },
        {
            "code": "snapshot_output_idempotency",
            "description": "day/week/full rebuild 前后 user/class snapshot 窗口没有重复有效行，计数与 run ledger 一致。",
        },
        {
            "code": "pool_and_lock_wait",
            "description": "重算期间记录连接池占用、锁等待、慢查询或重试情况，并确认业务查询可用。",
        },
    ]
