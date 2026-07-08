import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.db.session import get_session_factory, init_db, reset_database_state
from app.models import ClassKnowledgeSnapshot, KnowledgeSnapshotRun, UserKnowledgeSnapshot
from app.services.knowledge_snapshot_runs import snapshot_run_key, snapshot_window
from app.services.knowledge_snapshot_scheduler_drill import run_knowledge_snapshot_scheduler_drill
from scripts.knowledge_snapshot_scheduler_drill import run_knowledge_snapshot_scheduler_drill_report


def test_knowledge_snapshot_scheduler_drill_reports_ready_read_only_posture():
    database_url = _database_url()
    _init_database(database_url)
    period_start, period_end = snapshot_window("day", date(2026, 7, 8))
    with get_session_factory(database_url)() as db:
        db.add(
            KnowledgeSnapshotRun(
                run_key=snapshot_run_key("day", period_start, period_end),
                granularity="day",
                period_start=period_start,
                period_end=period_end,
                trigger_source="scheduler",
                status="success",
                started_at=datetime(2026, 7, 9, 3, 0),
                finished_at=datetime(2026, 7, 9, 3, 1),
                attempt_count=1,
                user_snapshot_count=0,
                class_snapshot_count=0,
                metadata_json={"trigger_source": "scheduler", "scheduler_lease_token": "secret-token"},
            )
        )
        db.commit()

    with get_session_factory(database_url)() as db:
        report = run_knowledge_snapshot_scheduler_drill(
            db,
            database_url=database_url,
            settings=_settings(scheduler_enabled=True),
            now=datetime(2026, 7, 9, 5, 0, tzinfo=UTC),
        )

    assert report["ok"] is True
    assert report["status"] == "ready_for_mysql_evidence"
    assert report["mode"] == "read_only"
    assert report["database"]["dialect"] == "sqlite"
    assert report["configuration"]["scheduler_enabled"] is True
    assert report["run_ledger"]["counts"]["success"] == 1
    assert report["queue"]["counts"]["fulfilled_jobs"] == 1
    assert report["queue"]["counts"]["issues"] == 0
    assert report["snapshot_outputs"]["counts"]["latest_success_windows"] == 1
    assert report["mysql_concurrency_evidence"]["status"] == "external_evidence_required"
    assert report["sensitive_fields_returned"] is False
    report_text = json.dumps(report, ensure_ascii=False)
    assert "secret-token" not in report_text
    assert "scheduler_lease_token" not in report_text
    assert "metadata_json" not in report_text


def test_knowledge_snapshot_scheduler_drill_require_mysql_rejects_sqlite_and_disabled_scheduler():
    database_url = _database_url()
    _init_database(database_url)

    report = run_knowledge_snapshot_scheduler_drill_report(
        database_url=database_url,
        require_mysql=True,
        expect_scheduler_enabled=True,
    )

    assert report["ok"] is False
    assert report["database"]["status"] == "mysql_required"
    assert report["configuration"]["ok"] is False
    assert "scheduler_disabled_when_expected" in report["configuration"]["issue_counts_by_code"]


def test_knowledge_snapshot_scheduler_drill_detects_bad_run_ledger_states():
    database_url = _database_url()
    _init_database(database_url)
    stale_start, stale_end = snapshot_window("day", date(2026, 7, 10))
    terminal_start, terminal_end = snapshot_window("day", date(2026, 7, 11))
    failed_start, failed_end = snapshot_window("week", date(2026, 7, 6))
    with get_session_factory(database_url)() as db:
        db.add_all(
            [
                KnowledgeSnapshotRun(
                    run_key=snapshot_run_key("day", stale_start, stale_end),
                    granularity="day",
                    period_start=stale_start,
                    period_end=stale_end,
                    trigger_source="scheduler",
                    status="running",
                    started_at=datetime(2026, 7, 11, 3, 0),
                    attempt_count=1,
                    metadata_json={"trigger_source": "scheduler"},
                ),
                KnowledgeSnapshotRun(
                    run_key=snapshot_run_key("day", terminal_start, terminal_end),
                    granularity="day",
                    period_start=terminal_start,
                    period_end=terminal_end,
                    trigger_source="scheduler",
                    status="success",
                    started_at=datetime(2026, 7, 12, 3, 0),
                    finished_at=datetime(2026, 7, 12, 3, 5),
                    scheduler_lease_owner="worker-terminal",
                    scheduler_lease_token="secret-terminal-token",
                    scheduler_lease_expires_at=datetime(2026, 7, 12, 4, 0),
                    scheduler_heartbeat_at=datetime(2026, 7, 12, 3, 30),
                    attempt_count=1,
                    metadata_json={"trigger_source": "scheduler"},
                ),
                KnowledgeSnapshotRun(
                    run_key="knowledge:week:wrong",
                    granularity="week",
                    period_start=failed_start,
                    period_end=failed_end,
                    trigger_source="scheduler",
                    status="failed",
                    started_at=datetime(2026, 7, 13, 4, 0),
                    finished_at=datetime(2026, 7, 13, 4, 1),
                    attempt_count=3,
                    error_message="RuntimeError",
                    metadata_json={"trigger_source": "scheduler"},
                ),
            ]
        )
        db.commit()

    with get_session_factory(database_url)() as db:
        report = run_knowledge_snapshot_scheduler_drill(
            db,
            database_url=database_url,
            settings=_settings(scheduler_enabled=True, retry_attempts=3),
            now=datetime(2026, 7, 13, 5, 0),
        )

    assert report["ok"] is False
    codes = report["run_ledger"]["issue_counts_by_code"]
    assert "running_missing_scheduler_lease" in codes
    assert "terminal_run_still_has_scheduler_lease" in codes
    assert "run_key_window_mismatch" in codes
    assert "exhausted_failed_run" in codes
    report_text = json.dumps(report, ensure_ascii=False)
    assert "secret-terminal-token" not in report_text


def test_knowledge_snapshot_scheduler_drill_flags_stale_running_without_failing():
    database_url = _database_url()
    _init_database(database_url)
    period_start, period_end = snapshot_window("day", date(2026, 7, 14))
    with get_session_factory(database_url)() as db:
        db.add(
            KnowledgeSnapshotRun(
                run_key=snapshot_run_key("day", period_start, period_end),
                granularity="day",
                period_start=period_start,
                period_end=period_end,
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 15, 3, 0),
                scheduler_lease_owner="worker-stale",
                scheduler_lease_token="secret-stale-token",
                scheduler_lease_expires_at=datetime(2026, 7, 15, 4, 0),
                scheduler_heartbeat_at=datetime(2026, 7, 15, 3, 30),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            )
        )
        db.commit()

    with get_session_factory(database_url)() as db:
        report = run_knowledge_snapshot_scheduler_drill(
            db,
            database_url=database_url,
            settings=_settings(scheduler_enabled=True),
            now=datetime(2026, 7, 15, 4, 30),
        )

    assert report["ok"] is True
    assert report["run_ledger"]["ok"] is True
    assert report["run_ledger"]["issue_counts_by_code"] == {"stale_running_lease_expired": 1}
    assert report["run_ledger"]["issue_counts_by_severity"] == {"warning": 1}
    assert "secret-stale-token" not in json.dumps(report, ensure_ascii=False)


def test_knowledge_snapshot_scheduler_drill_reports_snapshot_count_mismatch_as_warning():
    database_url = _database_url()
    _init_database(database_url)
    period_start, period_end = snapshot_window("day", date(2026, 7, 16))
    with get_session_factory(database_url)() as db:
        db.add(
            KnowledgeSnapshotRun(
                run_key=snapshot_run_key("day", period_start, period_end),
                granularity="day",
                period_start=period_start,
                period_end=period_end,
                trigger_source="script",
                status="success",
                started_at=datetime(2026, 7, 17, 3, 0),
                finished_at=datetime(2026, 7, 17, 3, 10),
                attempt_count=1,
                user_snapshot_count=2,
                class_snapshot_count=1,
                metadata_json={"trigger_source": "script"},
            )
        )
        db.add(
            UserKnowledgeSnapshot(
                user_id=1,
                school_id=1,
                class_id=1,
                class_scope_id=1,
                course_id=1,
                course_scope_id=1,
                granularity="day",
                period_start=period_start,
                period_end=period_end,
                created_by_user_id=1,
            )
        )
        db.add(
            ClassKnowledgeSnapshot(
                school_id=1,
                class_id=1,
                course_id=1,
                course_scope_id=1,
                granularity="day",
                period_start=period_start,
                period_end=period_end,
                created_by_user_id=1,
            )
        )
        db.commit()

    with get_session_factory(database_url)() as db:
        report = run_knowledge_snapshot_scheduler_drill(
            db,
            database_url=database_url,
            settings=_settings(scheduler_enabled=True),
            now=datetime(2026, 7, 17, 5, 0),
        )

    assert report["ok"] is True
    assert "user_snapshot_count_mismatch" in report["run_ledger"]["issue_counts_by_code"]
    assert "latest_success_user_snapshot_count_mismatch" in report["snapshot_outputs"]["issue_counts_by_code"]


def _init_database(database_url: str) -> None:
    reset_database_state()
    init_db(database_url)


def _database_url() -> str:
    return "sqlite+pysqlite:///:memory:"


def _settings(**overrides):
    values = {
        "knowledge_snapshot_scheduler_enabled": False,
        "knowledge_snapshot_scheduler_run_on_start": False,
        "knowledge_snapshot_scheduler_interval_seconds": 300,
        "knowledge_snapshot_scheduler_lease_seconds": 3600,
        "knowledge_snapshot_scheduler_heartbeat_seconds": 120,
        "knowledge_snapshot_daily_enabled": True,
        "knowledge_snapshot_daily_hour": 3,
        "knowledge_snapshot_weekly_enabled": True,
        "knowledge_snapshot_weekly_weekday": 0,
        "knowledge_snapshot_weekly_hour": 4,
        "knowledge_snapshot_retry_attempts": 3,
    }
    if "scheduler_enabled" in overrides:
        overrides["knowledge_snapshot_scheduler_enabled"] = overrides.pop("scheduler_enabled")
    if "retry_attempts" in overrides:
        overrides["knowledge_snapshot_retry_attempts"] = overrides.pop("retry_attempts")
    values.update(overrides)
    return SimpleNamespace(**values)
