from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import BackgroundTask, BackgroundTaskAttempt
from app.models.base import utc_now
from app.services.background_tasks import (
    cancel_background_task,
    claim_next_background_task,
    complete_background_task,
    enqueue_background_task,
    fail_background_task,
    heartbeat_background_task,
    retry_background_task,
)


def _session_factory():
    return get_session_factory(get_settings().database_url)


def test_background_task_enqueue_is_idempotent_and_claim_prefers_priority(client):
    now = utc_now()
    with _session_factory()() as db:
        low = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_run",
            idempotency_key="knowledge:1",
            source_type="knowledge_snapshot_run",
            source_id=1,
            payload={"run_id": 1},
            priority=1,
            available_at=now,
        )
        high = enqueue_background_task(
            db,
            task_type="alert_outbox_dispatch_plan",
            idempotency_key="alert-plan:2",
            source_type="admin_alert_outbox_dispatch_plan",
            source_id=2,
            payload={"plan_id": 2},
            priority=10,
            available_at=now,
        )
        duplicate = enqueue_background_task(
            db,
            task_type="alert_outbox_dispatch_plan",
            idempotency_key="alert-plan:2",
            source_type="admin_alert_outbox_dispatch_plan",
            source_id=2,
            payload={"plan_id": 999},
            priority=100,
            available_at=now,
        )
        db.commit()
        assert low.created is True
        assert high.created is True
        assert duplicate.created is False
        assert duplicate.task.id == high.task.id
        assert duplicate.task.payload_json == {"plan_id": 2}

    with _session_factory()() as db:
        lease = claim_next_background_task(db, worker_id="worker-a", lease_seconds=60, now=now)
        assert lease is not None
        assert lease.task_type == "alert_outbox_dispatch_plan"
        assert lease.source_id == 2
        assert lease.attempt_number == 1
        task = db.get(BackgroundTask, lease.task_id)
        assert task.status == "leased"
        assert task.lease_token == lease.lease_token
        assert db.scalar(
            select(BackgroundTaskAttempt).where(BackgroundTaskAttempt.task_id == task.id)
        ).status == "running"


def test_background_task_success_is_token_guarded_and_not_claimed_twice(client):
    now = utc_now()
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="content_script_asset_scan_run",
            idempotency_key="scan:success",
            source_type="content_script_asset_scan_run",
            source_id=7,
            payload={"run_id": 7},
            available_at=now,
        )
        db.commit()
        task_id = queued.task.id

    with _session_factory()() as first_db:
        lease = claim_next_background_task(first_db, worker_id="worker-a", lease_seconds=60, now=now)
        assert lease is not None
    with _session_factory()() as second_db:
        assert claim_next_background_task(second_db, worker_id="worker-b", lease_seconds=60, now=now) is None
    with _session_factory()() as db:
        assert heartbeat_background_task(
            db,
            lease,
            lease_seconds=120,
            now=now + timedelta(seconds=10),
        ) is True
        assert complete_background_task(
            db,
            lease,
            result_summary={"run_id": 7, "status": "success"},
            now=now + timedelta(seconds=20),
        ) is True
        task = db.get(BackgroundTask, task_id)
        assert task.status == "succeeded"
        assert task.result_summary_json == {"run_id": 7, "status": "success"}
        assert task.lease_token is None
        attempt = db.scalar(select(BackgroundTaskAttempt).where(BackgroundTaskAttempt.task_id == task_id))
        assert attempt.status == "succeeded"
    with _session_factory()() as db:
        assert complete_background_task(db, lease, now=now + timedelta(seconds=30)) is False


def test_retryable_background_task_uses_exponential_backoff_then_succeeds(client):
    now = utc_now()
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="alert_outbox_dispatch_plan",
            idempotency_key="alert-plan:retry",
            source_type="admin_alert_outbox_dispatch_plan",
            source_id=11,
            payload={"plan_id": 11},
            max_attempts=3,
            available_at=now,
        )
        db.commit()
        task_id = queued.task.id
        first = claim_next_background_task(db, worker_id="worker-a", lease_seconds=60, now=now)
        failure = fail_background_task(
            db,
            first,
            error_code="webhook_network_error",
            retryable=True,
            base_backoff_seconds=30,
            max_backoff_seconds=300,
            now=now + timedelta(seconds=5),
        )
        assert failure.status == "retry_wait"
        assert failure.next_available_at == now + timedelta(seconds=35)

    with _session_factory()() as db:
        assert claim_next_background_task(
            db,
            worker_id="worker-b",
            lease_seconds=60,
            now=now + timedelta(seconds=34),
        ) is None
        second = claim_next_background_task(
            db,
            worker_id="worker-b",
            lease_seconds=60,
            now=now + timedelta(seconds=35),
        )
        assert second is not None
        assert second.task_id == task_id
        assert second.attempt_number == 2
        assert complete_background_task(db, second, now=now + timedelta(seconds=40)) is True
        attempts = list(
            db.scalars(
                select(BackgroundTaskAttempt)
                .where(BackgroundTaskAttempt.task_id == task_id)
                .order_by(BackgroundTaskAttempt.attempt_number)
            ).all()
        )
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]


def test_nonretryable_task_enters_dead_letter_and_manual_retry_preserves_attempt_history(client):
    now = utc_now()
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_run",
            idempotency_key="knowledge:dead-letter",
            source_type="knowledge_snapshot_run",
            source_id=31,
            payload={"run_id": 31},
            max_attempts=5,
            available_at=now,
        )
        db.commit()
        task_id = queued.task.id
        lease = claim_next_background_task(db, worker_id="worker-a", lease_seconds=60, now=now)
        failure = fail_background_task(
            db,
            lease,
            error_code="invalid_payload",
            retryable=False,
            base_backoff_seconds=30,
            max_backoff_seconds=300,
            now=now + timedelta(seconds=1),
        )
        assert failure.status == "dead_letter"
        task, retried = retry_background_task(db, task_id, now=now + timedelta(seconds=2))
        assert retried is True
        assert task.status == "pending"
        second = claim_next_background_task(db, worker_id="worker-b", lease_seconds=60, now=now + timedelta(seconds=2))
        assert second.attempt_number == 2
        task, cancelled = cancel_background_task(db, task_id, now=now + timedelta(seconds=3))
        assert cancelled is True
        assert task.status == "cancelled"
        assert complete_background_task(db, second, now=now + timedelta(seconds=4)) is False
        attempts = list(
            db.scalars(
                select(BackgroundTaskAttempt)
                .where(BackgroundTaskAttempt.task_id == task_id)
                .order_by(BackgroundTaskAttempt.attempt_number)
            ).all()
        )
        assert [attempt.status for attempt in attempts] == ["failed", "cancelled"]


def test_expired_lease_is_reclaimed_and_old_worker_cannot_overwrite(client):
    now = utc_now()
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="content_script_asset_scan_run",
            idempotency_key="scan:lease-reclaim",
            source_type="content_script_asset_scan_run",
            source_id=41,
            payload={"run_id": 41},
            max_attempts=3,
            available_at=now,
        )
        db.commit()
        task_id = queued.task.id
        old_lease = claim_next_background_task(db, worker_id="worker-old", lease_seconds=30, now=now)

    with _session_factory()() as db:
        new_lease = claim_next_background_task(
            db,
            worker_id="worker-new",
            lease_seconds=60,
            now=now + timedelta(seconds=31),
        )
        assert new_lease is not None
        assert new_lease.task_id == task_id
        assert new_lease.attempt_number == 2
        assert complete_background_task(db, old_lease, now=now + timedelta(seconds=32)) is False
        assert complete_background_task(db, new_lease, now=now + timedelta(seconds=33)) is True
        attempts = list(
            db.scalars(
                select(BackgroundTaskAttempt)
                .where(BackgroundTaskAttempt.task_id == task_id)
                .order_by(BackgroundTaskAttempt.attempt_number)
            ).all()
        )
        assert [attempt.status for attempt in attempts] == ["lease_lost", "succeeded"]


def test_expired_final_lease_moves_task_and_attempt_to_dead_letter(client):
    now = utc_now()
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_rebuild",
            idempotency_key="knowledge:final-expired-lease",
            source_type="knowledge_snapshot_window",
            source_id=None,
            payload={"granularity": "day", "reference_date": now.date().isoformat()},
            max_attempts=1,
            available_at=now,
        )
        db.commit()
        task_id = queued.task.id
        assert claim_next_background_task(
            db,
            worker_id="worker-final",
            lease_seconds=30,
            now=now,
        ) is not None

    with _session_factory()() as db:
        assert claim_next_background_task(
            db,
            worker_id="worker-recovery",
            lease_seconds=30,
            now=now + timedelta(seconds=31),
        ) is None
        task = db.get(BackgroundTask, task_id)
        attempt = db.scalar(select(BackgroundTaskAttempt).where(BackgroundTaskAttempt.task_id == task_id))
        assert task.status == "dead_letter"
        assert task.last_error_code == "max_attempts_exhausted"
        assert attempt.status == "lease_lost"
        assert attempt.error_code == "max_attempts_exhausted"
        assert attempt.retryable is False
