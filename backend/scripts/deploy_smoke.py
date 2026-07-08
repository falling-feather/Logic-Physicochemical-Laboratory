from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import make_engine, reset_database_state
from app.models import Base
from scripts.deploy_preflight import BACKEND_ROOT, run_preflight


_RUNTIME_ENV_KEYS = (
    "ASTRA_DATABASE_URL",
    "ASTRA_AUTO_CREATE_TABLES",
    "ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED",
    "ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START",
    "ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED",
    "ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_RUN_ON_START",
)


def run_smoke(
    database_url: str | None = None,
    backend_root: Path | None = None,
    *,
    require_mysql: bool = False,
) -> dict[str, Any]:
    root = backend_root or BACKEND_ROOT
    url = _effective_database_url(database_url)
    previous_env = _capture_env()
    try:
        _configure_runtime(url)
        preflight = run_preflight(database_url=url, backend_root=root, require_mysql=require_mysql)
        schema = _schema_report(url, require_mysql=require_mysql)
        api = _api_report()
        return {
            "ok": bool(preflight["ok"] and schema["ok"] and api["ok"]),
            "preflight": preflight,
            "schema": schema,
            "api": api,
        }
    finally:
        _restore_env(previous_env)


def _effective_database_url(database_url: str | None) -> str:
    if database_url:
        return database_url
    get_settings.cache_clear()
    return get_settings().database_url


def _capture_env() -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in _RUNTIME_ENV_KEYS}


def _configure_runtime(database_url: str) -> None:
    os.environ["ASTRA_DATABASE_URL"] = database_url
    os.environ["ASTRA_AUTO_CREATE_TABLES"] = "false"
    os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED"] = "false"
    os.environ["ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_RUN_ON_START"] = "false"
    os.environ["ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_ENABLED"] = "false"
    os.environ["ASTRA_CONTENT_SCRIPT_REMOTE_DRIFT_SCHEDULER_RUN_ON_START"] = "false"
    get_settings.cache_clear()
    reset_database_state()


def _restore_env(previous_env: dict[str, str | None]) -> None:
    for key, value in previous_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    reset_database_state()


def _schema_report(database_url: str, *, require_mysql: bool) -> dict[str, Any]:
    expected_tables = sorted({table.name for table in Base.metadata.sorted_tables} | {"alembic_version"})
    engine = None
    try:
        engine = make_engine(database_url)
        inspector = inspect(engine)
        actual_tables = sorted(inspector.get_table_names())
        missing_tables = sorted(set(expected_tables).difference(actual_tables))
        extra_tables = sorted(set(actual_tables).difference(expected_tables))
        dialect = engine.dialect.name
        driver = engine.dialect.driver
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "expected_tables": expected_tables,
            "actual_tables": [],
            "missing_tables": expected_tables,
            "extra_tables": [],
            "error": exc.__class__.__name__,
        }
    finally:
        if engine is not None:
            engine.dispose()

    dialect_ok = not require_mysql or dialect == "mysql"
    tables_ok = not missing_tables
    status = "ready"
    if not dialect_ok:
        status = "unexpected_dialect"
    elif not tables_ok:
        status = "missing_tables"
    return {
        "ok": dialect_ok and tables_ok,
        "status": status,
        "dialect": dialect,
        "driver": driver,
        "require_mysql": require_mysql,
        "expected_tables": expected_tables,
        "actual_tables": actual_tables,
        "missing_tables": missing_tables,
        "extra_tables": extra_tables,
    }


def _api_report() -> dict[str, Any]:
    from app.main import create_app

    try:
        with TestClient(create_app()) as client:
            response = client.get("/api/health")
            payload = response.json()
    except Exception as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "error": exc.__class__.__name__,
        }
    database = payload.get("database", {}) if isinstance(payload, dict) else {}
    ok = response.status_code == 200 and bool(database.get("ok"))
    return {
        "ok": ok,
        "status": "healthy" if ok else "unhealthy",
        "status_code": response.status_code,
        "health": payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run backend deployment smoke checks.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this smoke check.")
    parser.add_argument(
        "--require-mysql",
        action="store_true",
        help="Fail unless the configured SQLAlchemy dialect is mysql.",
    )
    args = parser.parse_args(argv)
    report = run_smoke(database_url=args.database_url, require_mysql=args.require_mysql)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
