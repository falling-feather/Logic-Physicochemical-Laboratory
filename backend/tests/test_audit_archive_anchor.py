import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditArchiveAnchor, AuditLog, BackgroundTask, BackgroundTaskAttempt, User
from app.services import audit_anchor_delivery
from app.services.audit import audit_log_chain_hash
from app.services.audit_anchor_delivery import (
    AuditAnchorDeliveryError,
    AuditAnchorReceipt,
)
from app.services.audit_archive_anchors import enqueue_audit_archive_anchor
from app.services.background_task_worker import BackgroundTaskWorker
from app.services.background_tasks import enqueue_background_task
from scripts.anchor_audit_archive import run_anchor_request
from scripts.archive_audit_logs import run_archive


class _FakeAuditAnchorAdapter:
    provider = "webhook"

    def __init__(self, *, fail_count: int = 0) -> None:
        self.fail_count = fail_count
        self.calls: list[tuple[dict, str]] = []

    def anchor(self, envelope: dict, *, idempotency_key: str) -> AuditAnchorReceipt:
        self.calls.append((envelope, idempotency_key))
        if len(self.calls) <= self.fail_count:
            raise AuditAnchorDeliveryError("anchor_network_error", retryable=True)
        return AuditAnchorReceipt(
            provider="webhook",
            status_code=202,
            receipt_id="staging-receipt-001",
            anchored_at=datetime(2026, 7, 10, 9, 30, tzinfo=UTC),
            receipt_hash="a" * 64,
        )


class _FakeAnchorResponse:
    status = 202

    def __init__(self, body: dict) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int) -> bytes:
        assert limit == 64 * 1024
        return json.dumps(self.body).encode("utf-8")


def _session_factory():
    return get_session_factory(get_settings().database_url)


def _bootstrap_admin_id(client, username: str) -> int:
    created = client.post(
        "/api/admin/bootstrap",
        json={"username": username, "password": "secret123", "display_name": "Anchor Admin"},
    )
    assert created.status_code == 201
    with _session_factory()() as db:
        return int(db.scalar(select(User.id).where(User.username == username)))


@pytest.fixture()
def anchor_output_dir():
    root = Path.cwd() / ".tmp-test-audit-anchor"
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _archive_for_anchor(output_dir: Path) -> tuple[Path, int, str]:
    now = datetime.now(UTC)
    with _session_factory()() as db:
        log = AuditLog(
            action="audit.anchor.staging",
            resource="audit_archive:staging",
            resource_type="audit_archive",
            event_result="success",
            snapshot_json={"proof": "included-for-full-verification"},
            created_at=now - timedelta(days=400),
            updated_at=now - timedelta(days=400),
        )
        log.current_hash = audit_log_chain_hash(log)
        db.add(log)
        db.commit()
        log_id = log.id
        log_hash = log.current_hash
    report = run_archive(
        output_dir=output_dir,
        before_at=now - timedelta(days=365),
        action="audit.anchor.staging",
        include_snapshot=True,
    )
    return output_dir / report["manifest"]["manifest_file"], log_id, log_hash


def test_audit_anchor_staging_worker_sends_hash_only_envelope_and_recovers(anchor_output_dir, client):
    actor_id = _bootstrap_admin_id(client, "audit_anchor_staging_admin")
    manifest_path, log_id, original_hash = _archive_for_anchor(anchor_output_dir)
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_audit_anchor_enabled = True
    settings.background_task_worker_batch_size = 1
    with _session_factory()() as db:
        queued = enqueue_audit_archive_anchor(
            db,
            manifest_path=manifest_path,
            settings=settings,
            created_by_user_id=actor_id,
        )
        db.commit()
        anchor_id = queued.anchor.id
        task_id = queued.task_result.task.id

    adapter = _FakeAuditAnchorAdapter()
    worker = BackgroundTaskWorker(
        settings=settings,
        worker_id="audit-anchor-staging-worker",
        audit_anchor_adapter_factory=lambda _: adapter,
    )
    report = worker.run_once_sync()
    assert report.succeeded_count == 1
    assert len(adapter.calls) == 1
    envelope, idempotency_key = adapter.calls[0]
    assert envelope["schema"] == "astra.audit-archive-anchor.v1"
    assert envelope["range"]["first_log_id"] == log_id
    assert envelope["range"]["last_log_id"] == log_id
    assert envelope["chain"]["end_current_hash"] == original_hash
    assert idempotency_key.endswith(envelope["manifest_sha256"])
    serialized = json.dumps(envelope, ensure_ascii=False)
    assert "manifest_path" not in serialized
    assert "snapshot" not in serialized
    assert "included-for-full-verification" not in serialized

    with _session_factory()() as db:
        anchor = db.get(AuditArchiveAnchor, anchor_id)
        task = db.get(BackgroundTask, task_id)
        assert anchor.status == "anchored"
        assert anchor.attempt_count == 1
        assert anchor.external_receipt_id == "staging-receipt-001"
        assert anchor.receipt_hash == "a" * 64
        assert task.status == "succeeded"
        original = db.get(AuditLog, log_id)
        assert original.current_hash == original_hash
        recovery = enqueue_background_task(
            db,
            task_type="audit_archive_anchor",
            idempotency_key="audit-anchor-recovery-task",
            source_type="audit_archive_anchor",
            source_id=anchor_id,
            payload={"anchor_id": anchor_id, "manifest_path": str(manifest_path.resolve())},
            created_by_user_id=actor_id,
        )
        db.commit()
        recovery_task_id = recovery.task.id

    recovered = worker.run_once_sync()
    assert recovered.succeeded_count == 1
    assert len(adapter.calls) == 1
    with _session_factory()() as db:
        task = db.get(BackgroundTask, recovery_task_id)
        assert task.result_summary_json["recovered_existing_anchor"] is True


def test_audit_anchor_failure_records_retry_and_eventual_receipt(anchor_output_dir, client):
    actor_id = _bootstrap_admin_id(client, "audit_anchor_retry_admin")
    manifest_path, _, _ = _archive_for_anchor(anchor_output_dir)
    settings = get_settings().model_copy(deep=True)
    settings.background_task_worker_audit_anchor_enabled = True
    settings.background_task_worker_batch_size = 1
    settings.background_task_worker_base_backoff_seconds = 1
    with _session_factory()() as db:
        queued = enqueue_audit_archive_anchor(
            db,
            manifest_path=manifest_path,
            settings=settings,
            created_by_user_id=actor_id,
        )
        db.commit()
        anchor_id = queued.anchor.id
        task_id = queued.task_result.task.id

    adapter = _FakeAuditAnchorAdapter(fail_count=1)
    worker = BackgroundTaskWorker(
        settings=settings,
        worker_id="audit-anchor-retry-worker",
        audit_anchor_adapter_factory=lambda _: adapter,
    )
    first = worker.run_once_sync()
    assert first.retry_wait_count == 1
    with _session_factory()() as db:
        anchor = db.get(AuditArchiveAnchor, anchor_id)
        task = db.get(BackgroundTask, task_id)
        assert anchor.status == "failed"
        assert anchor.last_error_code == "anchor_network_error"
        assert anchor.attempt_count == 1
        assert task.status == "retry_wait"
        task.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    second = worker.run_once_sync()
    assert second.succeeded_count == 1
    assert len(adapter.calls) == 2
    assert adapter.calls[0][1] == adapter.calls[1][1]
    with _session_factory()() as db:
        anchor = db.get(AuditArchiveAnchor, anchor_id)
        task = db.get(BackgroundTask, task_id)
        attempts = list(
            db.scalars(
                select(BackgroundTaskAttempt)
                .where(BackgroundTaskAttempt.task_id == task_id)
                .order_by(BackgroundTaskAttempt.attempt_number)
            ).all()
        )
        assert anchor.status == "anchored"
        assert anchor.attempt_count == 2
        assert anchor.last_error_code is None
        assert task.status == "succeeded"
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]


def test_audit_anchor_cli_requires_confirmation_and_enqueue_is_idempotent(anchor_output_dir, client):
    actor_id = _bootstrap_admin_id(client, "audit_anchor_cli_admin")
    manifest_path, _, _ = _archive_for_anchor(anchor_output_dir)
    denied = run_anchor_request(manifest_path=manifest_path, confirm_external_anchor=False)
    assert denied["ok"] is False
    assert denied["status"] == "confirmation_required"

    unauthorized = run_anchor_request(manifest_path=manifest_path, confirm_external_anchor=True)
    assert unauthorized["ok"] is False
    assert unauthorized["error_code"] == "audit_anchor_actor_unauthorized"
    first = run_anchor_request(
        manifest_path=manifest_path,
        confirm_external_anchor=True,
        actor_user_id=actor_id,
    )
    second = run_anchor_request(
        manifest_path=manifest_path,
        confirm_external_anchor=True,
        actor_user_id=actor_id,
    )
    assert first["ok"] is True
    assert first["anchor_created"] is True
    assert first["task_created"] is True
    assert first["anchor"]["manifest_path_returned"] is False
    assert second["anchor_created"] is False
    assert second["task_created"] is False
    assert second["task_id"] == first["task_id"]
    with _session_factory()() as db:
        assert db.scalar(select(func.count()).select_from(AuditArchiveAnchor)) == 1
        assert db.scalar(select(func.count()).select_from(BackgroundTask)) == 1


def test_webhook_audit_anchor_adapter_validates_manifest_hash_and_redacts_token(monkeypatch):
    captured = {}
    manifest_hash = "b" * 64

    def fake_open(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeAnchorResponse(
            {
                "receiptId": "external-staging-42",
                "manifestSha256": manifest_hash,
                "anchoredAt": "2026-07-10T09:30:00Z",
            }
        )

    monkeypatch.setattr(audit_anchor_delivery, "_open_anchor_request", fake_open)
    adapter = audit_anchor_delivery.WebhookAuditAnchorAdapter(
        url="https://anchor.example.test/v1/receipts",
        token="anchor-secret-token",
        timeout_seconds=7,
    )
    envelope = {"schema": "astra.audit-archive-anchor.v1", "manifest_sha256": manifest_hash}
    receipt = adapter.anchor(envelope, idempotency_key="anchor-idempotency-key")
    assert receipt.receipt_id == "external-staging-42"
    assert receipt.anchored_at == datetime(2026, 7, 10, 9, 30, tzinfo=UTC)
    assert len(receipt.receipt_hash) == 64
    request = captured["request"]
    assert captured["timeout"] == 7
    assert request.get_header("Authorization") == "Bearer anchor-secret-token"
    assert request.get_header("Idempotency-key") == "anchor-idempotency-key"
    assert b"anchor-secret-token" not in request.data
