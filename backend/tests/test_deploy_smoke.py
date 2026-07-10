import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Column, Integer, MetaData, String, Table, text
from sqlalchemy.dialects import mysql

from app.core.config import get_settings
from app.db.session import make_engine, reset_database_state
import scripts.deploy_smoke as deploy_smoke
from scripts.deploy_smoke import run_smoke


def test_deploy_smoke_cli_escapes_non_ascii_for_legacy_windows_consoles(monkeypatch, capsys):
    monkeypatch.setattr(
        deploy_smoke,
        "run_smoke",
        lambda **_kwargs: {"ok": True, "system_time_zone": "\u05fc"},
    )

    assert deploy_smoke.main([]) == 0
    output = capsys.readouterr().out
    assert "\\u05fc" in output
    assert "\u05fc" not in output


def test_deploy_smoke_reports_ready_database_and_api(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        report = run_smoke(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is True
        assert report["preflight"]["ok"] is True
        assert report["preflight"]["configuration"]["status"] == "ready"
        assert report["preflight"]["configuration"]["auto_create_tables"] is False
        assert report["preflight"]["compatibility"]["status"] == "skipped_non_mysql"
        assert report["schema"]["status"] == "ready"
        assert report["schema"]["dialect"] == "sqlite"
        assert report["schema"]["missing_tables"] == []
        assert "users" in report["schema"]["actual_tables"]
        assert "content_pages" in report["schema"]["actual_tables"]
        assert "content_drafts" in report["schema"]["actual_tables"]
        assert "content_page_versions" in report["schema"]["actual_tables"]
        assert "content_script_asset_scan_runs" in report["schema"]["actual_tables"]
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
        assert report["preflight"]["ok"] is False
        assert report["preflight"]["configuration"]["status"] == "ready"
        assert report["preflight"]["configuration"]["auto_create_tables"] is False
        assert report["preflight"]["compatibility"]["status"] == "unexpected_dialect"
        assert report["preflight"]["compatibility"]["dialect"] == "sqlite"
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
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_RUN_ON_START", "true")
    try:
        report = run_smoke(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is True
        assert report["preflight"]["configuration"]["status"] == "ready"
        assert report["preflight"]["configuration"]["auto_create_tables"] is False
        assert _table_count(database_url, "content_pages") == 0
        assert os.environ["ASTRA_AUTO_CREATE_TABLES"] == "true"
        assert os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED"] == "true"
        assert os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START"] == "true"
        assert os.environ["ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED"] == "true"
        assert os.environ["ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_RUN_ON_START"] == "true"
    finally:
        _dispose_and_remove(database_url, database_path)


def test_deploy_smoke_schema_report_detects_missing_columns(monkeypatch):
    metadata = MetaData()
    Table("users", metadata, Column("id", Integer), Column("username", String))
    fake_base = type("FakeBase", (), {"metadata": metadata})
    monkeypatch.setattr(deploy_smoke, "Base", fake_base)
    monkeypatch.setattr(deploy_smoke, "make_engine", lambda database_url: _FakeSchemaEngine())
    monkeypatch.setattr(deploy_smoke, "inspect", lambda engine: _FakeSchemaInspector())

    report = deploy_smoke._schema_report("sqlite+pysqlite:///:memory:", require_mysql=False)

    assert report["ok"] is False
    assert report["status"] == "missing_columns"
    assert report["missing_tables"] == []
    assert report["checked_column_tables"] == 1
    assert report["missing_columns"] == {"users": ["username"]}


def test_deploy_smoke_rejects_mysql_knowledge_window_without_microseconds(monkeypatch):
    metadata = MetaData()
    Table(
        "knowledge_snapshot_runs",
        metadata,
        Column("period_start", mysql.DATETIME(fsp=6)),
        Column("period_end", mysql.DATETIME(fsp=6)),
    )
    fake_base = type("FakeBase", (), {"metadata": metadata})
    monkeypatch.setattr(deploy_smoke, "Base", fake_base)
    monkeypatch.setattr(deploy_smoke, "make_engine", lambda database_url: _FakeMysqlSchemaEngine())
    monkeypatch.setattr(deploy_smoke, "inspect", lambda engine: _FakeMysqlPrecisionInspector())

    report = deploy_smoke._schema_report("mysql+pymysql://example.invalid/astra", require_mysql=True)

    assert report["ok"] is False
    assert report["status"] == "datetime_precision_mismatch"
    assert report["datetime_precision_mismatches"] == {
        "knowledge_snapshot_runs": {"period_start": 0, "period_end": 0}
    }


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


class _FakeSchemaDialect:
    name = "sqlite"
    driver = "pysqlite"


class _FakeSchemaEngine:
    dialect = _FakeSchemaDialect()

    def dispose(self) -> None:
        pass


class _FakeSchemaInspector:
    def get_table_names(self) -> list[str]:
        return ["alembic_version", "users"]

    def get_columns(self, table_name: str) -> list[dict[str, str]]:
        if table_name == "users":
            return [{"name": "id"}]
        return [{"name": "version_num"}]


class _FakeMysqlSchemaDialect:
    name = "mysql"
    driver = "pymysql"


class _FakeMysqlSchemaEngine:
    dialect = _FakeMysqlSchemaDialect()

    def dispose(self) -> None:
        pass


class _FakeMysqlPrecisionInspector:
    def get_table_names(self) -> list[str]:
        return ["alembic_version", "knowledge_snapshot_runs"]

    def get_columns(self, table_name: str) -> list[dict[str, object]]:
        if table_name == "knowledge_snapshot_runs":
            return [
                {"name": "period_start", "type": mysql.DATETIME(fsp=0)},
                {"name": "period_end", "type": mysql.DATETIME(fsp=0)},
            ]
        return [{"name": "version_num", "type": String()}]
