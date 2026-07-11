from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import os
import socket
from typing import Callable
import uuid

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import ContentScriptAssetScanRun, User
from app.models.base import utc_now
from app.services.content_script_assets import scan_current_content_script_asset_remote_drift
from app.services.content_script_asset_scan_runs import (
    CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCHEDULER,
    acquire_content_script_asset_scan_job_lease,
    content_script_asset_remote_drift_scan_filters,
    finish_content_script_asset_scan_run_failure,
    finish_content_script_asset_scan_run_success,
    heartbeat_content_script_asset_scan_job_lease,
    scheduled_content_script_remote_drift_run_key,
)


@dataclass(frozen=True)
class ContentScriptRemoteDriftScheduleConfig:
    scan_limit: int = 25
    scan_offset: int = 0
    source_host: str | None = None
    slug: str | None = None
    actor_user_id: int | None = None


class ContentScriptRemoteDriftScheduler:
    def __init__(
        self,
        *,
        database_url: str,
        schedule_config: ContentScriptRemoteDriftScheduleConfig,
        interval_seconds: int,
        lease_seconds: int,
        run_on_start: bool = False,
        clock: Callable[[], datetime] = utc_now,
        instance_id: str | None = None,
    ) -> None:
        self.database_url = database_url
        self.schedule_config = schedule_config
        self.interval_seconds = interval_seconds
        self.lease_seconds = lease_seconds
        self.run_on_start = run_on_start
        self.clock = clock
        self.instance_id = instance_id or _default_scheduler_instance_id()
        self._lock = asyncio.Lock()
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._serve(), name="content-script-remote-drift-scheduler")

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None
        self._stop_event = None

    async def run_once(self, now: datetime | None = None) -> dict:
        async with self._lock:
            return await asyncio.to_thread(self._run_once_sync, now or self.clock())

    async def _serve(self) -> None:
        if self.run_on_start:
            await self.run_once()
        while self._stop_event is not None:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                break
            except TimeoutError:
                await self.run_once()

    def _run_once_sync(self, now: datetime) -> dict:
        filters = content_script_asset_remote_drift_scan_filters(
            slug=self.schedule_config.slug,
            source_host=self.schedule_config.source_host,
            scan_limit=self.schedule_config.scan_limit,
            scan_offset=self.schedule_config.scan_offset,
            confirm_external_network=True,
        )
        run_key = scheduled_content_script_remote_drift_run_key(
            scheduled_for=now,
            filters=filters,
            interval_seconds=self.interval_seconds,
        )
        session_factory = get_session_factory(self.database_url)
        with session_factory() as db:
            actor = _scheduler_actor(db, self.schedule_config.actor_user_id)
            if actor is None:
                return {
                    "ok": True,
                    "status": "skipped",
                    "reason": "active_admin_actor_required",
                    "run_key": run_key,
                }
            lease = acquire_content_script_asset_scan_job_lease(
                db,
                run_key=run_key,
                trigger_source=CONTENT_SCRIPT_ASSET_SCAN_TRIGGER_SCHEDULER,
                request_filters=filters,
                lease_owner=self.instance_id,
                lease_seconds=self.lease_seconds,
                created_by_user_id=actor.id if actor is not None else None,
                now=now,
            )
            if lease is None:
                return {
                    "ok": True,
                    "status": "skipped",
                    "reason": "lease_unavailable",
                    "run_key": run_key,
                }
            heartbeat_content_script_asset_scan_job_lease(db, lease, lease_seconds=self.lease_seconds, now=now)
            run = db.scalar(select(ContentScriptAssetScanRun).where(ContentScriptAssetScanRun.run_key == run_key))
            if run is None:
                return {
                    "ok": False,
                    "status": "failed",
                    "error": "ScanRunMissing",
                    "run_key": run_key,
                }
            try:
                report = scan_current_content_script_asset_remote_drift(
                    db,
                    slug=self.schedule_config.slug,
                    source_host=self.schedule_config.source_host,
                    scan_limit=self.schedule_config.scan_limit,
                    scan_offset=self.schedule_config.scan_offset,
                    generated_at=now,
                )
                run = finish_content_script_asset_scan_run_success(
                    db,
                    lease,
                    report=report,
                    finished_at=self.clock(),
                )
                if run is None:
                    return {
                        "ok": False,
                        "status": "lease_lost",
                        "error": "ScanLeaseLost",
                        "run_key": run_key,
                    }
                db.commit()
                return {
                    "ok": True,
                    "status": run.status,
                    "run_id": run.id,
                    "run_key": run.run_key,
                    "alert_status": run.alert_status,
                    "total_issues": report.total_issues,
                    "total_scanned_references": report.total_scanned_references,
                    "total_remote_fetches": report.total_remote_fetches,
                }
            except Exception as exc:
                db.rollback()
                failed_run = finish_content_script_asset_scan_run_failure(
                    db,
                    lease,
                    error=exc,
                    finished_at=self.clock(),
                )
                if failed_run is not None:
                    db.commit()
                return {
                    "ok": False,
                    "status": "failed",
                    "error": exc.__class__.__name__,
                    "run_key": run_key,
                }


def scheduler_from_settings(settings) -> ContentScriptRemoteDriftScheduler:
    return ContentScriptRemoteDriftScheduler(
        database_url=settings.database_url,
        schedule_config=ContentScriptRemoteDriftScheduleConfig(
            scan_limit=settings.content_script_remote_drift_scheduler_scan_limit,
            source_host=settings.content_script_remote_drift_scheduler_source_host,
            slug=settings.content_script_remote_drift_scheduler_slug,
            actor_user_id=settings.content_script_remote_drift_scheduler_actor_user_id,
        ),
        interval_seconds=settings.content_script_remote_drift_scheduler_interval_seconds,
        lease_seconds=settings.content_script_remote_drift_scheduler_lease_seconds,
        run_on_start=settings.content_script_remote_drift_scheduler_run_on_start,
    )


def _scheduler_actor(db, actor_user_id: int | None) -> User | None:
    if actor_user_id is None:
        return None
    actor = db.get(User, actor_user_id)
    if actor is None or actor.status != "active" or actor.role != "admin":
        return None
    return actor


def _default_scheduler_instance_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
