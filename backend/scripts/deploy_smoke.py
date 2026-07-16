from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Integer, Text, inspect, text
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

_MYSQL_MICROSECOND_COLUMNS = {
    "class_knowledge_snapshots": ("period_start", "period_end"),
    "user_knowledge_snapshots": ("period_start", "period_end"),
    "knowledge_snapshot_runs": ("period_start", "period_end"),
}

_ORGANIZATION_GOVERNANCE_TABLES = ("schools", "class_groups")
_ORGANIZATION_GOVERNANCE_REVISION = "20260716_0047"


def run_smoke(
    database_url: str | None = None,
    backend_root: Path | None = None,
    *,
    require_mysql: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(UTC)
    root = backend_root or BACKEND_ROOT
    url = _effective_database_url(database_url)
    previous_env = _capture_env()
    try:
        _configure_runtime(url)
        preflight = run_preflight(
            database_url=url,
            backend_root=root,
            require_mysql=require_mysql,
            generated_at=generated,
        )
        schema = _schema_report(url, require_mysql=require_mysql)
        api = _api_report()
        return {
            "ok": bool(preflight["ok"] and schema["ok"] and api["ok"]),
            "generated_at": generated.isoformat(),
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
    expected_columns = {
        table.name: sorted(column.name for column in table.columns)
        for table in Base.metadata.sorted_tables
    }
    engine = None
    try:
        engine = make_engine(database_url)
        inspector = inspect(engine)
        dialect = engine.dialect.name
        driver = engine.dialect.driver
        actual_tables = sorted(inspector.get_table_names())
        missing_tables = sorted(set(expected_tables).difference(actual_tables))
        extra_tables = sorted(set(actual_tables).difference(expected_tables))
        missing_columns: dict[str, list[str]] = {}
        datetime_precision_mismatches: dict[str, dict[str, int | None]] = {}
        organization_governance_mismatches: dict[str, dict[str, Any]] = {}
        organization_version_invalid_rows: dict[str, int] = {}
        checked_column_tables = 0
        for table_name, table_columns in expected_columns.items():
            if table_name in missing_tables:
                continue
            checked_column_tables += 1
            column_details = inspector.get_columns(table_name)
            actual_columns = {column["name"] for column in column_details}
            missing = sorted(set(table_columns).difference(actual_columns))
            if missing:
                missing_columns[table_name] = missing
            if table_name in _ORGANIZATION_GOVERNANCE_TABLES and not ({"description", "version"} - actual_columns):
                columns_by_name = {str(column["name"]): column for column in column_details}
                governance_mismatches = _organization_governance_column_mismatches(columns_by_name)
                if governance_mismatches:
                    organization_governance_mismatches[table_name] = governance_mismatches
                else:
                    with engine.connect() as connection:
                        invalid_count = connection.execute(
                            text(f"SELECT COUNT(*) FROM {table_name} WHERE version IS NULL OR version < 1")
                        ).scalar_one()
                    organization_version_invalid_rows[table_name] = int(invalid_count)
            if dialect == "mysql" and table_name in _MYSQL_MICROSECOND_COLUMNS:
                types_by_name = {str(column["name"]): column.get("type") for column in column_details}
                mismatches = {
                    column_name: getattr(types_by_name.get(column_name), "fsp", None)
                    for column_name in _MYSQL_MICROSECOND_COLUMNS[table_name]
                    if getattr(types_by_name.get(column_name), "fsp", None) != 6
                }
                if mismatches:
                    datetime_precision_mismatches[table_name] = mismatches
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "expected_tables": expected_tables,
            "actual_tables": [],
            "missing_tables": expected_tables,
            "extra_tables": [],
            "checked_column_tables": 0,
            "missing_columns": {},
            "datetime_precision_mismatches": {},
            "organization_governance_mismatches": {},
            "organization_version_invalid_rows": {},
            "expected_organization_governance_revision": _ORGANIZATION_GOVERNANCE_REVISION,
            "error": exc.__class__.__name__,
        }
    finally:
        if engine is not None:
            engine.dispose()

    dialect_ok = not require_mysql or dialect == "mysql"
    tables_ok = not missing_tables
    columns_ok = not missing_columns
    datetime_precision_ok = not datetime_precision_mismatches
    organization_governance_ok = not organization_governance_mismatches
    organization_version_rows_ok = not any(organization_version_invalid_rows.values())
    status = "ready"
    if not dialect_ok:
        status = "unexpected_dialect"
    elif not tables_ok:
        status = "missing_tables"
    elif not columns_ok:
        status = "missing_columns"
    elif not datetime_precision_ok:
        status = "datetime_precision_mismatch"
    elif not organization_governance_ok:
        status = "organization_governance_schema_mismatch"
    elif not organization_version_rows_ok:
        status = "organization_version_history_invalid"
    return {
        "ok": bool(
            dialect_ok
            and tables_ok
            and columns_ok
            and datetime_precision_ok
            and organization_governance_ok
            and organization_version_rows_ok
        ),
        "status": status,
        "dialect": dialect,
        "driver": driver,
        "require_mysql": require_mysql,
        "expected_tables": expected_tables,
        "actual_tables": actual_tables,
        "missing_tables": missing_tables,
        "extra_tables": extra_tables,
        "checked_column_tables": checked_column_tables,
        "missing_columns": missing_columns,
        "datetime_precision_mismatches": datetime_precision_mismatches,
        "mysql_expected_datetime_precision": 6,
        "organization_governance_mismatches": organization_governance_mismatches,
        "organization_version_invalid_rows": organization_version_invalid_rows,
        "expected_organization_governance_revision": _ORGANIZATION_GOVERNANCE_REVISION,
    }


def _organization_governance_column_mismatches(columns: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mismatches: dict[str, Any] = {}
    description = columns["description"]
    version = columns["version"]
    if not isinstance(description.get("type"), Text):
        mismatches["description_type"] = description.get("type").__class__.__name__
    if description.get("nullable") is not True:
        mismatches["description_nullable"] = description.get("nullable")
    if not isinstance(version.get("type"), Integer):
        mismatches["version_type"] = version.get("type").__class__.__name__
    if version.get("nullable") is not False:
        mismatches["version_nullable"] = version.get("nullable")
    if not _server_default_is_one(version.get("default")):
        mismatches["version_default"] = _safe_default_summary(version.get("default"))
    return mismatches


def _server_default_is_one(value: Any) -> bool:
    normalized = str(value or "").strip()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    normalized = normalized.strip("'\"")
    return normalized == "1"


def _safe_default_summary(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:64]


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
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
