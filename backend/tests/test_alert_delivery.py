import json
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.api.endpoints import admin as admin_endpoint
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AdminAlertOutboxDispatchPlan, AdminAlertOutboxEntry
from app.services.alert_delivery import AlertDeliveryError, AlertDeliveryReceipt
from app.services import alert_delivery


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client) -> str:
    created = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "alert_delivery_admin",
            "password": "secret123",
            "display_name": "Alert Delivery Admin",
        },
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "alert_delivery_admin", "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


class _FakeWebhookAdapter:
    provider = "webhook"
    delivery_target = "configured_webhook"

    def __init__(self, fail_entry_ids: set[int]) -> None:
        self.fail_entry_ids = fail_entry_ids
        self.calls: list[tuple[dict, str]] = []

    def deliver(self, envelope: dict, *, idempotency_key: str) -> AlertDeliveryReceipt:
        self.calls.append((envelope, idempotency_key))
        if envelope["entry_id"] in self.fail_entry_ids:
            raise AlertDeliveryError("webhook_network_error", retryable=True)
        return AlertDeliveryReceipt(
            provider=self.provider,
            status_code=202,
            receipt_hash=f"{'a' * 63}{envelope['entry_id'] % 10}",
        )


class _FakeWebhookResponse:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int) -> bytes:
        assert limit == 64 * 1024
        return b'{"accepted":true}'


def test_webhook_adapter_posts_signed_json_without_putting_token_in_body(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeWebhookResponse()

    monkeypatch.setattr(alert_delivery, "_open_webhook_request", fake_urlopen)
    adapter = alert_delivery.WebhookAlertDeliveryAdapter(
        url="https://alerts.example.test/astra",
        token="adapter-secret-token",
        timeout_seconds=7,
    )
    envelope = {"schema": "astra.alert-envelope.v1", "entry_id": 11, "payload_hash": "a" * 64}
    receipt = adapter.deliver(envelope, idempotency_key="i" * 64)

    assert receipt.status_code == 202
    assert receipt.provider == "webhook"
    assert len(receipt.receipt_hash) == 64
    assert captured["timeout"] == 7
    request = captured["request"]
    assert request.full_url == "https://alerts.example.test/astra"
    assert request.get_header("Authorization") == "Bearer adapter-secret-token"
    assert request.get_header("Idempotency-key") == "i" * 64
    assert len(request.get_header("X-astra-signature-sha256")) == 64
    assert json.loads(request.data.decode("utf-8")) == envelope
    assert b"adapter-secret-token" not in request.data


def test_webhook_adapter_maps_network_failure_to_retryable_code(monkeypatch):
    def fail_urlopen(request, timeout):
        raise alert_delivery.urllib_error.URLError("secret upstream error")

    monkeypatch.setattr(alert_delivery, "_open_webhook_request", fail_urlopen)
    adapter = alert_delivery.WebhookAlertDeliveryAdapter(
        url="https://alerts.example.test/astra",
        token="adapter-secret-token",
        timeout_seconds=5,
    )
    with pytest.raises(AlertDeliveryError) as captured:
        adapter.deliver({"entry_id": 12}, idempotency_key="j" * 64)
    assert captured.value.code == "webhook_network_error"
    assert captured.value.retryable is True
    assert "secret upstream error" not in str(captured.value)


def test_webhook_transport_installs_no_redirect_handler(monkeypatch):
    captured = {}

    class _FakeOpener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeWebhookResponse()

    def fake_build_opener(handler):
        captured["handler"] = handler
        return _FakeOpener()

    monkeypatch.setattr(alert_delivery.urllib_request, "build_opener", fake_build_opener)
    request = alert_delivery.urllib_request.Request(
        "https://alerts.example.test/astra",
        data=b"{}",
        method="POST",
    )
    response = alert_delivery._open_webhook_request(request, timeout=9)

    assert isinstance(captured["handler"], alert_delivery._NoRedirectHandler)
    assert captured["handler"].redirect_request(request, None, 302, "Found", {}, "https://other.test") is None
    assert captured["request"] is request
    assert captured["timeout"] == 9
    assert response.status == 202


def test_external_alert_dispatch_is_disabled_by_default_and_supports_audited_manual_retry(client, monkeypatch):
    admin_token = _bootstrap_admin(client)
    headers = _auth_header(admin_token)
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    entries = [
        AdminAlertOutboxEntry(
            source_type="knowledge_snapshot_run_alert",
            source_id=701,
            source_key="delivery-success-secret-source-key",
            event_code="stale_running",
            severity="critical",
            action_hint="investigate",
            status="queued",
            dispatch_mode="manual_review",
            delivery_target="admin_outbox",
            external_delivery=False,
            dedupe_key="delivery-success-dedupe",
            payload_hash="1" * 64,
            payload_json={"secret": "must-not-leave-success", "scheduler_lease_token": "hidden-token"},
            first_seen_at=now,
            last_seen_at=now,
            seen_count=1,
        ),
        AdminAlertOutboxEntry(
            source_type="content_script_asset_scan_run_alert",
            source_id=702,
            source_key="delivery-retry-secret-source-key",
            event_code="remote_drift",
            severity="warning",
            action_hint="review",
            status="queued",
            dispatch_mode="manual_review",
            delivery_target="admin_outbox",
            external_delivery=False,
            dedupe_key="delivery-retry-dedupe",
            payload_hash="2" * 64,
            payload_json={"source_url": "https://secret.invalid/script.js", "content_bytes": "hidden-bytes"},
            first_seen_at=now,
            last_seen_at=now,
            seen_count=1,
        ),
    ]
    with session_factory() as db:
        db.add_all(entries)
        db.commit()
        entry_ids = [entry.id for entry in entries]

    plan_response = client.post(
        "/api/admin/alert-outbox/dispatch-plans",
        headers=headers,
        json={"entry_ids": entry_ids, "confirm_create_plan": True},
    )
    assert plan_response.status_code == 200
    first_plan_id = plan_response.json()["id"]

    missing_confirmation = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers=headers,
        json={},
    )
    assert missing_confirmation.status_code == 422

    disabled = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers={**headers, "X-Request-ID": "external-delivery-disabled"},
        json={"confirm_external_dispatch": True},
    )
    assert disabled.status_code == 409
    disabled_body = disabled.json()["detail"]
    assert disabled_body["code"] == "external_delivery_disabled"
    assert disabled_body["posture"]["enabled"] is False
    assert disabled_body["posture"]["configured"] is False
    with session_factory() as db:
        assert db.get(AdminAlertOutboxDispatchPlan, first_plan_id).plan_status == "created"
        unchanged = list(
            db.scalars(select(AdminAlertOutboxEntry).where(AdminAlertOutboxEntry.id.in_(entry_ids))).all()
        )
        assert {entry.status for entry in unchanged} == {"queued"}
        assert {entry.attempt_count for entry in unchanged} == {0}
        assert all(not entry.external_delivery for entry in unchanged)

    settings = get_settings()
    settings.alert_delivery_enabled = True
    settings.alert_delivery_webhook_url = "https://alerts.example.test/astra"
    settings.alert_delivery_webhook_token = SecretStr("external-delivery-test-token")
    fake_adapter = _FakeWebhookAdapter({entry_ids[1]})
    monkeypatch.setattr(admin_endpoint, "build_alert_delivery_adapter", lambda _: fake_adapter)

    original_validation = admin_endpoint._admin_alert_outbox_dispatch_plan_validation_report

    def race_after_validation(plan, db, generated_at):
        report = original_validation(plan, db, generated_at)
        raced_entry = db.get(AdminAlertOutboxEntry, entry_ids[0])
        raced_entry.status = "planned"
        db.commit()
        return report

    monkeypatch.setattr(admin_endpoint, "_admin_alert_outbox_dispatch_plan_validation_report", race_after_validation)
    raced = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers=headers,
        json={"confirm_external_dispatch": True},
    )
    assert raced.status_code == 409
    assert raced.json()["detail"] == "Alert outbox dispatch plan changed while claiming entries"
    assert fake_adapter.calls == []
    restore_raced_entry = client.patch(
        f"/api/admin/alert-outbox/{entry_ids[0]}",
        headers=headers,
        json={"status": "queued", "confirm_manual_review": True},
    )
    assert restore_raced_entry.status_code == 200
    monkeypatch.setattr(
        admin_endpoint,
        "_admin_alert_outbox_dispatch_plan_validation_report",
        original_validation,
    )

    settings.alert_delivery_batch_limit = 1
    over_limit = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers=headers,
        json={"confirm_external_dispatch": True},
    )
    assert over_limit.status_code == 409
    assert over_limit.json()["detail"]["batch_limit"] == 1
    assert fake_adapter.calls == []
    settings.alert_delivery_batch_limit = 10

    dispatched = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers={**headers, "X-Request-ID": "external-delivery-partial"},
        json={"confirm_external_dispatch": True},
    )
    assert dispatched.status_code == 200
    first_report = dispatched.json()
    assert first_report["plan_status"] == "partial_failed"
    assert first_report["attempted_count"] == 2
    assert first_report["delivered_count"] == 1
    assert first_report["failed_count"] == 1
    assert first_report["policy"]["original_payload_included"] is False
    assert {item["status"] for item in first_report["items"]} == {"delivered", "failed"}
    response_text = json.dumps(first_report, ensure_ascii=False)
    for secret in ("must-not-leave", "hidden-token", "secret.invalid", "hidden-bytes", "external-delivery-test-token"):
        assert secret not in response_text

    captured_text = json.dumps([call[0] for call in fake_adapter.calls], ensure_ascii=False)
    assert "payload_json" not in captured_text
    assert "source_key_sha256" in captured_text
    assert "delivery-success-secret-source-key" not in captured_text
    assert "delivery-retry-secret-source-key" not in captured_text
    assert "must-not-leave" not in captured_text
    assert "secret.invalid" not in captured_text
    assert all(len(idempotency_key) == 64 for _, idempotency_key in fake_adapter.calls)
    retry_idempotency_key = next(
        key for envelope, key in fake_adapter.calls if envelope["entry_id"] == entry_ids[1]
    )

    repeated_plan = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{first_plan_id}/dispatch",
        headers=headers,
        json={"confirm_external_dispatch": True},
    )
    assert repeated_plan.status_code == 409
    assert len(fake_adapter.calls) == 2

    manual_requeue = client.patch(
        f"/api/admin/alert-outbox/{entry_ids[1]}",
        headers=headers,
        json={"status": "queued", "note": "manual retry", "confirm_manual_review": True},
    )
    assert manual_requeue.status_code == 200
    assert manual_requeue.json()["status"] == "queued"
    assert manual_requeue.json()["dispatch_mode"] == "manual_review"
    assert manual_requeue.json()["delivery_target"] == "admin_outbox"
    assert manual_requeue.json()["external_delivery"] is False
    assert manual_requeue.json()["attempt_count"] == 1

    retry_plan = client.post(
        "/api/admin/alert-outbox/dispatch-plans",
        headers=headers,
        json={"entry_ids": [entry_ids[1]], "confirm_create_plan": True},
    )
    assert retry_plan.status_code == 200
    fake_adapter.fail_entry_ids.clear()
    retried = client.post(
        f"/api/admin/alert-outbox/dispatch-plans/{retry_plan.json()['id']}/dispatch",
        headers={**headers, "X-Request-ID": "external-delivery-retry"},
        json={"confirm_external_dispatch": True},
    )
    assert retried.status_code == 200
    assert retried.json()["plan_status"] == "delivered"
    assert retried.json()["items"][0]["attempt_count"] == 2
    assert len(fake_adapter.calls) == 3
    assert fake_adapter.calls[-1][1] == retry_idempotency_key

    queue = client.get("/api/admin/alert-outbox/queue", headers=headers)
    assert queue.status_code == 200
    assert queue.json()["delivered_count"] == 2
    assert queue.json()["failed_count"] == 0
    assert queue.json()["dispatching_count"] == 0
    assert queue.json()["terminal_count"] == 2
    assert queue.json()["policy"]["delivery_posture"]["enabled"] is True
    assert queue.json()["policy"]["delivery_posture"]["configured"] is True

    audits = client.get(
        "/api/admin/audit-logs?action=admin.alert_outbox.external_dispatch",
        headers=headers,
    )
    assert audits.status_code == 200
    assert audits.json()["total"] == 3
    audit_text = json.dumps(audits.json(), ensure_ascii=False)
    for secret in ("must-not-leave", "hidden-token", "secret.invalid", "hidden-bytes", "external-delivery-test-token"):
        assert secret not in audit_text
