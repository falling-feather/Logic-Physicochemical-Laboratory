from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config

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
