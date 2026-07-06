from datetime import date, datetime

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_session_factory, reset_database_state
from app.main import create_app
from app.models import KnowledgeSnapshotRun
from app.models.base import utc_now
from app.services.knowledge_snapshot_runs import snapshot_run_key, snapshot_window
from app.services.knowledge_snapshot_scheduler import (
    SnapshotScheduleConfig,
    SnapshotScheduleJob,
    due_snapshot_jobs,
    should_run_snapshot_job,
)


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
        db.commit()
        assert should_run_snapshot_job(db, job, retry_attempts=3) is False


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
