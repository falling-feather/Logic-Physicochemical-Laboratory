from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.audit_archive_drill import run_audit_archive_drill


def run_audit_archive_drill_report(
    *,
    database_url: str | None = None,
    require_mysql: bool = False,
    archive_format: str = "jsonl",
    output_dir: str | Path = "audit-archives",
    before_at: datetime | None = None,
    retention_days: int | None = None,
    warning_days: int = 30,
    limit: int = 5000,
    chain_limit: int = 5000,
    issue_limit: int = 50,
    bucket_limit: int = 20,
    action: str | None = None,
    resource_type: str | None = None,
    event_result: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    generated_at: datetime | None = None,
) -> dict:
    settings = get_settings()
    target_database_url = database_url or settings.database_url
    try:
        session_factory = get_session_factory(target_database_url)
        with session_factory() as db:
            return run_audit_archive_drill(
                db,
                database_url=target_database_url,
                settings=settings,
                require_mysql=require_mysql,
                archive_format=archive_format,  # type: ignore[arg-type]
                output_dir=output_dir,
                before_at=before_at,
                retention_days=retention_days,
                warning_days=warning_days,
                limit=limit,
                chain_limit=chain_limit,
                issue_limit=issue_limit,
                bucket_limit=bucket_limit,
                action=action,
                resource_type=resource_type,
                event_result=event_result,
                from_at=from_at,
                to_at=to_at,
                generated_at=generated_at,
            )
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "database_error",
            "error": exc.__class__.__name__,
            "database": {
                "safe_database_url": settings.safe_database_url
                if database_url is None
                else _safe_database_url(target_database_url)
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only audit archive/retention drill report.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--require-mysql", action="store_true", help="Fail when the target database is not MySQL.")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="Archive format to preview.")
    parser.add_argument("--output-dir", type=Path, default=Path("audit-archives"), help="Planned archive output directory.")
    parser.add_argument("--before", default=None, help="Use an explicit archive cutoff ISO datetime/date.")
    parser.add_argument("--retention-days", type=int, default=None, help="Override ASTRA_AUDIT_LOG_RETENTION_DAYS.")
    parser.add_argument("--warning-days", type=int, default=30, help="Expiring-soon window after the cutoff.")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum archive candidates to preview.")
    parser.add_argument("--chain-limit", type=int, default=5000, help="Maximum archive candidates to chain-check.")
    parser.add_argument("--issue-limit", type=int, default=50, help="Maximum issues to include per section.")
    parser.add_argument("--bucket-limit", type=int, default=20, help="Maximum retention buckets per dimension.")
    parser.add_argument("--action", default=None)
    parser.add_argument("--resource-type", default=None)
    parser.add_argument("--event-result", default=None)
    parser.add_argument("--from", dest="from_at", default=None, help="Only consider logs at or after this ISO datetime.")
    parser.add_argument("--to", dest="to_at", default=None, help="Only consider logs at or before this ISO datetime.")
    parser.add_argument("--now", default=None, help="Override generated_at for deterministic drills.")
    args = parser.parse_args(argv)

    try:
        generated_at = _parse_datetime(args.now) if args.now else None
        before_at = _parse_datetime(args.before) if args.before else None
        from_at = _parse_datetime(args.from_at) if args.from_at else None
        to_at = _parse_datetime(args.to_at) if args.to_at else None
    except ValueError as exc:
        report = {
            "ok": False,
            "status": "invalid_argument",
            "error": exc.__class__.__name__,
            "detail": str(exc),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    report = run_audit_archive_drill_report(
        database_url=args.database_url,
        require_mysql=args.require_mysql,
        archive_format=args.format,
        output_dir=args.output_dir,
        before_at=before_at,
        retention_days=args.retention_days,
        warning_days=args.warning_days,
        limit=args.limit,
        chain_limit=args.chain_limit,
        issue_limit=args.issue_limit,
        bucket_limit=args.bucket_limit,
        action=args.action,
        resource_type=args.resource_type,
        event_result=args.event_result,
        from_at=from_at,
        to_at=to_at,
        generated_at=generated_at,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_database_url(database_url: str) -> str:
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError

    try:
        return str(make_url(database_url).render_as_string(hide_password=True))
    except ArgumentError:
        return "<invalid>"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
