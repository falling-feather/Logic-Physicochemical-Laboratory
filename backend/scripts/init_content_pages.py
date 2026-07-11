from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import User
from app.services.content_catalog import initialize_builtin_content_pages
from scripts.deploy_preflight import BACKEND_ROOT, run_preflight


def run_content_initialization(
    database_url: str | None = None,
    backend_root: Path | None = None,
    *,
    publisher_user_id: int | None = None,
    dry_run: bool = False,
    skip_preflight: bool = False,
    note: str | None = "Built-in content initialization",
    allow_reviewed_scripts: bool = False,
    upgrade_existing: bool = False,
    allow_stale_drafts: bool = False,
) -> dict[str, Any]:
    root = backend_root or BACKEND_ROOT
    settings = get_settings()
    url = database_url or settings.database_url
    preflight = _skipped_preflight_report() if skip_preflight else run_preflight(database_url=url, backend_root=root)
    if not preflight["ok"]:
        return {
            "ok": False,
            "status": "preflight_failed",
            "preflight": preflight,
            "content": _empty_content_report(dry_run=dry_run),
        }

    session_factory = get_session_factory(url)
    with session_factory() as db:
        try:
            publisher = _resolve_publisher(db, publisher_user_id)
            if publisher is None:
                db.rollback()
                return {
                    "ok": False,
                    "status": "publisher_not_found",
                    "preflight": preflight,
                    "content": _empty_content_report(dry_run=dry_run),
                }
            content = initialize_builtin_content_pages(
                db,
                publisher=publisher,
                dry_run=dry_run,
                note=note,
                allow_reviewed_scripts=allow_reviewed_scripts,
                upgrade_existing=upgrade_existing,
                allow_stale_drafts=allow_stale_drafts,
            )
        except SQLAlchemyError as exc:
            db.rollback()
            return {
                "ok": False,
                "status": "database_error",
                "preflight": preflight,
                "content": _empty_content_report(dry_run=dry_run),
                "error": exc.__class__.__name__,
            }

    return {
        "ok": bool(content["ok"]),
        "status": content["status"],
        "preflight": preflight,
        "content": content,
    }


def _resolve_publisher(db: Session, publisher_user_id: int | None) -> User | None:
    if publisher_user_id is not None:
        user = db.get(User, publisher_user_id)
        if user is None or user.role != "admin" or user.status != "active":
            return None
        return user
    return db.scalar(
        select(User)
        .where(
            User.role == "admin",
            User.status == "active",
        )
        .order_by(User.id)
        .limit(1)
    )


def _skipped_preflight_report() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "skipped",
    }


def _empty_content_report(*, dry_run: bool) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "not_run",
        "dry_run": dry_run,
        "publisher_user_id": None,
        "items": [],
        "counts": {
            "total": 0,
            "changed": 0,
            "created_pages": 0,
            "created_versions": 0,
            "repaired_pages": 0,
            "upgraded": 0,
            "conflicts": 0,
            "skipped": 0,
            "failed": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize built-in content pages after backend migrations.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument(
        "--publisher-user-id",
        type=int,
        default=None,
        help="Active admin user id to attribute initial content versions to. Defaults to the first active admin.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing them.")
    parser.add_argument(
        "--allow-reviewed-scripts",
        action="store_true",
        help="Confirm that built-in script references have been reviewed for initialization.",
    )
    parser.add_argument(
        "--upgrade-existing",
        action="store_true",
        help="Append a new version when an existing current page differs from the built-in schema.",
    )
    parser.add_argument(
        "--allow-stale-drafts",
        action="store_true",
        help="Allow upgrades even when active drafts for the same slug would become stale.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip database and Alembic head checks. Intended only for controlled tests or recovery.",
    )
    parser.add_argument(
        "--note",
        default="Built-in content initialization",
        help="Note stored on created content page versions.",
    )
    args = parser.parse_args(argv)
    report = run_content_initialization(
        database_url=args.database_url,
        publisher_user_id=args.publisher_user_id,
        dry_run=args.dry_run,
        skip_preflight=args.skip_preflight,
        note=args.note,
        allow_reviewed_scripts=args.allow_reviewed_scripts,
        upgrade_existing=args.upgrade_existing,
        allow_stale_drafts=args.allow_stale_drafts,
    )
    # Keep Windows legacy consoles safe when MySQL/system metadata contains
    # characters that cannot be encoded by the active OEM code page.
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
