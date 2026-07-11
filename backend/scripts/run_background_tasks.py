from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.services.background_task_worker import BackgroundTaskWorker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the persistent Astra background task worker.")
    parser.add_argument("--once", action="store_true", help="Claim at most one configured batch, then exit.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this worker.")
    parser.add_argument("--worker-id", default=None, help="Stable operational worker label for this process.")
    parser.add_argument(
        "--enable-content-scan",
        action="store_true",
        help="Allow queued content script scans to perform external network requests.",
    )
    parser.add_argument(
        "--enable-audit-anchor",
        action="store_true",
        help="Allow queued audit archive anchors to call the configured external receipt service.",
    )
    args = parser.parse_args(argv)
    settings = get_settings().model_copy(deep=True)
    if args.database_url:
        settings.database_url = args.database_url
    if args.enable_content_scan:
        settings.background_task_worker_content_scan_enabled = True
    if args.enable_audit_anchor:
        settings.background_task_worker_audit_anchor_enabled = True
    worker = BackgroundTaskWorker(settings=settings, worker_id=args.worker_id)
    if args.once:
        report = worker.run_once_sync().as_dict()
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    try:
        asyncio.run(_serve(worker))
    except KeyboardInterrupt:
        return 130
    return 0


async def _serve(worker: BackgroundTaskWorker) -> None:
    worker.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await worker.stop()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
