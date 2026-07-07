from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from app.services.password_reset_tokens import cleanup_password_reset_tokens


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or delete expired/used password-reset tokens beyond the retention window."
    )
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--before", default=None, help="Delete tokens whose terminal time is at or before this ISO date/time.")
    parser.add_argument("--retention-days", type=int, default=None, help="Override ASTRA_PASSWORD_RESET_TOKEN_RETENTION_DAYS.")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum records to delete in one batch.")
    parser.add_argument("--apply", action="store_true", help="Actually delete selected rows. Default is dry-run.")
    args = parser.parse_args(argv)

    try:
        report = cleanup_password_reset_tokens(
            database_url=args.database_url,
            before_at=_parse_datetime(args.before) if args.before else None,
            retention_days=args.retention_days,
            limit=args.limit,
            apply=args.apply,
        )
    except ValueError as exc:
        report = {"ok": False, "status": "failed", "error": exc.__class__.__name__, "detail": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
