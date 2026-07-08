from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from uuid import uuid4

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.base import utc_now
from app.services.knowledge_snapshot_runs import rebuild_periodic_knowledge_snapshots, snapshot_run_report
from app.services.knowledge_snapshot_scheduler import (
    SnapshotScheduleJob,
    acquire_snapshot_job_lease,
    heartbeat_snapshot_job_lease,
)


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


def run_rebuild(
    *,
    granularity: str,
    reference_date: date | None = None,
    database_url: str | None = None,
) -> dict:
    settings = get_settings()
    url = database_url or settings.database_url
    session_factory = get_session_factory(url)
    with session_factory() as db:
        job = SnapshotScheduleJob(
            granularity=granularity,
            reference_date=reference_date or utc_now().date(),
        )
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=settings.knowledge_snapshot_retry_attempts,
            lease_owner=f"script:{uuid4().hex[:24]}",
            lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
            trigger_source="script",
        )
        if lease is None:
            return {
                "ok": True,
                "status": "skipped",
                "reason": "lease_unavailable",
                "granularity": granularity,
                "reference_date": job.reference_date.isoformat(),
            }

        def lease_heartbeat() -> bool:
            with session_factory() as heartbeat_db:
                return heartbeat_snapshot_job_lease(
                    heartbeat_db,
                    lease,
                    lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
                )

        run = rebuild_periodic_knowledge_snapshots(
            db,
            granularity=granularity,
            reference_date=job.reference_date,
            trigger_source="script",
            scheduler_lease_owner=lease.lease_owner,
            scheduler_lease_token=lease.lease_token,
            scheduler_lease_heartbeat=lease_heartbeat,
            scheduler_heartbeat_seconds=settings.knowledge_snapshot_scheduler_heartbeat_seconds,
        )
        return snapshot_run_report(run)


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(description="Rebuild day/week knowledge snapshots.")
    parser.add_argument("--granularity", choices=["day", "week"], required=True)
    parser.add_argument("--date", default=None, help="Reference date in YYYY-MM-DD format. Defaults to today UTC.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    args = parser.parse_args(argv)
    try:
        reference_date = date.fromisoformat(args.date) if args.date else None
    except ValueError as exc:
        report = _invalid_argument_report("ValueError", f"invalid --date: {exc}")
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    try:
        report = run_rebuild(
            granularity=args.granularity,
            reference_date=reference_date,
            database_url=args.database_url,
        )
    except Exception as exc:
        report = {
            "ok": False,
            "status": "failed",
            "error": exc.__class__.__name__,
            "sensitive_fields_returned": False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _invalid_argument_report(error: str, message: str) -> dict:
    return {
        "ok": False,
        "status": "invalid_argument",
        "error": error,
        "message": message,
        "sensitive_fields_returned": False,
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
