from __future__ import annotations

import argparse
from datetime import date
import json
import sys

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.knowledge_snapshot_runs import rebuild_periodic_knowledge_snapshots, snapshot_run_report


def run_rebuild(
    *,
    granularity: str,
    reference_date: date | None = None,
    database_url: str | None = None,
) -> dict:
    url = database_url or get_settings().database_url
    session_factory = get_session_factory(url)
    with session_factory() as db:
        run = rebuild_periodic_knowledge_snapshots(
            db,
            granularity=granularity,
            reference_date=reference_date,
            trigger_source="script",
        )
        return snapshot_run_report(run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild day/week knowledge snapshots.")
    parser.add_argument("--granularity", choices=["day", "week"], required=True)
    parser.add_argument("--date", default=None, help="Reference date in YYYY-MM-DD format. Defaults to today UTC.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    args = parser.parse_args(argv)
    reference_date = date.fromisoformat(args.date) if args.date else None
    try:
        report = run_rebuild(
            granularity=args.granularity,
            reference_date=reference_date,
            database_url=args.database_url,
        )
    except Exception as exc:
        report = {"ok": False, "status": "failed", "error": exc.__class__.__name__}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
