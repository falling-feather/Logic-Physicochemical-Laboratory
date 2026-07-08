import asyncio
from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory, reset_database_state
from app.main import create_app
from app.models import KnowledgeSnapshotRun
from app.models.base import utc_now
from app.services.knowledge_snapshot_runs import (
    SnapshotRunLeaseLost,
    cancel_knowledge_snapshot_run,
    requeue_knowledge_snapshot_run,
    rebuild_periodic_knowledge_snapshots,
    snapshot_run_key,
    snapshot_window,
)
from app.services.knowledge_snapshot_scheduler import (
    KnowledgeSnapshotScheduler,
    SnapshotScheduleConfig,
    SnapshotScheduleJob,
    acquire_snapshot_job_lease,
    due_snapshot_jobs,
    heartbeat_snapshot_job_lease,
    should_run_snapshot_job,
)
from scripts.rebuild_knowledge_snapshots import run_rebuild


def test_due_snapshot_jobs_aligns_completed_day_and_week():
    config = SnapshotScheduleConfig()

    before_daily = due_snapshot_jobs(datetime(2026, 7, 3, 2, 59), config)
    assert before_daily == []

    after_daily = due_snapshot_jobs(datetime(2026, 7, 3, 3, 0), config)
    assert after_daily == [SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 2))]

    after_weekly = due_snapshot_jobs(datetime(2026, 7, 6, 4, 0), config)
    assert after_weekly == [
        SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 5)),
        SnapshotScheduleJob(granularity="week", reference_date=date(2026, 6, 29)),
    ]


def test_snapshot_scheduler_skips_success_and_retries_failed_runs(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)

    with get_session_factory(get_settings().database_url)() as db:
        assert should_run_snapshot_job(db, job, retry_attempts=3) is True
        run = KnowledgeSnapshotRun(
            run_key=run_key,
            granularity=job.granularity,
            period_start=period_start,
            period_end=period_end,
            trigger_source="pytest",
            status="success",
            started_at=utc_now(),
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={},
        )
        db.add(run)
        db.commit()

        assert should_run_snapshot_job(db, job, retry_attempts=3) is False

        run.status = "failed"
        run.attempt_count = 2
        db.commit()
        assert should_run_snapshot_job(db, job, retry_attempts=3) is True

        run.attempt_count = 3
        db.commit()
        assert should_run_snapshot_job(db, job, retry_attempts=3) is False

        run.status = "running"
        run.attempt_count = 1
        run.started_at = utc_now()
        run.scheduler_lease_owner = "worker-1"
        run.scheduler_lease_expires_at = utc_now()
        db.commit()
        assert should_run_snapshot_job(db, job, retry_attempts=3) is False
        assert should_run_snapshot_job(db, job, retry_attempts=3, lease_seconds=3600) is True


def test_snapshot_scheduler_does_not_retry_cancelled_runs(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 8))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)

    with get_session_factory(get_settings().database_url)() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-cancelled",
            lease_seconds=3600,
            now=datetime(2026, 7, 9, 2, 0),
        )
        assert lease is not None
        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert run is not None
        cancel_knowledge_snapshot_run(run, cancelled_by_user_id=1, clock=lambda: datetime(2026, 7, 9, 2, 45))
        db.commit()

        assert run.status == "cancelled"
        assert run.scheduler_lease_owner is None
        assert run.scheduler_lease_token is None
        assert run.scheduler_lease_expires_at is None
        assert run.scheduler_heartbeat_at is None
        assert (
            heartbeat_snapshot_job_lease(
                db,
                lease,
                lease_seconds=3600,
                now=datetime(2026, 7, 9, 2, 50),
            )
            is False
        )
        assert should_run_snapshot_job(db, job, retry_attempts=3, lease_seconds=3600) is False
        assert (
            acquire_snapshot_job_lease(
                db,
                job,
                retry_attempts=3,
                lease_owner="worker-after-cancel",
                lease_seconds=3600,
                now=datetime(2026, 7, 9, 4, 0),
            )
            is None
        )


def test_running_snapshot_run_without_lease_cannot_be_cancelled(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 10))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)

    with get_session_factory(get_settings().database_url)() as db:
        run = KnowledgeSnapshotRun(
            run_key=run_key,
            granularity=job.granularity,
            period_start=period_start,
            period_end=period_end,
            trigger_source="script",
            status="running",
            started_at=datetime(2026, 7, 11, 3, 0),
            attempt_count=1,
            metadata_json={"trigger_source": "script"},
        )
        db.add(run)
        db.commit()

        with pytest.raises(ValueError, match="scheduler lease"):
            cancel_knowledge_snapshot_run(run, cancelled_by_user_id=1)

        assert run.status == "running"
        assert run.finished_at is None


def test_snapshot_scheduler_claims_pending_requeued_runs(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 12))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)

    with get_session_factory(get_settings().database_url)() as db:
        run = KnowledgeSnapshotRun(
            run_key=run_key,
            granularity=job.granularity,
            period_start=period_start,
            period_end=period_end,
            trigger_source="scheduler",
            status="failed",
            started_at=datetime(2026, 7, 13, 3, 0),
            finished_at=datetime(2026, 7, 13, 3, 1),
            attempt_count=3,
            error_message="RuntimeError",
            metadata_json={"trigger_source": "scheduler"},
        )
        db.add(run)
        db.commit()

        requeue_knowledge_snapshot_run(
            run,
            requeued_by_user_id=1,
            lease_seconds=3600,
            clock=lambda: datetime(2026, 7, 13, 4, 0),
        )
        db.commit()

        assert run.status == "pending"
        assert run.attempt_count == 0
        assert should_run_snapshot_job(db, job, retry_attempts=3, lease_seconds=3600) is True

        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-requeue",
            lease_seconds=3600,
            now=datetime(2026, 7, 13, 4, 5),
        )
        assert lease is not None
        db.refresh(run)
        assert run.status == "running"
        assert run.scheduler_lease_owner == "worker-requeue"
        assert run.scheduler_lease_token == lease.lease_token
        assert run.scheduler_lease_expires_at == datetime(2026, 7, 13, 5, 5)


def test_snapshot_scheduler_run_once_processes_pending_runs_outside_due_window(client, monkeypatch):
    pending_job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 14))
    period_start, period_end = snapshot_window(pending_job.granularity, pending_job.reference_date)
    with get_session_factory(get_settings().database_url)() as db:
        db.add(
            KnowledgeSnapshotRun(
                run_key=snapshot_run_key(pending_job.granularity, period_start, period_end),
                granularity=pending_job.granularity,
                period_start=period_start,
                period_end=period_end,
                trigger_source="admin_requeue",
                status="pending",
                started_at=datetime(2026, 7, 20, 1, 0),
                attempt_count=0,
                metadata_json={"trigger_source": "admin_requeue"},
            )
        )
        db.commit()

    captured_jobs: list[tuple[str, date]] = []

    def fake_rebuild(db, **kwargs):
        captured_jobs.append((kwargs["granularity"], kwargs["reference_date"]))
        return SimpleNamespace(status="success", id=789, attempt_count=1)

    monkeypatch.setattr(
        "app.services.knowledge_snapshot_scheduler.rebuild_periodic_knowledge_snapshots",
        fake_rebuild,
    )
    scheduler = KnowledgeSnapshotScheduler(
        database_url=get_settings().database_url,
        schedule_config=SnapshotScheduleConfig(daily_enabled=False, weekly_enabled=False),
        retry_attempts=3,
        interval_seconds=300,
        lease_seconds=3600,
        heartbeat_seconds=45,
        instance_id="scheduler-pending-test",
    )

    results = asyncio.run(scheduler.run_once(now=datetime(2026, 7, 20, 1, 30)))

    assert results == [
        {
            "granularity": "day",
            "reference_date": "2026-07-14",
            "status": "success",
            "run_id": 789,
            "attempt_count": 1,
        }
    ]
    assert captured_jobs == [("day", date(2026, 7, 14))]


def test_snapshot_scheduler_lease_blocks_parallel_workers_until_expiry(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    now = datetime(2026, 7, 4, 3, 0)

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first_lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-1",
            lease_seconds=3600,
            now=now,
        )
        assert first_lease is not None
        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert run is not None
        assert run.status == "running"
        assert run.scheduler_lease_owner == "worker-1"
        assert run.scheduler_lease_token == first_lease.lease_token
        assert run.scheduler_lease_expires_at == datetime(2026, 7, 4, 4, 0)

    with session_factory() as db:
        assert acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-2",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 30),
        ) is None

    with session_factory() as db:
        second_lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-2",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 4, 1),
        )
        assert second_lease is not None
        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert run is not None
        assert run.scheduler_lease_owner == "worker-2"
        assert run.scheduler_lease_token == second_lease.lease_token
        assert run.scheduler_lease_expires_at == datetime(2026, 7, 4, 5, 1)


def test_snapshot_scheduler_lease_heartbeat_uses_token_guard(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-heartbeat",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 0),
        )
        assert lease is not None
        assert heartbeat_snapshot_job_lease(
            db,
            lease,
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 30),
        )

        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == lease.run_key))
        assert run is not None
        assert run.scheduler_heartbeat_at == datetime(2026, 7, 4, 3, 30)
        assert run.scheduler_lease_expires_at == datetime(2026, 7, 4, 4, 30)

        stale_lease = type(lease)(
            run_key=lease.run_key,
            lease_owner=lease.lease_owner,
            lease_token="stale-token",
            lease_expires_at=lease.lease_expires_at,
        )
        assert not heartbeat_snapshot_job_lease(
            db,
            stale_lease,
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 45),
        )


def test_snapshot_rebuild_releases_scheduler_lease(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-release",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 0),
        )
        assert lease is not None
        run = rebuild_periodic_knowledge_snapshots(
            db,
            granularity=job.granularity,
            reference_date=job.reference_date,
            trigger_source="scheduler",
            scheduler_lease_owner=lease.lease_owner,
            scheduler_lease_token=lease.lease_token,
        )
        assert run.status == "success"
        assert run.scheduler_lease_owner is None
        assert run.scheduler_lease_token is None
        assert run.scheduler_lease_expires_at is None
        assert run.scheduler_heartbeat_at is None

    with session_factory() as db:
        stored_run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert stored_run is not None
        assert stored_run.scheduler_lease_owner is None
        assert stored_run.scheduler_lease_token is None
        assert stored_run.scheduler_lease_expires_at is None
        assert stored_run.scheduler_heartbeat_at is None


def test_snapshot_rebuild_runs_automatic_lease_heartbeat(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    session_factory = get_session_factory(get_settings().database_url)
    heartbeat_calls: list[str] = []

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-auto-heartbeat",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 0),
        )
        assert lease is not None

        run = rebuild_periodic_knowledge_snapshots(
            db,
            granularity=job.granularity,
            reference_date=job.reference_date,
            trigger_source="scheduler",
            scheduler_lease_owner=lease.lease_owner,
            scheduler_lease_token=lease.lease_token,
            scheduler_lease_heartbeat=lambda: heartbeat_calls.append("beat") or True,
            scheduler_heartbeat_seconds=0,
        )

        assert run.status == "success"
        assert heartbeat_calls


def test_snapshot_rebuild_stops_when_automatic_heartbeat_loses_lease(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-heartbeat-lost",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 0),
        )
        assert lease is not None

        with pytest.raises(SnapshotRunLeaseLost):
            rebuild_periodic_knowledge_snapshots(
                db,
                granularity=job.granularity,
                reference_date=job.reference_date,
                trigger_source="scheduler",
                scheduler_lease_owner=lease.lease_owner,
                scheduler_lease_token=lease.lease_token,
                scheduler_lease_heartbeat=lambda: False,
                scheduler_heartbeat_seconds=0,
            )

    with session_factory() as db:
        stored_run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert stored_run is not None
        assert stored_run.status == "running"
        assert stored_run.scheduler_lease_owner == "worker-heartbeat-lost"
        assert stored_run.scheduler_lease_token == lease.lease_token
        assert stored_run.error_message is None


def test_snapshot_rebuild_with_cancelled_lease_cannot_restart_run(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 19))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-cancelled-before-start",
            lease_seconds=3600,
            now=datetime(2026, 7, 20, 3, 0),
        )
        assert lease is not None
        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert run is not None
        cancel_knowledge_snapshot_run(
            run,
            cancelled_by_user_id=1,
            clock=lambda: datetime(2026, 7, 20, 3, 5),
        )
        db.commit()

    with session_factory() as db:
        with pytest.raises(SnapshotRunLeaseLost):
            rebuild_periodic_knowledge_snapshots(
                db,
                granularity=job.granularity,
                reference_date=job.reference_date,
                trigger_source="scheduler",
                scheduler_lease_owner=lease.lease_owner,
                scheduler_lease_token=lease.lease_token,
                clock=lambda: datetime(2026, 7, 20, 3, 10),
            )

    with session_factory() as db:
        stored_run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert stored_run is not None
        assert stored_run.status == "cancelled"
        assert stored_run.finished_at == datetime(2026, 7, 20, 3, 5)
        assert stored_run.scheduler_lease_owner is None
        assert stored_run.scheduler_lease_token is None
        assert stored_run.scheduler_lease_expires_at is None
        assert stored_run.scheduler_heartbeat_at is None


def test_snapshot_rebuild_scheduler_owned_run_requires_lease_token(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 21))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        db.add(
            KnowledgeSnapshotRun(
                run_key=run_key,
                granularity=job.granularity,
                period_start=period_start,
                period_end=period_end,
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 22, 3, 0),
                scheduler_lease_owner="worker-missing-token",
                scheduler_lease_expires_at=datetime(2026, 7, 22, 4, 0),
                scheduler_heartbeat_at=datetime(2026, 7, 22, 3, 30),
                attempt_count=0,
                metadata_json={"trigger_source": "scheduler"},
            )
        )
        db.commit()

    with session_factory() as db:
        with pytest.raises(SnapshotRunLeaseLost, match="token"):
            rebuild_periodic_knowledge_snapshots(
                db,
                granularity=job.granularity,
                reference_date=job.reference_date,
                trigger_source="scheduler",
                scheduler_lease_owner="worker-missing-token",
                scheduler_lease_token=None,
            )


def test_snapshot_rebuild_with_stale_token_cannot_finish_run(client):
    job = SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 3))
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    session_factory = get_session_factory(get_settings().database_url)

    with session_factory() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-stale",
            lease_seconds=3600,
            now=datetime(2026, 7, 4, 3, 0),
        )
        assert lease is not None

    with session_factory() as db:
        run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert run is not None
        run.scheduler_lease_owner = "worker-current"
        run.scheduler_lease_token = "current-token"
        db.commit()

    with session_factory() as db:
        with pytest.raises(SnapshotRunLeaseLost):
            rebuild_periodic_knowledge_snapshots(
                db,
                granularity=job.granularity,
                reference_date=job.reference_date,
                trigger_source="scheduler",
                scheduler_lease_owner=lease.lease_owner,
                scheduler_lease_token=lease.lease_token,
            )

    with session_factory() as db:
        stored_run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
        assert stored_run is not None
        assert stored_run.status == "running"
        assert stored_run.scheduler_lease_owner == "worker-current"
        assert stored_run.scheduler_lease_token == "current-token"


def test_snapshot_rebuild_script_skips_when_lease_is_unavailable(client):
    reference_date = date(2026, 7, 12)
    job = SnapshotScheduleJob(granularity="day", reference_date=reference_date)
    with get_session_factory(get_settings().database_url)() as db:
        lease = acquire_snapshot_job_lease(
            db,
            job,
            retry_attempts=3,
            lease_owner="worker-blocking-script",
            lease_seconds=3600,
            now=datetime(2026, 7, 13, 3, 0),
        )
        assert lease is not None

    report = run_rebuild(
        granularity="day",
        reference_date=reference_date,
        database_url=get_settings().database_url,
    )

    assert report == {
        "ok": True,
        "status": "skipped",
        "reason": "lease_unavailable",
        "granularity": "day",
        "reference_date": "2026-07-12",
    }


def test_snapshot_scheduler_passes_automatic_heartbeat_to_rebuild(client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_rebuild(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status="success", id=123, attempt_count=1)

    monkeypatch.setattr(
        "app.services.knowledge_snapshot_scheduler.rebuild_periodic_knowledge_snapshots",
        fake_rebuild,
    )
    scheduler = KnowledgeSnapshotScheduler(
        database_url=get_settings().database_url,
        schedule_config=SnapshotScheduleConfig(),
        retry_attempts=3,
        interval_seconds=300,
        lease_seconds=3600,
        heartbeat_seconds=45,
        instance_id="scheduler-heartbeat-test",
    )

    result = scheduler._run_job_if_needed(SnapshotScheduleJob(granularity="day", reference_date=date(2026, 7, 20)))

    assert result["status"] == "success"
    assert callable(captured["scheduler_lease_heartbeat"])
    assert captured["scheduler_heartbeat_seconds"] == 45
    assert captured["scheduler_lease_owner"] == "scheduler-heartbeat-test"
    assert isinstance(captured["scheduler_lease_token"], str)


def test_snapshot_rebuild_script_passes_automatic_heartbeat_to_rebuild(client, monkeypatch):
    captured: dict[str, object] = {}

    def fake_rebuild(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            status="success",
            id=456,
            run_key="knowledge:day:fake",
            granularity=kwargs["granularity"],
            period_start=datetime(2026, 7, 20),
            period_end=datetime(2026, 7, 20, 23, 59, 59),
            trigger_source=kwargs["trigger_source"],
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            error_message=None,
            metadata_json={"trigger_source": kwargs["trigger_source"]},
        )

    monkeypatch.setattr("scripts.rebuild_knowledge_snapshots.rebuild_periodic_knowledge_snapshots", fake_rebuild)

    report = run_rebuild(
        granularity="day",
        reference_date=date(2026, 7, 20),
        database_url=get_settings().database_url,
    )

    assert report["ok"] is True
    assert callable(captured["scheduler_lease_heartbeat"])
    assert captured["scheduler_heartbeat_seconds"] == get_settings().knowledge_snapshot_scheduler_heartbeat_seconds
    assert str(captured["scheduler_lease_owner"]).startswith("script:")
    assert isinstance(captured["scheduler_lease_token"], str)


def test_snapshot_scheduler_is_not_registered_by_default(client):
    assert not hasattr(client.app.state, "knowledge_snapshot_scheduler")


def test_snapshot_scheduler_registers_when_enabled(monkeypatch):
    monkeypatch.setenv("ASTRA_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("ASTRA_KNOWLEDGE_SNAPSHOT_SCHEDULER_INTERVAL_SECONDS", "3600")
    get_settings.cache_clear()
    reset_database_state()
    try:
        with TestClient(create_app()) as test_client:
            assert hasattr(test_client.app.state, "knowledge_snapshot_scheduler")
    finally:
        get_settings.cache_clear()
        reset_database_state()
