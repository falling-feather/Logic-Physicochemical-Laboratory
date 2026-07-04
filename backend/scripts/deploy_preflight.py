from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import check_database, make_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_preflight(database_url: str | None = None, backend_root: Path | None = None) -> dict[str, Any]:
    root = backend_root or BACKEND_ROOT
    settings = get_settings()
    url = database_url or settings.database_url
    database = check_database(url)
    migrations = _migration_report(url, root) if database["ok"] else _skipped_migration_report()
    return {
        "ok": bool(database["ok"] and migrations["ok"]),
        "database": database,
        "migrations": migrations,
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


def _alembic_config(backend_root: Path) -> Config:
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run backend deployment preflight checks.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this check.")
    args = parser.parse_args(argv)
    report = run_preflight(database_url=args.database_url)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
