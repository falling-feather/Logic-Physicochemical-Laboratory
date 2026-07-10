from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine, reset_database_state
import scripts.deploy_preflight as deploy_preflight
from scripts.deploy_preflight import run_preflight


def test_deploy_preflight_reports_migrated_database(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    runtime_dir = backend_root / "pytest-cache-files-preflight"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"preflight-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
        get_settings.cache_clear()
        reset_database_state()

        config = Config(str(backend_root / "alembic.ini"))
        config.set_main_option("script_location", str(backend_root / "alembic"))
        command.upgrade(config, "head")

        report = run_preflight(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is True
        assert report["configuration"]["ok"] is True
        assert report["configuration"]["status"] == "ready"
        assert report["configuration"]["auto_create_tables"] is False
        assert report["configuration"]["expected_auto_create_tables"] is False
        assert report["configuration"]["background_task_worker"]["enabled"] is False
        assert report["configuration"]["background_task_worker"]["queue_backend"] == "database"
        assert report["configuration"]["background_task_worker"]["payload_returned"] is False
        assert report["configuration"]["background_task_worker"]["lease_token_returned"] is False
        assert report["configuration"]["audit_anchor"]["enabled"] is False
        assert report["configuration"]["audit_anchor"]["payload_policy"] == "hashes_and_range_only"
        assert report["configuration"]["external_issue_sync"]["enabled"] is False
        assert report["configuration"]["external_issue_sync"]["local_authority"] is True
        assert report["database"]["ok"] is True
        assert report["migrations"]["status"] == "up_to_date"
        assert report["migrations"]["current"] == report["migrations"]["heads"]
        assert report["compatibility"]["ok"] is True
        assert report["compatibility"]["status"] == "skipped_non_mysql"
        assert report["compatibility"]["dialect"] == "sqlite"
        assert report["compatibility"]["require_mysql"] is False
    finally:
        make_engine(database_url).dispose()
        get_settings.cache_clear()
        reset_database_state()
        if database_path.exists():
            database_path.unlink()


def test_deploy_preflight_can_require_mysql(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    runtime_dir = backend_root / "pytest-cache-files-preflight"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"preflight-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
        get_settings.cache_clear()
        reset_database_state()

        config = Config(str(backend_root / "alembic.ini"))
        config.set_main_option("script_location", str(backend_root / "alembic"))
        command.upgrade(config, "head")

        report = run_preflight(database_url=database_url, backend_root=backend_root, require_mysql=True)

        assert report["ok"] is False
        assert report["configuration"]["ok"] is True
        assert report["configuration"]["status"] == "ready"
        assert report["configuration"]["auto_create_tables"] is False
        assert report["configuration"]["require_mysql"] is True
        assert report["configuration"]["background_task_worker"]["execution_mode"] == "hybrid_domain_ledgers"
        assert report["database"]["ok"] is True
        assert report["migrations"]["status"] == "up_to_date"
        assert report["compatibility"]["ok"] is False
        assert report["compatibility"]["status"] == "unexpected_dialect"
        assert report["compatibility"]["dialect"] == "sqlite"
        assert report["compatibility"]["require_mysql"] is True
    finally:
        make_engine(database_url).dispose()
        get_settings.cache_clear()
        reset_database_state()
        if database_path.exists():
            database_path.unlink()


def test_deploy_preflight_allows_development_auto_create_without_mysql_requirement(monkeypatch):
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "true")
    get_settings.cache_clear()

    report = deploy_preflight._configuration_report(get_settings(), require_mysql=False)

    assert report["ok"] is True
    assert report["status"] == "allowed_development_auto_create"
    assert report["auto_create_tables"] is True
    assert report["expected_auto_create_tables"] is False


def test_deploy_preflight_require_mysql_rejects_auto_create_tables(monkeypatch):
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "true")
    get_settings.cache_clear()

    report = deploy_preflight._configuration_report(get_settings(), require_mysql=True)

    assert report["ok"] is False
    assert report["status"] == "auto_create_tables_enabled"
    assert report["auto_create_tables"] is True
    assert report["expected_auto_create_tables"] is False


def test_deploy_preflight_require_mysql_accepts_disabled_auto_create(monkeypatch):
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "false")
    get_settings.cache_clear()

    report = deploy_preflight._configuration_report(get_settings(), require_mysql=True)

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["auto_create_tables"] is False
    assert report["expected_auto_create_tables"] is False


def test_deploy_preflight_rejects_enabled_but_incomplete_alert_delivery(monkeypatch):
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_WEBHOOK_URL", "")
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_WEBHOOK_TOKEN", "")
    get_settings.cache_clear()

    report = deploy_preflight._configuration_report(get_settings(), require_mysql=False)

    assert report["ok"] is False
    assert report["status"] == "alert_delivery_not_configured"
    assert report["alert_delivery"]["enabled"] is True
    assert report["alert_delivery"]["configured"] is False
    assert "url" not in report["alert_delivery"]
    assert "token" not in report["alert_delivery"]


def test_deploy_preflight_accepts_complete_alert_delivery_without_leaking_credentials(monkeypatch):
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_ENABLED", "true")
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_WEBHOOK_URL", "https://alerts.example.test/astra")
    monkeypatch.setenv("ASTRA_ALERT_DELIVERY_WEBHOOK_TOKEN", "preflight-secret-token")
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "false")
    get_settings.cache_clear()

    report = deploy_preflight._configuration_report(get_settings(), require_mysql=False)

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["alert_delivery"]["enabled"] is True
    assert report["alert_delivery"]["configured"] is True
    assert "alerts.example.test" not in str(report)
    assert "preflight-secret-token" not in str(report)


def test_deploy_preflight_rejects_incomplete_audit_anchor_and_accepts_https_configuration(monkeypatch):
    monkeypatch.setenv("ASTRA_AUDIT_ANCHOR_ENABLED", "true")
    monkeypatch.setenv("ASTRA_AUDIT_ANCHOR_WEBHOOK_URL", "")
    monkeypatch.setenv("ASTRA_AUDIT_ANCHOR_WEBHOOK_TOKEN", "")
    get_settings.cache_clear()

    incomplete = deploy_preflight._configuration_report(get_settings(), require_mysql=False)
    assert incomplete["ok"] is False
    assert incomplete["status"] == "audit_anchor_not_configured"
    assert incomplete["audit_anchor"]["enabled"] is True
    assert incomplete["audit_anchor"]["configured"] is False
    assert "url" not in incomplete["audit_anchor"]
    assert "token" not in incomplete["audit_anchor"]

    monkeypatch.setenv("ASTRA_AUDIT_ANCHOR_WEBHOOK_URL", "https://anchor.example.test/v1/receipts")
    monkeypatch.setenv("ASTRA_AUDIT_ANCHOR_WEBHOOK_TOKEN", "audit-anchor-secret-token")
    get_settings.cache_clear()
    complete = deploy_preflight._configuration_report(get_settings(), require_mysql=False)
    assert complete["ok"] is True
    assert complete["status"] == "ready"
    assert complete["audit_anchor"]["configured"] is True
    assert "anchor.example.test" not in str(complete)
    assert "audit-anchor-secret-token" not in str(complete)


def test_deploy_preflight_rejects_incomplete_external_issue_sync_and_redacts_target(monkeypatch):
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_ENABLED", "true")
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_OWNER", "")
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_REPO", "")
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_TOKEN", "")
    get_settings.cache_clear()

    incomplete = deploy_preflight._configuration_report(get_settings(), require_mysql=False)
    assert incomplete["ok"] is False
    assert incomplete["status"] == "external_issue_sync_not_configured"
    assert incomplete["external_issue_sync"]["enabled"] is True
    assert incomplete["external_issue_sync"]["configured"] is False

    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_OWNER", "example")
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_REPO", "private-astra")
    monkeypatch.setenv("ASTRA_EXTERNAL_ISSUE_SYNC_GITHUB_TOKEN", "issue-sync-secret-token")
    get_settings.cache_clear()
    complete = deploy_preflight._configuration_report(get_settings(), require_mysql=False)
    assert complete["ok"] is True
    assert complete["status"] == "ready"
    assert complete["external_issue_sync"]["configured"] is True
    assert complete["external_issue_sync"]["local_authority"] is True
    assert "private-astra" not in str(complete)
    assert "issue-sync-secret-token" not in str(complete)


def test_deploy_preflight_mysql_compatibility_accepts_utf8mb4(monkeypatch):
    report = _mysql_compatibility_report(
        monkeypatch,
        {
            "character_set_database": "utf8mb4",
            "collation_database": "utf8mb4_unicode_ci",
            "character_set_connection": "utf8mb4",
            "collation_connection": "utf8mb4_unicode_ci",
            "time_zone": "+00:00",
            "system_time_zone": "UTC",
            "server_version": "8.0.36",
            "server_version_comment": "MySQL Community Server",
            "sql_mode": "STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION",
            "max_connections": "151",
            "database_name": "astra_staging",
            "current_user": "astra@localhost",
        },
    )

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["dialect"] == "mysql"
    assert report["driver"] == "pymysql"
    assert report["expected_character_set"] == "utf8mb4"
    assert report["expected_collation_prefix"] == "utf8mb4_"
    assert report["time_zone"] == "+00:00"
    assert report["system_time_zone"] == "UTC"
    assert report["server_version"] == "8.0.36"
    assert report["server_version_comment"] == "MySQL Community Server"
    assert report["sql_mode"] == "STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION"
    assert report["max_connections"] == 151
    assert report["database_name"] == "astra_staging"
    assert report["current_user"] == "astra@localhost"
    assert report["time_zone_policy"] == "reported_only"
    assert report["max_connections_policy"] == "reported_only"
    assert report["sql_mode_policy"] == "reported_only"


def test_deploy_preflight_mysql_compatibility_rejects_charset_mismatch(monkeypatch):
    report = _mysql_compatibility_report(
        monkeypatch,
        {
            "character_set_database": "utf8",
            "collation_database": "utf8_general_ci",
            "character_set_connection": "utf8mb4",
            "collation_connection": "utf8mb4_unicode_ci",
            "time_zone": "SYSTEM",
        },
    )

    assert report["ok"] is False
    assert report["status"] == "mysql_charset_mismatch"
    assert report["character_set_database"] == "utf8"
    assert report["collation_database"] == "utf8_general_ci"


def test_user_normalized_username_migration_rejects_duplicates(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    try:
        command.upgrade(config, "20260706_0021")
        _insert_user(database_url, "LegacyTeacher")
        _insert_user(database_url, "legacyteacher")

        with pytest.raises(RuntimeError, match="Duplicate normalized usernames"):
            command.upgrade(config, "head")
    finally:
        _dispose_and_remove(database_url, database_path)


def test_login_attempt_normalized_username_migration_clears_duplicate_buckets(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    try:
        command.upgrade(config, "20260706_0021")
        _insert_login_attempt(database_url, "CaseLockTeacher")
        _insert_login_attempt(database_url, "caselockteacher")

        command.upgrade(config, "head")

        engine = make_engine(database_url)
        with engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM login_attempts")).scalar_one()
            assert int(count) == 0
    finally:
        _dispose_and_remove(database_url, database_path)


def test_auth_session_device_metadata_migration_preserves_legacy_sessions(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    try:
        command.upgrade(config, "20260706_0022")
        user_id = _insert_normalized_user(database_url, "legacy_device_teacher")
        session_id = _insert_auth_session(database_url, user_id)

        command.upgrade(config, "head")

        engine = make_engine(database_url)
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT device_label, user_agent, last_seen_at, last_seen_ip_hash
                    FROM auth_sessions
                    WHERE id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).mappings().one()
            assert row["device_label"] is None
            assert row["user_agent"] is None
            assert row["last_seen_at"] is None
            assert row["last_seen_ip_hash"] is None
    finally:
        _dispose_and_remove(database_url, database_path)


def test_audit_log_chain_hash_migration_preserves_legacy_logs(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    try:
        command.upgrade(config, "20260707_0024")
        audit_id = _insert_audit_log(database_url)

        command.upgrade(config, "head")

        engine = make_engine(database_url)
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT prev_hash, current_hash
                    FROM audit_logs
                    WHERE id = :audit_id
                    """
                ),
                {"audit_id": audit_id},
            ).mappings().one()
            assert row["prev_hash"] is None
            assert row["current_hash"] is None
    finally:
        _dispose_and_remove(database_url, database_path)


def test_knowledge_snapshot_run_lease_migration_preserves_legacy_runs(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    try:
        command.upgrade(config, "20260707_0025")
        run_id = _insert_knowledge_snapshot_run(database_url)

        command.upgrade(config, "head")

        engine = make_engine(database_url)
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT scheduler_lease_owner, scheduler_lease_token,
                           scheduler_lease_expires_at, scheduler_heartbeat_at
                    FROM knowledge_snapshot_runs
                    WHERE id = :run_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().one()
            assert row["scheduler_lease_owner"] is None
            assert row["scheduler_lease_token"] is None
            assert row["scheduler_lease_expires_at"] is None
            assert row["scheduler_heartbeat_at"] is None
    finally:
        _dispose_and_remove(database_url, database_path)


def _empty_sqlite_database(monkeypatch, backend_root: Path) -> tuple[Path, str]:
    runtime_dir = backend_root / "pytest-cache-files-preflight"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"preflight-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
    get_settings.cache_clear()
    reset_database_state()
    return database_path, database_url


def _alembic_config(backend_root: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def _mysql_compatibility_report(monkeypatch, variables: dict[str, str]) -> dict[str, object]:
    monkeypatch.setattr(deploy_preflight, "make_engine", lambda database_url: _FakeMysqlEngine(variables))
    return deploy_preflight._database_compatibility_report(
        "mysql+pymysql://astra:secret@127.0.0.1:3306/astra?charset=utf8mb4",
        require_mysql=True,
    )


class _FakeMysqlDialect:
    name = "mysql"
    driver = "pymysql"


class _FakeMysqlEngine:
    dialect = _FakeMysqlDialect()

    def __init__(self, variables: dict[str, str]) -> None:
        self._variables = variables

    def connect(self) -> "_FakeMysqlConnection":
        return _FakeMysqlConnection(self._variables)

    def dispose(self) -> None:
        pass


class _FakeMysqlConnection:
    def __init__(self, variables: dict[str, str]) -> None:
        self._variables = variables

    def __enter__(self) -> "_FakeMysqlConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execute(self, statement: object) -> "_FakeMysqlResult":
        return _FakeMysqlResult(self._variables)


class _FakeMysqlResult:
    def __init__(self, variables: dict[str, str]) -> None:
        self._variables = variables

    def mappings(self) -> "_FakeMysqlResult":
        return self

    def one(self) -> dict[str, str]:
        return self._variables


def _insert_user(database_url: str, username: str) -> None:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    username, display_name, password_hash, role, status, created_at, updated_at
                )
                VALUES (
                    :username, :display_name, :password_hash, :role, :status, :created_at, :updated_at
                )
                """
            ),
            {
                "username": username,
                "display_name": username,
                "password_hash": "not-used-in-test",
                "role": "teacher",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )


def _insert_login_attempt(database_url: str, username: str) -> None:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO login_attempts (
                    username, failure_count, locked_until, last_failed_at, created_at, updated_at
                )
                VALUES (
                    :username, :failure_count, NULL, :last_failed_at, :created_at, :updated_at
                )
                """
            ),
            {
                "username": username,
                "failure_count": 1,
                "last_failed_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )


def _insert_normalized_user(database_url: str, username: str) -> int:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                INSERT INTO users (
                    username, normalized_username, display_name, password_hash, role, status, created_at, updated_at
                )
                VALUES (
                    :username, :normalized_username, :display_name, :password_hash, :role, :status,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "username": username,
                "normalized_username": username.lower(),
                "display_name": username,
                "password_hash": "not-used-in-test",
                "role": "teacher",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        return int(result.lastrowid)


def _insert_auth_session(database_url: str, user_id: int) -> int:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                INSERT INTO auth_sessions (
                    user_id, token_hash, expires_at, revoked_at, created_at, updated_at
                )
                VALUES (
                    :user_id, :token_hash, :expires_at, NULL, :created_at, :updated_at
                )
                """
            ),
            {
                "user_id": user_id,
                "token_hash": f"legacy-token-{user_id}",
                "expires_at": now + timedelta(days=7),
                "created_at": now,
                "updated_at": now,
            },
        )
        return int(result.lastrowid)


def _insert_audit_log(database_url: str) -> int:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                INSERT INTO audit_logs (
                    actor_user_id, actor_role, action, resource, resource_type, resource_id,
                    school_id, class_id, event_result, failure_reason, request_id, client_ip_hash,
                    user_agent, request_method, request_path, snapshot_json, created_at, updated_at
                )
                VALUES (
                    NULL, 'admin', 'legacy.audit', 'legacy', 'legacy', NULL,
                    NULL, NULL, 'success', NULL, 'legacy-request', NULL,
                    'pytest', 'POST', '/api/legacy', '{}', :created_at, :updated_at
                )
                """
            ),
            {"created_at": now, "updated_at": now},
        )
        return int(result.lastrowid)


def _insert_knowledge_snapshot_run(database_url: str) -> int:
    now = datetime.now(UTC)
    engine = make_engine(database_url)
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                INSERT INTO knowledge_snapshot_runs (
                    run_key, granularity, period_start, period_end, trigger_source, status,
                    started_at, finished_at, user_snapshot_count, class_snapshot_count,
                    error_message, metadata_json, created_at, updated_at, attempt_count
                )
                VALUES (
                    'knowledge:day:legacy', 'day', :period_start, :period_end, 'scheduler', 'success',
                    :started_at, :finished_at, 0, 0, NULL, '{}', :created_at, :updated_at, 1
                )
                """
            ),
            {
                "period_start": now,
                "period_end": now,
                "started_at": now,
                "finished_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        return int(result.lastrowid)


def _dispose_and_remove(database_url: str, database_path: Path) -> None:
    make_engine(database_url).dispose()
    get_settings.cache_clear()
    reset_database_state()
    if database_path.exists():
        database_path.unlink()


def test_audit_archive_anchor_migration_round_trip_seeds_chain_head(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    runtime_dir = backend_root / "pytest-cache-files-preflight"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"audit-anchor-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
        get_settings.cache_clear()
        reset_database_state()
        config = Config(str(backend_root / "alembic.ini"))
        config.set_main_option("script_location", str(backend_root / "alembic"))
        command.upgrade(config, "20260710_0040")
        audit_id = _insert_audit_log(database_url)
        with make_engine(database_url).begin() as connection:
            connection.execute(
                text("UPDATE audit_logs SET current_hash = :current_hash WHERE id = :audit_id"),
                {"current_hash": "c" * 64, "audit_id": audit_id},
            )

        command.upgrade(config, "head")
        with make_engine(database_url).connect() as connection:
            head = connection.execute(
                text("SELECT id, current_audit_log_id, current_hash FROM audit_chain_heads")
            ).mappings().one()
            anchor_count = connection.execute(text("SELECT COUNT(*) FROM audit_archive_anchors")).scalar_one()
        assert head["id"] == 1
        assert head["current_audit_log_id"] == audit_id
        assert head["current_hash"] == "c" * 64
        assert anchor_count == 0

        command.downgrade(config, "20260710_0040")
        with make_engine(database_url).connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                ).all()
            }
        assert "audit_chain_heads" not in tables
        assert "audit_archive_anchors" not in tables

        command.upgrade(config, "head")
        with make_engine(database_url).connect() as connection:
            restored = connection.execute(
                text("SELECT current_audit_log_id, current_hash FROM audit_chain_heads")
            ).mappings().one()
        assert restored["current_audit_log_id"] == audit_id
        assert restored["current_hash"] == "c" * 64
    finally:
        make_engine(database_url).dispose()
        get_settings.cache_clear()
        reset_database_state()
        if database_path.exists():
            database_path.unlink()


def test_bug_external_sync_migration_round_trip_preserves_local_bug(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path, database_url = _empty_sqlite_database(monkeypatch, backend_root)
    config = _alembic_config(backend_root)
    now = datetime.now(UTC)
    try:
        command.upgrade(config, "20260710_0041")
        with make_engine(database_url).begin() as connection:
            result = connection.execute(
                text(
                    """
                    INSERT INTO bug_records (
                        title, category, severity, status, source,
                        external_issue_provider, external_issue_id, external_issue_url,
                        evidence, notes, created_at, updated_at
                    ) VALUES (
                        'legacy sync bug', 'BE', 'P1', 'open', NULL,
                        NULL, NULL, NULL, NULL, NULL, :created_at, :updated_at
                    )
                    """
                ),
                {"created_at": now, "updated_at": now},
            )
            bug_id = int(result.lastrowid)

        command.upgrade(config, "head")
        with make_engine(database_url).connect() as connection:
            bug = connection.execute(
                text(
                    "SELECT external_issue_state, external_issue_synced_at, external_sync_revision "
                    "FROM bug_records WHERE id = :bug_id"
                ),
                {"bug_id": bug_id},
            ).mappings().one()
            operation_count = connection.execute(
                text("SELECT COUNT(*) FROM bug_external_sync_operations")
            ).scalar_one()
        assert bug["external_issue_state"] is None
        assert bug["external_issue_synced_at"] is None
        assert bug["external_sync_revision"] == 1
        assert operation_count == 0

        command.downgrade(config, "20260710_0041")
        with make_engine(database_url).connect() as connection:
            columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(bug_records)")).all()
            }
            tables = {
                row[0]
                for row in connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                ).all()
            }
        assert "external_sync_revision" not in columns
        assert "bug_external_sync_operations" not in tables

        command.upgrade(config, "head")
        with make_engine(database_url).connect() as connection:
            restored_revision = connection.execute(
                text("SELECT external_sync_revision FROM bug_records WHERE id = :bug_id"),
                {"bug_id": bug_id},
            ).scalar_one()
        assert restored_revision == 1
    finally:
        _dispose_and_remove(database_url, database_path)
