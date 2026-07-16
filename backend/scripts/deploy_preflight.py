from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import check_database, make_engine
from app.services.alert_delivery import alert_delivery_posture
from app.services.audit_anchor_delivery import audit_anchor_posture
from app.services.external_issue_providers import external_issue_sync_posture
from app.services.backend_performance import performance_posture


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_preflight(
    database_url: str | None = None,
    backend_root: Path | None = None,
    *,
    require_mysql: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(UTC)
    root = backend_root or BACKEND_ROOT
    settings = get_settings()
    url = database_url or settings.database_url
    configuration = _configuration_report(settings, require_mysql=require_mysql)
    database = check_database(url)
    migrations = _migration_report(url, root) if database["ok"] else _skipped_migration_report()
    compatibility = (
        _database_compatibility_report(url, require_mysql=require_mysql)
        if database["ok"]
        else _skipped_compatibility_report(require_mysql)
    )
    return {
        "ok": bool(configuration["ok"] and database["ok"] and migrations["ok"] and compatibility["ok"]),
        "generated_at": generated.isoformat(),
        "configuration": configuration,
        "database": database,
        "migrations": migrations,
        "compatibility": compatibility,
    }


def _configuration_report(settings: Any, *, require_mysql: bool) -> dict[str, Any]:
    auto_create_tables = bool(settings.auto_create_tables)
    delivery_posture = alert_delivery_posture(settings)
    anchor_posture = audit_anchor_posture(settings)
    issue_sync_posture = external_issue_sync_posture(settings)
    if delivery_posture["enabled"] and not delivery_posture["configured"]:
        status = "alert_delivery_not_configured"
        ok = False
    elif anchor_posture["enabled"] and not anchor_posture["configured"]:
        status = "audit_anchor_not_configured"
        ok = False
    elif issue_sync_posture["enabled"] and not issue_sync_posture["configured"]:
        status = "external_issue_sync_not_configured"
        ok = False
    elif require_mysql and auto_create_tables:
        status = "auto_create_tables_enabled"
        ok = False
    elif auto_create_tables:
        status = "allowed_development_auto_create"
        ok = True
    else:
        status = "ready"
        ok = True
    return {
        "ok": ok,
        "status": status,
        "require_mysql": require_mysql,
        "environment": settings.environment,
        "auto_create_tables": auto_create_tables,
        "expected_auto_create_tables": False,
        "auto_create_tables_policy": "must_be_false_when_require_mysql",
        "alert_delivery": delivery_posture,
        "audit_anchor": anchor_posture,
        "external_issue_sync": issue_sync_posture,
        "performance": performance_posture(settings),
        "background_task_worker": {
            "enabled": settings.background_task_worker_enabled,
            "queue_backend": "database",
            "execution_mode": "hybrid_domain_ledgers",
            "interval_seconds": settings.background_task_worker_interval_seconds,
            "lease_seconds": settings.background_task_worker_lease_seconds,
            "batch_size": settings.background_task_worker_batch_size,
            "base_backoff_seconds": settings.background_task_worker_base_backoff_seconds,
            "max_backoff_seconds": settings.background_task_worker_max_backoff_seconds,
            "content_scan_enabled": settings.background_task_worker_content_scan_enabled,
            "audit_anchor_enabled": settings.background_task_worker_audit_anchor_enabled,
            "payload_returned": False,
            "lease_token_returned": False,
        },
    }


def _database_compatibility_report(database_url: str, *, require_mysql: bool) -> dict[str, Any]:
    engine = None
    try:
        engine = make_engine(database_url)
        dialect = engine.dialect.name
        driver = engine.dialect.driver
        if dialect != "mysql":
            return {
                "ok": not require_mysql,
                "status": "unexpected_dialect" if require_mysql else "skipped_non_mysql",
                "dialect": dialect,
                "driver": driver,
                "require_mysql": require_mysql,
            }
        with engine.connect() as connection:
            variables = connection.execute(
                text(
                    """
                    SELECT
                        @@character_set_database AS character_set_database,
                        @@collation_database AS collation_database,
                        @@character_set_connection AS character_set_connection,
                        @@collation_connection AS collation_connection,
                        @@time_zone AS time_zone,
                        @@system_time_zone AS system_time_zone,
                        @@version AS server_version,
                        @@version_comment AS server_version_comment,
                        @@sql_mode AS sql_mode,
                        @@max_connections AS max_connections,
                        DATABASE() AS database_name,
                        CURRENT_USER() AS current_user_name
                    """
                )
            ).mappings().one()
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "require_mysql": require_mysql,
            "error": exc.__class__.__name__,
        }
    finally:
        if engine is not None:
            engine.dispose()

    charset_database = _variable_text(variables, "character_set_database").lower()
    charset_connection = _variable_text(variables, "character_set_connection").lower()
    collation_database = _variable_text(variables, "collation_database").lower()
    collation_connection = _variable_text(variables, "collation_connection").lower()
    charset_ok = charset_database == "utf8mb4" and charset_connection == "utf8mb4"
    collation_ok = collation_database.startswith("utf8mb4_") and collation_connection.startswith("utf8mb4_")
    ok = charset_ok and collation_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "mysql_charset_mismatch",
        "dialect": "mysql",
        "driver": driver,
        "require_mysql": require_mysql,
        "character_set_database": charset_database,
        "collation_database": collation_database,
        "character_set_connection": charset_connection,
        "collation_connection": collation_connection,
        "time_zone": _variable_text(variables, "time_zone"),
        "system_time_zone": _variable_text(variables, "system_time_zone"),
        "server_version": _variable_text(variables, "server_version"),
        "server_version_comment": _variable_text(variables, "server_version_comment"),
        "sql_mode": _variable_text(variables, "sql_mode"),
        "max_connections": _variable_int(variables, "max_connections"),
        "database_name": _variable_text(variables, "database_name"),
        "current_user": _variable_text(variables, "current_user_name"),
        "expected_character_set": "utf8mb4",
        "expected_collation_prefix": "utf8mb4_",
        "time_zone_policy": "reported_only",
        "max_connections_policy": "reported_only",
        "sql_mode_policy": "reported_only",
    }


def _variable_text(variables: Any, key: str) -> str:
    try:
        value = variables[key]
    except KeyError:
        return ""
    if value is None:
        return ""
    return str(value)


def _variable_int(variables: Any, key: str) -> int | None:
    value = _variable_text(variables, key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _migration_report(database_url: str, backend_root: Path) -> dict[str, Any]:
    config = _alembic_config(backend_root)
    script = ScriptDirectory.from_config(config)
    heads = sorted(script.get_heads())
    engine = None
    try:
        engine = make_engine(database_url)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current = sorted(context.get_current_heads())
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "heads": heads,
            "current": [],
            "error": exc.__class__.__name__,
        }
    finally:
        if engine is not None:
            engine.dispose()
    ok = current == heads
    return {
        "ok": ok,
        "status": "up_to_date" if ok else "pending",
        "heads": heads,
        "current": current,
    }


def _skipped_migration_report() -> dict[str, Any]:
    return {
        "ok": False,
        "status": "skipped_database_unavailable",
        "heads": [],
        "current": [],
    }


def _skipped_compatibility_report(require_mysql: bool) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "skipped_database_unavailable",
        "require_mysql": require_mysql,
    }


def _alembic_config(backend_root: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run backend deployment preflight checks.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this check.")
    parser.add_argument(
        "--require-mysql",
        action="store_true",
        help="Fail unless the configured database is MySQL with utf8mb4 charset/collation.",
    )
    args = parser.parse_args(argv)
    report = run_preflight(database_url=args.database_url, require_mysql=args.require_mysql)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
