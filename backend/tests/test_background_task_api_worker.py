from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import (
    AdminAlertOutboxDispatchPlan,
    AdminAlertOutboxEntry,
    BackgroundTask,
    BackgroundTaskAttempt,
    ContentScriptAssetScanRun,
    KnowledgeSnapshotRun,
    User,
)
from app.services.alert_delivery import AlertDeliveryReceipt
from app.services.background_task_worker import BackgroundTaskWorker
from app.services.background_tasks import enqueue_background_task


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Cookie": ""}


def _bootstrap_admin(client, username: str = "background_task_admin") -> str:
    created = client.post(
        "/api/admin/bootstrap",
        json={"username": username, "password": "secret123", "display_name": "Task Admin"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _session_factory():
    return get_session_factory(get_settings().database_url)


def _bootstrap_admin_id(client, username: str) -> int:
    _bootstrap_admin(client, username=username)
    with _session_factory()() as db:
        return int(db.scalar(select(User.id).where(User.username == username)))


class _FakeAlertAdapter:
    provider = "webhook"
    delivery_target = "configured_webhook"

    def __init__(self) -> None:
        self.calls: list[tuple[dict, str]] = []

    def deliver(self, envelope: dict, *, idempotency_key: str) -> AlertDeliveryReceipt:
        self.calls.append((envelope, idempotency_key))
        return AlertDeliveryReceipt(provider="webhook", status_code=202, receipt_hash="a" * 64)


def test_admin_background_task_api_redacts_control_data_and_supports_recovery_actions(client):
    token = _bootstrap_admin(client)
    headers = _auth_header(token)
    request_body = {
        "granularity": "day",
        "reference_date": "2026-07-09",
        "priority": 7,
        "max_attempts": 4,
    }
    missing_confirmation = client.post(
        "/api/admin/background-tasks/knowledge-snapshots",
        headers=headers,
        json=request_body,
    )
    assert missing_confirmation.status_code == 422

    created = client.post(
        "/api/admin/background-tasks/knowledge-snapshots",
        headers=headers,
        json={**request_body, "confirm_enqueue": True},
    )
    assert created.status_code == 200
    created_body = created.json()
    task_id = created_body["id"]
    assert created_body["status"] == "pending"
    assert created_body["priority"] == 7
    assert created_body["payload_redacted"] is True
    assert "payload" not in created_body
    assert "lease_token" not in created_body

    duplicate = client.post(
        "/api/admin/background-tasks/knowledge-snapshots",
        headers=headers,
        json={**request_body, "confirm_enqueue": True},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == task_id

    queue = client.get("/api/admin/background-tasks/queue", headers=headers)
    assert queue.status_code == 200
    assert queue.json()["ready_count"] == 1
    assert queue.json()["policy"]["queue_backend"] == "database"
    assert queue.json()["policy"]["payload_redacted"] is True
    assert queue.json()["policy"]["lease_token_returned"] is False

    cancelled = client.post(
        f"/api/admin/background-tasks/{task_id}/cancel",
        headers=headers,
        json={"confirm_action": True, "reason": "operator test"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    retried = client.post(
        f"/api/admin/background-tasks/{task_id}/retry",
        headers=headers,
        json={"confirm_action": True, "reason": "configuration fixed"},
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "pending"

    listed = client.get("/api/admin/background-tasks?status=pending", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == task_id
    response_text = listed.text
    assert "reference_date" not in response_text
    assert "lease_token" not in response_text


def test_background_worker_reuses_successful_knowledge_snapshot_domain_run(client):
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_batch_size = 1
    with _session_factory()() as db:
        first = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_rebuild",
            idempotency_key="knowledge-snapshot:first:2026-07-09",
            source_type="knowledge_snapshot_window",
            source_id=None,
            payload={"granularity": "day", "reference_date": "2026-07-09"},
        )
        db.commit()
        first_task_id = first.task.id

    first_report = BackgroundTaskWorker(settings=settings, worker_id="knowledge-worker-a").run_once_sync()
    with _session_factory()() as db:
        first_task = db.get(BackgroundTask, first_task_id)
        assert first_report.succeeded_count == 1, (
            first_task.status,
            first_task.last_error_code,
            first_task.result_summary_json,
        )
        run = db.scalar(select(KnowledgeSnapshotRun))
        assert first_task.status == "succeeded"
        assert run.status == "success"
        assert run.attempt_count == 1
        run_id = run.id
        second = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_rebuild",
            idempotency_key="knowledge-snapshot:recovery:2026-07-09",
            source_type="knowledge_snapshot_window",
            source_id=None,
            payload={"granularity": "day", "reference_date": "2026-07-09"},
        )
        db.commit()
        second_task_id = second.task.id

    second_report = BackgroundTaskWorker(settings=settings, worker_id="knowledge-worker-b").run_once_sync()
    assert second_report.succeeded_count == 1
    with _session_factory()() as db:
        second_task = db.get(BackgroundTask, second_task_id)
        run = db.get(KnowledgeSnapshotRun, run_id)
        assert second_task.status == "succeeded"
        assert second_task.result_summary_json["recovered_existing_run"] is True
        assert run.attempt_count == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeSnapshotRun)) == 1


def test_background_worker_alert_delivery_uses_stable_key_and_terminal_recovery_skips_resend(client):
    actor_id = _bootstrap_admin_id(client, "background_task_alert_admin")
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_batch_size = 1
    now = datetime.now(UTC)
    with _session_factory()() as db:
        entry = AdminAlertOutboxEntry(
            source_type="knowledge_snapshot_run_alert",
            source_id=88,
            source_key="background-worker-secret-source",
            event_code="stale_running",
            severity="critical",
            action_hint="investigate",
            status="queued",
            dispatch_mode="manual_review",
            delivery_target="admin_outbox",
            external_delivery=False,
            dedupe_key="background-worker-alert-dedupe",
            payload_hash="8" * 64,
            payload_json={"secret": "must-never-leave"},
            first_seen_at=now,
            last_seen_at=now,
            seen_count=1,
        )
        db.add(entry)
        db.flush()
        plan = AdminAlertOutboxDispatchPlan(
            plan_key="background-worker-plan-key",
            plan_status="created",
            dry_run_status="ready",
            ready_entry_ids_json=[entry.id],
            ready_entry_payload_hashes_json={str(entry.id): entry.payload_hash},
            total_count=1,
            active_count=1,
            ready_count=1,
            generated_at=now,
        )
        db.add(plan)
        db.flush()
        first = enqueue_background_task(
            db,
            task_type="alert_outbox_dispatch_plan",
            idempotency_key="alert-background:first",
            source_type="admin_alert_outbox_dispatch_plan",
            source_id=plan.id,
            payload={"plan_id": plan.id},
            created_by_user_id=actor_id,
        )
        db.commit()
        entry_id = entry.id
        plan_id = plan.id
        first_task_id = first.task.id

    adapter = _FakeAlertAdapter()
    worker = BackgroundTaskWorker(
        settings=settings,
        worker_id="alert-worker-a",
        adapter_factory=lambda _: adapter,
    )
    first_report = worker.run_once_sync()
    assert first_report.succeeded_count == 1
    assert len(adapter.calls) == 1
    assert len(adapter.calls[0][1]) == 64
    assert "must-never-leave" not in str(adapter.calls[0][0])
    assert "background-worker-secret-source" not in str(adapter.calls[0][0])
    with _session_factory()() as db:
        assert db.get(BackgroundTask, first_task_id).status == "succeeded"
        assert db.get(AdminAlertOutboxDispatchPlan, plan_id).plan_status == "delivered"
        assert db.get(AdminAlertOutboxEntry, entry_id).status == "delivered"
        recovered = enqueue_background_task(
            db,
            task_type="alert_outbox_dispatch_plan",
            idempotency_key="alert-background:recovery",
            source_type="admin_alert_outbox_dispatch_plan",
            source_id=plan_id,
            payload={"plan_id": plan_id},
            created_by_user_id=actor_id,
        )
        db.commit()
        recovered_task_id = recovered.task.id

    second_report = worker.run_once_sync()
    assert second_report.succeeded_count == 1
    assert len(adapter.calls) == 1
    with _session_factory()() as db:
        recovered_task = db.get(BackgroundTask, recovered_task_id)
        assert recovered_task.result_summary_json["recovered_terminal_plan"] is True


def test_background_worker_dead_letters_invalid_payload_and_leaves_network_scan_queued_by_default(client):
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_batch_size = 2
    with _session_factory()() as db:
        invalid = enqueue_background_task(
            db,
            task_type="knowledge_snapshot_rebuild",
            idempotency_key="invalid-knowledge-task",
            source_type="knowledge_snapshot_window",
            source_id=None,
            payload={"granularity": "month", "reference_date": "not-a-date"},
        )
        scan = enqueue_background_task(
            db,
            task_type="content_script_asset_scan",
            idempotency_key="disabled-network-scan",
            source_type="content_script_asset_scan_request",
            source_id=None,
            payload={"slug": None, "source_host": None, "scan_limit": 25, "scan_offset": 0},
        )
        db.commit()
        invalid_id = invalid.task.id
        scan_id = scan.task.id

    report = BackgroundTaskWorker(settings=settings, worker_id="policy-worker").run_once_sync()
    assert report.claimed_count == 1
    assert report.dead_letter_count == 1
    with _session_factory()() as db:
        invalid_task = db.get(BackgroundTask, invalid_id)
        scan_task = db.get(BackgroundTask, scan_id)
        assert invalid_task.status == "dead_letter"
        assert invalid_task.last_error_code == "invalid_knowledge_snapshot_payload"
        assert scan_task.status == "pending"
        assert db.scalar(select(func.count()).select_from(ContentScriptAssetScanRun)) == 0
        attempts = list(
            db.scalars(select(BackgroundTaskAttempt).where(BackgroundTaskAttempt.task_id == invalid_id)).all()
        )
        assert len(attempts) == 1
        assert attempts[0].status == "failed"
        assert attempts[0].retryable is False


def test_background_worker_content_scan_opt_in_recovers_domain_success_without_duplicate_run(client):
    actor_id = _bootstrap_admin_id(client, "background_task_scan_admin")
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_batch_size = 1
    settings.background_task_worker_content_scan_enabled = True
    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="content_script_asset_scan",
            idempotency_key="enabled-empty-content-scan",
            source_type="content_script_asset_scan_request",
            source_id=None,
            payload={"slug": None, "source_host": None, "scan_limit": 25, "scan_offset": 0},
            created_by_user_id=actor_id,
        )
        db.commit()
        task_id = queued.task.id

    worker = BackgroundTaskWorker(settings=settings, worker_id="content-scan-worker")
    first_report = worker.run_once_sync()
    assert first_report.succeeded_count == 1
    with _session_factory()() as db:
        task = db.get(BackgroundTask, task_id)
        run = db.scalar(select(ContentScriptAssetScanRun))
        assert task.status == "succeeded"
        assert run.status == "success"
        assert run.attempt_count == 1
        run_id = run.id
        task.status = "pending"
        task.finished_at = None
        task.result_summary_json = {}
        db.commit()

    recovered_report = worker.run_once_sync()
    assert recovered_report.succeeded_count == 1
    with _session_factory()() as db:
        task = db.get(BackgroundTask, task_id)
        run = db.get(ContentScriptAssetScanRun, run_id)
        assert task.status == "succeeded"
        assert task.attempt_count == 2
        assert task.result_summary_json["recovered_existing_run"] is True
        assert run.attempt_count == 1
        assert db.scalar(select(func.count()).select_from(ContentScriptAssetScanRun)) == 1


def test_background_worker_reauthorizes_privileged_task_actor_before_execution(client):
    root_token = _bootstrap_admin(client, username="background_task_root_admin")
    registered = client.post(
        "/api/auth/register",
        json={
            "username": "background_task_revoked_admin",
            "password": "secret123",
            "display_name": "Revoked Task Admin",
            "role": "teacher",
        },
    )
    assert registered.status_code == 201
    actor_id = registered.json()["id"]
    promoted = client.patch(
        f"/api/admin/users/{actor_id}",
        headers=_auth_header(root_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == 200

    with _session_factory()() as db:
        queued = enqueue_background_task(
            db,
            task_type="content_script_asset_scan",
            idempotency_key="revoked-actor-content-scan",
            source_type="content_script_asset_scan_request",
            source_id=None,
            payload={"slug": None, "source_host": None, "scan_limit": 25, "scan_offset": 0},
            created_by_user_id=actor_id,
        )
        db.commit()
        task_id = queued.task.id

    demoted = client.patch(
        f"/api/admin/users/{actor_id}",
        headers=_auth_header(root_token),
        json={"role": "student"},
    )
    assert demoted.status_code == 200
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_content_scan_enabled = True
    report = BackgroundTaskWorker(settings=settings, worker_id="revoked-actor-worker").run_once_sync()
    assert report.dead_letter_count == 1
    with _session_factory()() as db:
        task = db.get(BackgroundTask, task_id)
        assert task.status == "dead_letter"
        assert task.last_error_code == "privileged_task_actor_unauthorized"
        assert db.scalar(select(func.count()).select_from(ContentScriptAssetScanRun)) == 0


def test_background_worker_materializes_due_schedule_as_unified_task_record(client):
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_batch_size = 1
    settings.knowledge_snapshot_scheduler_enabled = True
    settings.knowledge_snapshot_daily_enabled = True
    settings.knowledge_snapshot_daily_hour = 0
    settings.knowledge_snapshot_weekly_enabled = False
    settings.content_script_remote_drift_scheduler_enabled = False

    report = BackgroundTaskWorker(settings=settings, worker_id="schedule-producer-worker").run_once_sync()
    assert report.scheduled_enqueue_count == 1
    assert report.succeeded_count == 1
    with _session_factory()() as db:
        task = db.scalar(select(BackgroundTask))
        run = db.scalar(select(KnowledgeSnapshotRun))
        assert task.task_type == "knowledge_snapshot_rebuild"
        assert task.source_type == "knowledge_snapshot_schedule"
        assert task.status == "succeeded"
        assert run.status == "success"

    repeated = BackgroundTaskWorker(settings=settings, worker_id="schedule-producer-worker-b").run_once_sync()
    assert repeated.scheduled_enqueue_count == 0
    assert repeated.claimed_count == 0
    with _session_factory()() as db:
        assert db.scalar(select(func.count()).select_from(BackgroundTask)) == 1
        assert db.scalar(select(func.count()).select_from(KnowledgeSnapshotRun)) == 1
