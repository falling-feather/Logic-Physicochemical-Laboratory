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
    database = check_database(url)
    migrations = _migration_report(url, root) if database["ok"] else _skipped_migration_report()
    compatibility = (
        _database_compatibility_report(url, require_mysql=require_mysql)
        if database["ok"]
        else _skipped_compatibility_report(require_mysql)
    )
    return {
        "ok": bool(database["ok"] and migrations["ok"] and compatibility["ok"]),
        "database": database,
        "migrations": migrations,
        "compatibility": compatibility,
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
                        @@time_zone AS time_zone
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

    charset_database = str(variables["character_set_database"] or "").lower()
    charset_connection = str(variables["character_set_connection"] or "").lower()
    collation_database = str(variables["collation_database"] or "").lower()
    collation_connection = str(variables["collation_connection"] or "").lower()
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
        "time_zone": variables["time_zone"],
        "expected_character_set": "utf8mb4",
        "expected_collation_prefix": "utf8mb4_",
    }


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
