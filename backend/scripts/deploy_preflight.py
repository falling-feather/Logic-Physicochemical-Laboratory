from __future__ import annotations

import argparse
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


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_preflight(
    database_url: str | None = None,
    backend_root: Path | None = None,
    *,
    require_mysql: bool = False,
) -> dict[str, Any]:
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
        "configuration": configuration,
        "database": database,
        "migrations": migrations,
        "compatibility": compatibility,
    }


def _configuration_report(settings: Any, *, require_mysql: bool) -> dict[str, Any]:
    auto_create_tables = bool(settings.auto_create_tables)
    if require_mysql and auto_create_tables:
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
                        CURRENT_USER() AS current_user
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
        "current_user": _variable_text(variables, "current_user"),
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
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
