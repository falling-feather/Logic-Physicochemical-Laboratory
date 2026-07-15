import asyncio
from datetime import UTC, datetime, timedelta
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory, reset_database_state
from app.main import create_app
from app.models import ContentScriptAssetScanRun, User
from app.services.content_script_assets import ContentScriptAssetRemoteDriftReport
from app.services.content_script_asset_scan_scheduler import (
    ContentScriptRemoteDriftScheduleConfig,
    ContentScriptRemoteDriftScheduler,
)
from app.services.content_script_asset_scan_runs import (
    acquire_content_script_asset_scan_job_lease,
    finish_content_script_asset_scan_run_success,
)
from scripts.scan_content_script_asset_remote_drift import run_scan


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Cookie": ""}


def _bootstrap_admin(client) -> str:
    response = client.post(
        "/api/admin/bootstrap",
        json={"username": "admin_root", "password": "secret123", "display_name": "Root Admin"},
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": "admin_root", "password": "secret123"})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_admin_remote_drift_alerts_include_failed_and_stale_scheduler_runs(client):
    admin_token = _bootstrap_admin(client)
    now = datetime(2026, 7, 8, 14, 0, tzinfo=UTC)
    with get_session_factory(get_settings().database_url)() as db:
        db.add(
            ContentScriptAssetScanRun(
                run_key="content-script-remote-drift:scheduler:failed",
                scan_type="remote_drift",
                trigger_source="scheduler",
                status="failed",
                started_at=now - timedelta(hours=2),
                finished_at=now - timedelta(hours=1, minutes=59),
                created_by_user_id=None,
                attempt_count=2,
                filters_json={"source_host": "cdn-alert.example.test"},
                totals_json={},
                issue_counts_json={"by_code": {}, "by_severity": {}},
                issue_summary_json=[],
                alert_status="critical",
                error_message="RuntimeError",
            )
        )
        db.add(
            ContentScriptAssetScanRun(
                run_key="content-script-remote-drift:scheduler:stale",
                scan_type="remote_drift",
                trigger_source="scheduler",
                status="running",
                started_at=now - timedelta(hours=3),
                finished_at=None,
                created_by_user_id=None,
                attempt_count=1,
                scheduler_lease_owner="scheduler-alert-test",
                scheduler_lease_token="secret-scheduler-token",
                scheduler_lease_expires_at=now - timedelta(hours=1),
                scheduler_heartbeat_at=now - timedelta(hours=2),
                filters_json={"source_host": "cdn-alert.example.test"},
                totals_json={},
                issue_counts_json={"by_code": {}, "by_severity": {}},
                issue_summary_json=[],
                alert_status="ok",
                error_message=None,
            )
        )
        db.commit()

    runs = client.get(
        "/api/admin/content/script-assets/remote-drift-scan-runs?status=running",
        headers=_auth_header(admin_token),
    )
    assert runs.status_code == 200
    runs_body = runs.json()
    assert runs_body["total"] == 1
    assert runs_body["items"][0]["scheduler_lease_owner"] == "scheduler-alert-test"
    assert "scheduler_lease_token" not in json.dumps(runs_body, ensure_ascii=False)

    alerts = client.get(
        "/api/admin/content/script-assets/remote-drift-alerts"
        "?trigger_source=scheduler&recent_run_limit=10&candidate_limit=10&now=2026-07-08T14:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert alerts.status_code == 200
    alerts_body = alerts.json()
    codes = {item["code"] for item in alerts_body["candidates"]}
    assert {"scan_failed", "scan_run_stale"}.issubset(codes)
    assert alerts_body["critical_count"] == 2
    alerts_text = json.dumps(alerts_body, ensure_ascii=False)
    assert "secret-scheduler-token" not in alerts_text
    assert '"source_url"' not in alerts_text
    assert "integrity" not in alerts_text


def test_admin_remote_drift_scan_run_health_and_queue_reports_are_redacted(client, monkeypatch):
    admin_token = _bootstrap_admin(client)
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)
    with get_session_factory(get_settings().database_url)() as db:
        db.add_all(
            [
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:health-failed",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="failed",
                    started_at=now - timedelta(hours=5),
                    finished_at=now - timedelta(hours=4, minutes=55),
                    attempt_count=2,
                    filters_json={"source_host": "cdn-health.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="critical",
                    error_message="RuntimeError",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:health-stale",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="running",
                    started_at=now - timedelta(hours=4),
                    finished_at=None,
                    attempt_count=1,
                    scheduler_lease_owner="scheduler-health-stale",
                    scheduler_lease_token="secret-health-stale-token",
                    scheduler_lease_expires_at=now - timedelta(hours=2),
                    scheduler_heartbeat_at=now - timedelta(hours=3),
                    filters_json={"source_host": "cdn-health.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="ok",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:health-active",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="running",
                    started_at=now - timedelta(minutes=10),
                    finished_at=None,
                    attempt_count=1,
                    scheduler_lease_owner="scheduler-health-active",
                    scheduler_lease_token="secret-health-active-token",
                    scheduler_lease_expires_at=now + timedelta(minutes=5),
                    scheduler_heartbeat_at=now - timedelta(minutes=1),
                    filters_json={"source_host": "cdn-health.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="ok",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:health-legacy",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="running",
                    started_at=now - timedelta(hours=6),
                    finished_at=None,
                    attempt_count=1,
                    filters_json={"source_host": "cdn-health.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="ok",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:manual:health-warning",
                    scan_type="remote_drift",
                    trigger_source="manual",
                    status="success",
                    started_at=now - timedelta(hours=1),
                    finished_at=now - timedelta(minutes=55),
                    created_by_user_id=None,
                    attempt_count=1,
                    filters_json={"source_host": "cdn-health.example.test"},
                    totals_json={"total_issues": 1},
                    issue_counts_json={"by_code": {"remote_asset_unavailable": 1}, "by_severity": {"warning": 1}},
                    issue_summary_json=[],
                    alert_status="warning",
                ),
            ]
        )
        db.commit()

    health = client.get(
        "/api/admin/content/script-assets/remote-drift-scan-runs/health"
        "?problem_limit=10&lease_expiring_seconds=900&now=2026-07-08T16:00:00Z",
        headers={**_auth_header(admin_token), "X-Request-ID": "remote-drift-health"},
    )
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["health_status"] == "attention"
    assert health_body["running_count"] == 3
    assert health_body["stale_running_count"] == 2
    assert health_body["lease_expiring_count"] == 1
    assert health_body["legacy_running_without_lease_count"] == 1
    assert health_body["failed_count"] == 1
    assert health_body["warning_run_count"] == 1
    problem_flags = {flag for item in health_body["problem_runs"] for flag in item["health_flags"]}
    assert {"failed", "stale_running", "legacy_running_without_lease", "lease_expiring", "warning_issues"} <= problem_flags
    health_text = json.dumps(health_body, ensure_ascii=False)
    assert "secret-health-stale-token" not in health_text
    assert "secret-health-active-token" not in health_text
    assert "source_url" not in health_text
    assert "integrity" not in health_text

    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_SCAN_LIMIT", "5")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_SOURCE_HOST", "cdn-queue.example.test")
    get_settings.cache_clear()
    queue = client.get(
        "/api/admin/content/script-assets/remote-drift-scan-runs/queue"
        "?item_limit=10&now=2026-07-08T16:00:00Z",
        headers={**_auth_header(admin_token), "X-Request-ID": "remote-drift-queue"},
    )
    assert queue.status_code == 200
    queue_body = queue.json()
    assert queue_body["queue_status"] == "ready"
    assert queue_body["dispatchable_now_count"] == 1
    assert queue_body["manual_review_count"] == 3
    assert queue_body["blocked_count"] == 1
    assert queue_body["failed_count"] == 1
    assert queue_body["stale_running_count"] == 2
    assert queue_body["active_running_count"] == 1
    assert queue_body["ready_jobs"][0]["source"] == "due"
    assert queue_body["ready_jobs"][0]["reason"] == "scheduler_window_missing_run"
    assert {item["source"] for item in queue_body["manual_review_runs"]} >= {"failed", "stale_running"}
    queue_text = json.dumps(queue_body, ensure_ascii=False)
    assert "secret-health-stale-token" not in queue_text
    assert "secret-health-active-token" not in queue_text
    assert "source_url" not in queue_text
    assert "integrity" not in queue_text

    for action, request_id in [
        ("admin.content_script_asset.remote_drift_scan_run.health_report", "remote-drift-health"),
        ("admin.content_script_asset.remote_drift_scan_run.queue_report", "remote-drift-queue"),
    ]:
        audit = client.get(
            f"/api/admin/audit-logs?action={action}&resource_type=content_script_asset_scan_run&request_id={request_id}",
            headers=_auth_header(admin_token),
        )
        assert audit.status_code == 200
        assert audit.json()["total"] == 1
        audit_text = json.dumps(audit.json()["items"][0]["snapshot_json"], ensure_ascii=False)
        assert "secret-health-stale-token" not in audit_text
        assert "secret-health-active-token" not in audit_text
        assert "source_url" not in audit_text
        assert "integrity" not in audit_text


def test_content_script_remote_drift_scheduler_run_once_writes_observe_only_run(client, monkeypatch):
    actor_id = _insert_admin_user("script_scheduler_admin")
    captured = {}
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

    def fake_scan(db, **kwargs):
        captured.update(kwargs)
        return ContentScriptAssetRemoteDriftReport(
            generated_at=kwargs["generated_at"],
            total_pages_scanned=2,
            total_external_references=3,
            total_scanned_references=1,
            total_remote_fetches=1,
            total_skipped_references=0,
            total_issues=0,
            issue_counts_by_code={},
            issue_counts_by_severity={},
            issues=[],
        )

    monkeypatch.setattr("app.services.content_script_asset_scan_scheduler.scan_current_content_script_asset_remote_drift", fake_scan)
    monkeypatch.setattr(
        "app.services.content_script_asset_scan_runs.utc_now",
        lambda: now + timedelta(seconds=1),
    )
    scheduler = ContentScriptRemoteDriftScheduler(
        database_url=get_settings().database_url,
        schedule_config=ContentScriptRemoteDriftScheduleConfig(
            scan_limit=1,
            source_host="cdn-scheduler.example.test",
            actor_user_id=actor_id,
        ),
        interval_seconds=3600,
        lease_seconds=3600,
        clock=lambda: now + timedelta(seconds=1),
        instance_id="scheduler-test",
    )

    result = asyncio.run(scheduler.run_once(now))

    assert result["ok"] is True
    assert result["status"] == "success"
    assert result["total_remote_fetches"] == 1
    assert captured["source_host"] == "cdn-scheduler.example.test"
    assert captured["scan_limit"] == 1
    with get_session_factory(get_settings().database_url)() as db:
        run = db.get(ContentScriptAssetScanRun, result["run_id"])
        assert run is not None
        assert run.trigger_source == "scheduler"
        assert run.status == "success"
        assert run.created_by_user_id == actor_id
        assert run.attempt_count == 1
        assert run.scheduler_lease_token is None
        assert run.scheduler_lease_owner is None
        assert run.filters_json == {
            "source_host": "cdn-scheduler.example.test",
            "limit": 1,
            "offset": 0,
            "confirm_external_network": True,
        }

    skipped = asyncio.run(scheduler.run_once(now))
    assert skipped == {"ok": True, "status": "skipped", "reason": "lease_unavailable", "run_key": result["run_key"]}


def test_content_script_remote_drift_scheduler_records_failed_run_without_exception_text(client, monkeypatch):
    actor_id = _insert_admin_user("script_scheduler_failure_admin")
    now = datetime(2026, 7, 8, 13, 0, tzinfo=UTC)
    def fake_scan(db, **kwargs):
        raise RuntimeError("secret scheduler token")

    monkeypatch.setattr("app.services.content_script_asset_scan_scheduler.scan_current_content_script_asset_remote_drift", fake_scan)
    monkeypatch.setattr(
        "app.services.content_script_asset_scan_runs.utc_now",
        lambda: now + timedelta(seconds=1),
    )
    scheduler = ContentScriptRemoteDriftScheduler(
        database_url=get_settings().database_url,
        schedule_config=ContentScriptRemoteDriftScheduleConfig(scan_limit=1, actor_user_id=actor_id),
        interval_seconds=3600,
        lease_seconds=3600,
        clock=lambda: now + timedelta(seconds=1),
        instance_id="scheduler-failure-test",
    )

    result = asyncio.run(scheduler.run_once(now))

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error"] == "RuntimeError"
    with get_session_factory(get_settings().database_url)() as db:
        run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == result["run_key"]))
        assert run is not None
        assert run.status == "failed"
        assert run.trigger_source == "scheduler"
        assert run.created_by_user_id == actor_id
        assert run.error_message == "RuntimeError"
        stored = json.dumps(
            {
                "filters": run.filters_json,
                "totals": run.totals_json,
                "issue_counts": run.issue_counts_json,
                "issue_summary": run.issue_summary_json,
                "error_message": run.error_message,
            },
            ensure_ascii=False,
        )
        assert "secret scheduler token" not in stored
        assert "source_url" not in stored
        assert "integrity" not in stored
        assert "content_bytes" not in stored


def test_content_script_remote_drift_scheduler_registration_is_opt_in(monkeypatch):
    monkeypatch.setenv("ASTRA_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()
    reset_database_state()
    with TestClient(create_app()) as test_client:
        assert not hasattr(test_client.app.state, "content_script_remote_drift_scheduler")

    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_RUN_ON_START", "false")
    get_settings.cache_clear()
    reset_database_state()
    with TestClient(create_app()) as test_client:
        assert hasattr(test_client.app.state, "content_script_remote_drift_scheduler")

    get_settings.cache_clear()
    reset_database_state()


def test_content_script_remote_drift_cli_requires_confirmation_and_writes_script_run(client, monkeypatch):
    actor_id = _insert_admin_user("script_cli_admin")
    inactive_actor_id = _insert_admin_user("script_cli_inactive_admin", status="disabled")

    assert run_scan(confirm_external_network=False)["error"] == "ExternalNetworkConfirmationRequired"
    assert (
        run_scan(
            confirm_external_network=True,
            actor_user_id=inactive_actor_id,
            database_url=get_settings().database_url,
        )["error"]
        == "ActiveAdminActorRequired"
    )
    assert (
        run_scan(
            confirm_external_network=True,
            database_url=get_settings().database_url,
        )["error"]
        == "ActiveAdminActorRequired"
    )

    def fake_scan(db, **kwargs):
        return ContentScriptAssetRemoteDriftReport(
            generated_at=kwargs["generated_at"],
            total_pages_scanned=1,
            total_external_references=1,
            total_scanned_references=1,
            total_remote_fetches=1,
            total_skipped_references=0,
            total_issues=0,
            issue_counts_by_code={},
            issue_counts_by_severity={},
            issues=[],
        )

    monkeypatch.setattr("scripts.scan_content_script_asset_remote_drift.scan_current_content_script_asset_remote_drift", fake_scan)
    report = run_scan(
        confirm_external_network=True,
        actor_user_id=actor_id,
        source_host="cdn-cli.example.test",
        limit=1,
        database_url=get_settings().database_url,
    )

    assert report["ok"] is True
    assert report["status"] == "success"
    assert report["trigger_source"] == "script"
    with get_session_factory(get_settings().database_url)() as db:
        run = db.get(ContentScriptAssetScanRun, report["run_id"])
        assert run is not None
        assert run.trigger_source == "script"
        assert run.created_by_user_id == actor_id
        assert run.filters_json["source_host"] == "cdn-cli.example.test"
        assert run.scheduler_lease_token is None


def _insert_admin_user(username: str, *, status: str = "active") -> int:
    with get_session_factory(get_settings().database_url)() as db:
        user = User(
            username=username,
            normalized_username=username,
            display_name=username.replace("_", " ").title(),
            password_hash="test",
            role="admin",
            status=status,
        )
        db.add(user)
        db.commit()
        return user.id


def test_reclaimed_scan_lease_cannot_be_overwritten_by_stale_worker(client, monkeypatch):
    started_at = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    run_key = "content-script-remote-drift:test:reclaimed"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first_lease = acquire_content_script_asset_scan_job_lease(
            db,
            run_key=run_key,
            trigger_source="pytest",
            request_filters={"limit": 1},
            lease_owner="worker-a",
            lease_seconds=60,
            now=started_at,
        )
    with session_factory() as db:
        second_lease = acquire_content_script_asset_scan_job_lease(
            db,
            run_key=run_key,
            trigger_source="pytest",
            request_filters={"limit": 1},
            lease_owner="worker-b",
            lease_seconds=60,
            now=started_at + timedelta(seconds=120),
        )
    assert first_lease is not None
    assert second_lease is not None
    report = ContentScriptAssetRemoteDriftReport(
        generated_at=started_at + timedelta(seconds=121),
        total_pages_scanned=0,
        total_external_references=0,
        total_scanned_references=0,
        total_remote_fetches=0,
        total_skipped_references=0,
        total_issues=0,
        issue_counts_by_code={},
        issue_counts_by_severity={},
        issues=[],
    )
    monkeypatch.setattr("app.services.content_script_asset_scan_runs.utc_now", lambda: report.generated_at)
    with session_factory() as db:
        assert finish_content_script_asset_scan_run_success(
            db,
            first_lease,
            report=report,
            finished_at=report.generated_at,
        ) is None
        db.rollback()
    with session_factory() as db:
        completed = finish_content_script_asset_scan_run_success(
            db,
            second_lease,
            report=report,
            finished_at=report.generated_at,
        )
        assert completed is not None
        db.commit()
    with session_factory() as db:
        run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
        assert run.status == "success"
        assert run.attempt_count == 2
        assert run.scheduler_lease_owner is None
        assert run.scheduler_lease_token is None
