from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.content_script_remote_drift_drill import run_content_script_remote_drift_drill


def run_content_script_remote_drift_drill_report(
    *,
    database_url: str | None = None,
    require_mysql: bool = False,
    expect_scheduler_enabled: bool = False,
    source_host: str | None = None,
    slug: str | None = None,
    now: datetime | None = None,
    recent_run_limit: int = 50,
    candidate_limit: int = 50,
    lease_expiring_seconds: int = 900,
    max_issues: int = 100,
    max_policy_hosts: int = 200,
) -> dict:
    settings = get_settings()
    url = database_url or settings.database_url
    session_factory = get_session_factory(url)
    try:
        with session_factory() as db:
            return run_content_script_remote_drift_drill(
                db,
                database_url=url,
                settings=settings,
                require_mysql=require_mysql,
                expect_scheduler_enabled=expect_scheduler_enabled,
                source_host=source_host,
                slug=slug,
                generated_at=now,
                recent_run_limit=recent_run_limit,
                candidate_limit=candidate_limit,
                lease_expiring_seconds=lease_expiring_seconds,
                max_issues=max_issues,
                max_policy_hosts=max_policy_hosts,
            )
    except (ImportError, ModuleNotFoundError, SQLAlchemyError) as exc:
        return {
            "ok": False,
            "status": "database_error",
            "mode": "read_only",
            "database": {
                "ok": False,
                "status": "unavailable",
                "safe_database_url": settings.safe_database_url if database_url is None else _safe_database_url(database_url),
                "error": exc.__class__.__name__,
            },
            "sensitive_fields_returned": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a read-only content script remote drift observation drill.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--require-mysql", action="store_true")
    parser.add_argument("--expect-scheduler-enabled", action="store_true")
    parser.add_argument("--source-host", default=None)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--now", default=None, help="ISO timestamp used as report generated_at.")
    parser.add_argument("--recent-run-limit", type=int, default=50)
    parser.add_argument("--candidate-limit", type=int, default=50)
    parser.add_argument("--lease-expiring-seconds", type=int, default=900)
    parser.add_argument("--max-issues", type=int, default=100)
    parser.add_argument("--max-policy-hosts", type=int, default=200)
    args = parser.parse_args(argv)

    try:
        now = _parse_optional_datetime(args.now)
    except ValueError:
        report = {
            "ok": False,
            "status": "invalid_argument",
            "mode": "read_only",
            "error": "InvalidNowTimestamp",
            "sensitive_fields_returned": False,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    report = run_content_script_remote_drift_drill_report(
        database_url=args.database_url,
        require_mysql=args.require_mysql,
        expect_scheduler_enabled=args.expect_scheduler_enabled,
        source_host=args.source_host,
        slug=args.slug,
        now=now,
        recent_run_limit=args.recent_run_limit,
        candidate_limit=args.candidate_limit,
        lease_expiring_seconds=args.lease_expiring_seconds,
        max_issues=args.max_issues,
        max_policy_hosts=args.max_policy_hosts,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _safe_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
