from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.knowledge_snapshot_scheduler_drill import run_knowledge_snapshot_scheduler_drill


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(
            json.dumps(
                _invalid_argument_report("ArgumentError", message),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        raise SystemExit(2)


def run_knowledge_snapshot_scheduler_drill_report(
    *,
    database_url: str | None = None,
    require_mysql: bool = False,
    expect_scheduler_enabled: bool = False,
    now: datetime | None = None,
    lease_expiring_seconds: int = 600,
    max_issues: int = 100,
    max_runs: int = 500,
) -> dict[str, Any]:
    settings = get_settings()
    url = database_url or settings.database_url
    session_factory = get_session_factory(url)
    try:
        with session_factory() as db:
            return run_knowledge_snapshot_scheduler_drill(
                db,
                database_url=url,
                settings=settings,
                require_mysql=require_mysql,
                expect_scheduler_enabled=expect_scheduler_enabled,
                now=now,
                lease_expiring_seconds=lease_expiring_seconds,
                max_issues=max_issues,
                max_runs=max_runs,
            )
    except (ImportError, ModuleNotFoundError, SQLAlchemyError) as exc:
        return {
            "ok": False,
            "status": "database_error",
            "mode": "read_only",
            "database": {
                "ok": False,
                "status": "database_error",
                "safe_database_url": _safe_database_url(url),
                "error": exc.__class__.__name__,
                "require_mysql": require_mysql,
            },
            "sensitive_fields_returned": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(description="Read-only knowledge snapshot scheduler drill report.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--require-mysql", action="store_true", help="Fail the report unless the target DB dialect is MySQL.")
    parser.add_argument(
        "--expect-scheduler-enabled",
        action="store_true",
        help="Fail unless ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED=true.",
    )
    parser.add_argument("--now", default=None, help="Override report clock as ISO datetime.")
    parser.add_argument(
        "--lease-expiring-seconds",
        type=int,
        default=600,
        help="Window for lease_expiring_soon warnings.",
    )
    parser.add_argument("--max-issues", type=int, default=100, help="Maximum issue rows to include per report section.")
    parser.add_argument("--max-runs", type=int, default=500, help="Maximum recent run ledger rows to scan.")
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.now) if args.now else None
    except ValueError as exc:
        report = _invalid_argument_report("ValueError", f"invalid --now: {exc}")
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    report = run_knowledge_snapshot_scheduler_drill_report(
        database_url=args.database_url,
        require_mysql=args.require_mysql,
        expect_scheduler_enabled=args.expect_scheduler_enabled,
        now=now,
        lease_expiring_seconds=max(0, args.lease_expiring_seconds),
        max_issues=max(1, args.max_issues),
        max_runs=max(1, args.max_runs),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def _invalid_argument_report(error: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "invalid_argument",
        "error": error,
        "message": message,
        "sensitive_fields_returned": False,
    }


def _safe_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
