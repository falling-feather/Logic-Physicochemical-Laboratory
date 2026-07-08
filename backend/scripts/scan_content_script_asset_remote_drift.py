from __future__ import annotations

import argparse
from datetime import UTC
import json
import sys
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentScriptAssetScanRun, User
from app.models.base import utc_now
from app.services.content_script_assets import scan_current_content_script_asset_remote_drift
from app.services.content_script_asset_scan_runs import (
    CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCRIPT,
    acquire_content_script_asset_scan_job_lease,
    content_script_asset_remote_drift_scan_filters,
    finish_content_script_asset_scan_run_failure,
    finish_content_script_asset_scan_run_success,
)


def run_scan(
    *,
    confirm_external_network: bool,
    actor_user_id: int | None = None,
    slug: str | None = None,
    source_host: str | None = None,
    issue_code: str | None = None,
    severity: str | None = None,
    limit: int = 25,
    offset: int = 0,
    database_url: str | None = None,
) -> dict:
    if not confirm_external_network:
        return {
            "ok": False,
            "status": "failed",
            "error": "ExternalNetworkConfirmationRequired",
        }
    settings = get_settings()
    url = database_url or settings.database_url
    session_factory = get_session_factory(url)
    now = utc_now()
    filters = content_script_asset_remote_drift_scan_filters(
        slug=slug,
        source_host=source_host,
        issue_code=issue_code,
        severity=severity,
        scan_limit=limit,
        scan_offset=offset,
        confirm_external_network=True,
    )
    run_key = f"content-script-remote-drift:script:{now.astimezone(UTC).strftime('%Y%m%dT%H%M%S%fZ')}:{uuid4().hex[:12]}"
    with session_factory() as db:
        actor = db.get(User, actor_user_id) if actor_user_id is not None else None
        if actor_user_id is not None and (actor is None or actor.status != "active"):
            return {
                "ok": False,
                "status": "failed",
                "error": "ActorUserNotFound",
                "actor_user_id": actor_user_id,
            }
        lease = acquire_content_script_asset_scan_job_lease(
            db,
            run_key=run_key,
            trigger_source=CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCRIPT,
            request_filters=filters,
            lease_owner=f"script:{uuid4().hex[:24]}",
            lease_seconds=settings.content_script_remote_drift_scheduler_lease_seconds,
            created_by_user_id=actor.id if actor is not None else None,
            now=now,
        )
        if lease is None:
            return {"ok": True, "status": "skipped", "reason": "lease_unavailable", "run_key": run_key}
        run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
        if run is None:
            return {"ok": False, "status": "failed", "error": "ScanRunMissing", "run_key": run_key}
        try:
            report = scan_current_content_script_asset_remote_drift(
                db,
                slug=slug,
                source_host=source_host,
                issue_code=issue_code,
                severity=severity,
                scan_limit=limit,
                scan_offset=offset,
                generated_at=now,
            )
            finish_content_script_asset_scan_run_success(run, report=report, finished_at=report.generated_at)
            db.commit()
            return {
                "ok": True,
                "status": run.status,
                "run_id": run.id,
                "run_key": run.run_key,
                "trigger_source": run.trigger_source,
                "alert_status": run.alert_status,
                "total_pages_scanned": report.total_pages_scanned,
                "total_external_references": report.total_external_references,
                "total_scanned_references": report.total_scanned_references,
                "total_remote_fetches": report.total_remote_fetches,
                "total_skipped_references": report.total_skipped_references,
                "total_issues": report.total_issues,
                "issue_counts_by_code": report.issue_counts_by_code,
                "issue_counts_by_severity": report.issue_counts_by_severity,
            }
        except Exception as exc:
            db.rollback()
            failed_run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
            if failed_run is not None:
                finish_content_script_asset_scan_run_failure(failed_run, error=exc, finished_at=utc_now())
                db.commit()
            return {
                "ok": False,
                "status": "failed",
                "error": exc.__class__.__name__,
                "run_key": run_key,
            }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run observe-only content script remote drift scan.")
    parser.add_argument("--confirm-external-network", action="store_true")
    parser.add_argument("--actor-user-id", type=int, default=None)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--source-host", default=None)
    parser.add_argument("--issue-code", default=None)
    parser.add_argument("--severity", choices=["critical", "warning", "info"], default=None)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    report = run_scan(
        confirm_external_network=args.confirm_external_network,
        actor_user_id=args.actor_user_id,
        slug=args.slug,
        source_host=args.source_host,
        issue_code=args.issue_code,
        severity=args.severity,
        limit=args.limit,
        offset=args.offset,
        database_url=args.database_url,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
