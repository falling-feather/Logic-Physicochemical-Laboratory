import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import make_engine, reset_database_state
from scripts.deploy_smoke import run_smoke


def test_deploy_smoke_reports_ready_database_and_api(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        report = run_smoke(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is True
        assert report["preflight"]["ok"] is True
        assert report["schema"]["status"] == "ready"
        assert report["schema"]["dialect"] == "sqlite"
        assert report["schema"]["missing_tables"] == []
        assert "users" in report["schema"]["actual_tables"]
        assert "content_pages" in report["schema"]["actual_tables"]
        assert report["api"]["status"] == "healthy"
        assert report["api"]["health"]["database"]["ok"] is True
    finally:
        _dispose_and_remove(database_url, database_path)


def test_deploy_smoke_can_require_mysql(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        report = run_smoke(database_url=database_url, backend_root=backend_root, require_mysql=True)

        assert report["ok"] is False
        assert report["preflight"]["ok"] is True
        assert report["schema"]["status"] == "unexpected_dialect"
        assert report["schema"]["dialect"] == "sqlite"
        assert report["schema"]["require_mysql"] is True
        assert report["api"]["status"] == "healthy"
    finally:
        _dispose_and_remove(database_url, database_path)


def test_deploy_smoke_disables_mutating_runtime_defaults(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START", "true")
    try:
        report = run_smoke(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is True
        assert _table_count(database_url, "content_pages") == 0
        assert os.environ["ASTRA_AUTO_CREATE_TABLES"] == "true"
        assert os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED"] == "true"
        assert os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START"] == "true"
    finally:
        _dispose_and_remove(database_url, database_path)


def _migrated_sqlite_database(monkeypatch, backend_root: Path) -> Path:
    runtime_dir = backend_root / "pytest-cache-files-smoke"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"smoke-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "false")
    get_settings.cache_clear()
    reset_database_state()

    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")
    return database_path


def _table_count(database_url: str, table_name: str) -> int:
    engine = make_engine(database_url)
    try:
        with engine.connect() as connection:
            return int(connection.execute(text(f"select count(*) from {table_name}")).scalar_one())
    finally:
        engine.dispose()


def _dispose_and_remove(database_url: str, database_path: Path) -> None:
    make_engine(database_url).dispose()
    get_settings.cache_clear()
    reset_database_state()
    if database_path.exists():
        database_path.unlink()
