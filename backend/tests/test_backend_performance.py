import json
from datetime import timedelta

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import _engine_options, database_engine_posture, get_session_factory, slow_query_metadata
from app.models import AuditLog, BackgroundTask
from app.models.base import utc_now
from app.services.backend_performance import QUERY_PROFILES, performance_posture


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client) -> str:
    created = client.post(
        "/api/admin/bootstrap",
        json={"username": "performance_admin", "password": "secret123", "display_name": "Performance Admin"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "performance_admin", "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_mysql_engine_options_and_performance_posture_are_explicit_and_redacted():
    settings = Settings(
        database_pool_size=12,
        database_max_overflow=4,
        database_pool_timeout_seconds=17,
        database_pool_recycle_seconds=900,
        database_connect_timeout_seconds=8,
        database_read_timeout_seconds=21,
        database_write_timeout_seconds=22,
        performance_probe_iterations=5,
    )
    options = _engine_options("mysql+pymysql://user:private@db.example/astra", settings)
    assert options["pool_pre_ping"] is True
    assert options["pool_use_lifo"] is True
    assert options["pool_size"] == 12
    assert options["max_overflow"] == 4
    assert options["pool_timeout"] == 17
    assert options["pool_recycle"] == 900
    assert options["connect_args"] == {
        "connect_timeout": 8,
        "read_timeout": 21,
        "write_timeout": 22,
    }
    posture = performance_posture(settings)
    assert posture["worker_isolation"]["recommended_mode"] == "independent_service"
    assert posture["worker_isolation"]["pool_capacity_per_process"] == 16
    assert posture["worker_isolation"]["automatic_write_retry"] is False
    assert posture["pagination"]["admin_lists_max"] == 200
    assert posture["pagination"]["audit_export_max"] == 5000
    assert posture["probe_iterations"] == 5
    assert posture["sensitive_values_returned"] is False
    assert "private" not in json.dumps(posture)
    assert database_engine_posture(settings)["database_url_returned"] is False


def test_slow_query_metadata_never_returns_sql_or_parameters():
    statement = "SELECT * FROM users WHERE password = 'database-secret'"
    metadata = slow_query_metadata(statement, duration_ms=612.345, dialect="mysql")
    serialized = json.dumps(metadata)
    assert metadata["operation"] == "SELECT"
    assert metadata["duration_ms"] == 612.35
    assert len(metadata["query_sha256"]) == 64
    assert metadata["sql_text_logged"] is False
    assert metadata["parameters_logged"] is False
    assert "database-secret" not in serialized
    assert statement not in serialized


def test_admin_performance_report_verifies_indexes_plans_budgets_and_safe_audit(client):
    token = _bootstrap_admin(client)
    session_factory = get_session_factory("sqlite+pysqlite:///:memory:")
    now = utc_now()
    with session_factory() as db:
        db.add_all(
            BackgroundTask(
                task_type="performance_probe",
                idempotency_key=f"performance-probe-{index}",
                source_type="performance_test",
                source_id=index,
                status="pending",
                priority=index % 5,
                payload_json={},
                result_summary_json={},
                available_at=now - timedelta(seconds=index),
                attempt_count=0,
                max_attempts=3,
            )
            for index in range(250)
        )
        db.commit()
    response = client.get(
        "/api/admin/performance/report",
        headers={**_auth_header(token), "X-Request-ID": "performance-report"},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is True
    assert report["status"] == "local_contract_ready_mysql_evidence_pending"
    assert report["dialect"] == "sqlite"
    assert report["summary"]["profile_count"] == len(QUERY_PROFILES)
    assert report["summary"]["index_present_count"] == len(QUERY_PROFILES)
    assert report["summary"]["missing_index_count"] == 0
    assert report["summary"]["explain_error_count"] == 0
    assert report["summary"]["benchmark_error_count"] == 0
    assert report["summary"]["budget_exceeded_count"] == 0
    assert report["missing_indexes"] == []
    assert all(item["index_present"] for item in report["profiles"])
    assert all(item["benchmark"]["within_budget"] for item in report["profiles"])
    assert all(item["benchmark"]["maximum_rows"] <= 50 for item in report["profiles"])
    assert all(item["explain"]["full_scan_detected"] is False for item in report["profiles"])
    assert response.headers["Server-Timing"].startswith("app;dur=")
    assert float(response.headers["Server-Timing"].split("=", 1)[1]) < 5000
    response_text = response.text.lower()
    assert "select id from" not in response_text
    assert "database_url" not in response_text or '"database_url_returned":false' in response_text

    with session_factory() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "admin.performance.report"))
        assert audit.event_result == "success"
        assert audit.snapshot_json["summary"]["missing_index_count"] == 0
        assert audit.snapshot_json["sql_text_returned"] is False
        assert audit.snapshot_json["database_url_returned"] is False


def test_performance_report_requires_admin(client):
    response = client.get("/api/admin/performance/report")
    assert response.status_code == 401
