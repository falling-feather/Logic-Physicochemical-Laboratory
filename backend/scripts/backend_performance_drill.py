from __future__ import annotations

import argparse
import json
import sys

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.backend_performance import build_backend_performance_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect backend query/index/performance posture")
    parser.add_argument("--database-url")
    parser.add_argument("--require-mysql", action="store_true")
    parser.add_argument("--skip-explain", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    database_url = args.database_url or settings.database_url
    try:
        session_factory = get_session_factory(database_url)
        with session_factory() as db:
            report = build_backend_performance_report(
                db,
                settings=settings,
                include_explain=not args.skip_explain,
                include_benchmark=not args.skip_benchmark,
                require_mysql=args.require_mysql,
            )
    except Exception as exc:
        report = {
            "ok": False,
            "status": "performance_drill_failed",
            "error": exc.__class__.__name__,
            "database_url_returned": False,
        }
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
