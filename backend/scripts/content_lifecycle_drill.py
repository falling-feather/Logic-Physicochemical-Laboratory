from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.content_lifecycle_drill import run_content_lifecycle_drill


def run_content_lifecycle_drill_report(
    *,
    database_url: str | None = None,
    require_mysql: bool = False,
    render_url: str | None = None,
    static_url: str | None = None,
    request_id: str = "astra-content-lifecycle-drill",
    timeout_seconds: float = 5.0,
    max_issues: int = 100,
) -> dict[str, Any]:
    settings = get_settings()
    url = database_url or settings.database_url
    session_factory = get_session_factory(url)
    try:
        with session_factory() as db:
            return run_content_lifecycle_drill(
                db,
                database_url=url,
                api_cache_control=settings.api_cache_control,
                require_mysql=require_mysql,
                render_url=render_url,
                static_url=static_url,
                request_id=request_id,
                timeout_seconds=timeout_seconds,
                max_issues=max_issues,
            )
    except SQLAlchemyError as exc:
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
    parser = argparse.ArgumentParser(description="Read-only content publish/init/rollback lifecycle drill report.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--require-mysql", action="store_true", help="Fail the report unless the target DB dialect is MySQL.")
    parser.add_argument(
        "--render-url",
        default=None,
        help="Optional live /api/render/page/{slug} URL to verify JSON and Cache-Control: no-store.",
    )
    parser.add_argument(
        "--static-url",
        default=None,
        help="Optional legacy/static page URL to verify non-API static fallback remains available.",
    )
    parser.add_argument("--request-id", default="astra-content-lifecycle-drill", help="X-Request-ID for live probes.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="HTTP timeout for optional live probes.")
    parser.add_argument("--max-issues", type=int, default=100, help="Maximum issue rows to include per report section.")
    args = parser.parse_args(argv)
    report = run_content_lifecycle_drill_report(
        database_url=args.database_url,
        require_mysql=args.require_mysql,
        render_url=args.render_url,
        static_url=args.static_url,
        request_id=args.request_id,
        timeout_seconds=args.timeout_seconds,
        max_issues=max(1, args.max_issues),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def _safe_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
