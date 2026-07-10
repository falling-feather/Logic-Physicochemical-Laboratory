from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditArchiveAnchor
from app.services.audit_anchor_delivery import audit_anchor_posture
from app.services.audit_archive_anchors import (
    AuditArchiveAnchorError,
    audit_archive_anchor_read,
    enqueue_audit_archive_anchor,
)
from app.services.background_task_worker import BackgroundTaskWorker


def run_anchor_request(
    *,
    manifest_path: Path,
    confirm_external_anchor: bool,
    run_once: bool = False,
    database_url: str | None = None,
    actor_user_id: int | None = None,
) -> dict:
    if not confirm_external_anchor:
        return {
            "ok": False,
            "status": "confirmation_required",
            "required_flag": "--confirm-external-anchor",
        }
    settings = get_settings().model_copy(deep=True)
    if database_url:
        settings.database_url = database_url
    session_factory = get_session_factory(settings.database_url)
    try:
        with session_factory() as db:
            result = enqueue_audit_archive_anchor(
                db,
                manifest_path=manifest_path,
                settings=settings,
                created_by_user_id=actor_user_id,
            )
            db.commit()
            db.refresh(result.anchor)
            anchor_report = audit_archive_anchor_read(result.anchor)
            task_id = result.task_result.task.id
    except (AuditArchiveAnchorError, OSError, SQLAlchemyError, ValueError) as exc:
        code = exc.code if isinstance(exc, AuditArchiveAnchorError) else exc.__class__.__name__
        return {"ok": False, "status": "failed", "error_code": code}
    worker_report = None
    if run_once:
        settings.background_task_worker_audit_anchor_enabled = True
        worker_report = BackgroundTaskWorker(
            settings=settings,
            task_type_allowlist={"audit_archive_anchor"},
        ).run_once_sync().as_dict()
        with session_factory() as db:
            refreshed = db.get(AuditArchiveAnchor, anchor_report["id"])
            if refreshed is not None:
                anchor_report = audit_archive_anchor_read(refreshed)
    return {
        "ok": anchor_report["status"] != "failed",
        "status": anchor_report["status"],
        "anchor_created": result.anchor_created,
        "task_created": result.task_result.created,
        "task_id": task_id,
        "anchor": anchor_report,
        "worker": worker_report,
        "posture": audit_anchor_posture(settings),
    }


def read_anchor_status(*, anchor_id: int, database_url: str | None = None) -> dict:
    settings = get_settings()
    target_url = database_url or settings.database_url
    with get_session_factory(target_url)() as db:
        anchor = db.get(AuditArchiveAnchor, anchor_id)
        if anchor is None:
            return {"ok": False, "status": "not_found", "anchor_id": anchor_id}
        return {"ok": True, "status": anchor.status, "anchor": audit_archive_anchor_read(anchor)}


def list_anchor_statuses(*, database_url: str | None = None, limit: int = 50) -> dict:
    settings = get_settings()
    target_url = database_url or settings.database_url
    with get_session_factory(target_url)() as db:
        anchors = list(
            db.scalars(
                select(AuditArchiveAnchor)
                .order_by(AuditArchiveAnchor.id.desc())
                .limit(limit)
            ).all()
        )
    return {
        "ok": True,
        "status": "listed",
        "items": [audit_archive_anchor_read(anchor) for anchor in anchors],
        "count": len(anchors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Queue and inspect external audit archive hash anchors.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--status", type=int, default=None, dest="anchor_id")
    parser.add_argument("--list", action="store_true", dest="list_anchors")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--actor-user-id", type=int, default=None)
    parser.add_argument("--confirm-external-anchor", action="store_true")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Immediately run one worker batch; external anchor configuration must already be enabled.",
    )
    args = parser.parse_args(argv)
    selected = int(args.manifest is not None) + int(args.anchor_id is not None) + int(args.list_anchors)
    if selected != 1:
        report = {"ok": False, "status": "select_exactly_one_action"}
    elif args.manifest is not None:
        report = run_anchor_request(
            manifest_path=args.manifest,
            confirm_external_anchor=args.confirm_external_anchor,
            run_once=args.run_once,
            database_url=args.database_url,
            actor_user_id=args.actor_user_id,
        )
    elif args.anchor_id is not None:
        report = read_anchor_status(anchor_id=args.anchor_id, database_url=args.database_url)
    else:
        report = list_anchor_statuses(database_url=args.database_url, limit=max(1, min(args.limit, 500)))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
