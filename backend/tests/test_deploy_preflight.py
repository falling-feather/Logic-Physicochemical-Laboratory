from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine, reset_database_state
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
        assert report["database"]["ok"] is True
        assert report["migrations"]["status"] == "up_to_date"
        assert report["migrations"]["current"] == report["migrations"]["heads"]
    finally:
        make_engine(database_url).dispose()
        get_settings.cache_clear()
        reset_database_state()
        if database_path.exists():
            database_path.unlink()


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


def _dispose_and_remove(database_url: str, database_path: Path) -> None:
    make_engine(database_url).dispose()
    get_settings.cache_clear()
    reset_database_state()
    if database_path.exists():
        database_path.unlink()
