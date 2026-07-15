import json
from datetime import UTC, datetime

from pydantic import SecretStr
from sqlalchemy import select

from app.api.endpoints import admin_governance as admin_endpoint
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog, BugExternalSyncOperation, BugRecord
from app.services import external_issue_providers
from app.services.external_issue_providers import (
    ExternalCommentReceipt,
    ExternalIssueReceipt,
    IssueProviderError,
)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Cookie": ""}


def _bootstrap_admin(client) -> str:
    created = client.post(
        "/api/admin/bootstrap",
        json={"username": "issue_sync_admin", "password": "secret123", "display_name": "Issue Sync Admin"},
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "issue_sync_admin", "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_bug(client, token: str, *, title: str = "External synchronization regression") -> dict:
    response = client.post(
        "/api/admin/bugs",
        headers=_auth_header(token),
        json={
            "title": title,
            "category": "BE",
            "severity": "P1",
            "evidence": "private evidence must stay local",
            "notes": "private notes must stay local",
            "source": "internal/path/that/must/stay/local",
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure_issue_sync() -> None:
    settings = get_settings()
    settings.external_issue_sync_enabled = True
    settings.external_issue_sync_github_owner = "example"
    settings.external_issue_sync_github_repo = "astra"
    settings.external_issue_sync_github_token = SecretStr("github-test-token")


class _FakeIssueAdapter:
    provider = "github"

    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str]] = []
        self.status_calls: list[tuple[str, str]] = []
        self.comment_calls: list[tuple[str, str]] = []

    def create_issue(self, *, title: str, body: str) -> ExternalIssueReceipt:
        self.create_calls.append((title, body))
        return ExternalIssueReceipt(
            provider="github",
            issue_id="42",
            issue_url="https://github.com/example/astra/issues/42",
            state="open",
            updated_at=datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
            response_hash="a" * 64,
        )

    def update_issue_state(self, issue_id: str, *, state: str) -> ExternalIssueReceipt:
        self.status_calls.append((issue_id, state))
        return ExternalIssueReceipt(
            provider="github",
            issue_id=issue_id,
            issue_url=f"https://github.com/example/astra/issues/{issue_id}",
            state=state,
            updated_at=datetime(2026, 7, 10, 10, 5, tzinfo=UTC),
            response_hash="b" * 64,
        )

    def create_comment(self, issue_id: str, *, body: str) -> ExternalCommentReceipt:
        self.comment_calls.append((issue_id, body))
        return ExternalCommentReceipt(
            provider="github",
            comment_id="9001",
            comment_url=f"https://github.com/example/astra/issues/{issue_id}#issuecomment-9001",
            response_hash="c" * 64,
        )


class _AmbiguousCreateAdapter(_FakeIssueAdapter):
    def create_issue(self, *, title: str, body: str) -> ExternalIssueReceipt:
        self.create_calls.append((title, body))
        raise IssueProviderError("provider_network_error", retryable=True, ambiguous=True)


class _WrongStateReceiptAdapter(_FakeIssueAdapter):
    def update_issue_state(self, issue_id: str, *, state: str) -> ExternalIssueReceipt:
        self.status_calls.append((issue_id, state))
        return ExternalIssueReceipt(
            provider="github",
            issue_id=issue_id,
            issue_url=f"https://github.com/example/astra/issues/{issue_id}",
            state="open" if state == "closed" else "closed",
            updated_at=datetime(2026, 7, 10, 10, 6, tzinfo=UTC),
            response_hash="d" * 64,
        )


class _FakeGitHubResponse:
    status = 201

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int) -> bytes:
        assert limit == 64 * 1024
        return json.dumps(self.payload).encode("utf-8")


def test_external_issue_sync_is_disabled_by_default_and_records_safe_failure(client):
    token = _bootstrap_admin(client)
    bug = _create_bug(client, token)
    missing_confirmation = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={},
    )
    assert missing_confirmation.status_code == 422

    blocked = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers={**_auth_header(token), "X-Request-ID": "issue-sync-disabled"},
        json={"confirm_external_sync": True},
    )
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "external_issue_sync_disabled"
    assert detail["retryable"] is False
    assert detail["ambiguous"] is False
    assert detail["posture"]["enabled"] is False
    assert "token" not in json.dumps(detail).lower()

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored_bug = db.get(BugRecord, bug["id"])
        operation = db.scalar(select(BugExternalSyncOperation))
        audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "admin.bug.external_sync.create")
        )
        assert stored_bug.status == "open"
        assert stored_bug.external_issue_id is None
        assert operation.status == "failed"
        assert operation.last_error_code == "external_issue_sync_disabled"
        assert operation.attempt_count == 1
        assert audit.event_result == "failure"
        assert audit.failure_reason == "external_issue_sync_disabled"


def test_bug_external_issue_create_status_and_comment_sync_are_idempotent_and_redacted(client, monkeypatch):
    token = _bootstrap_admin(client)
    bug = _create_bug(client, token)
    _configure_issue_sync()
    adapter = _FakeIssueAdapter()
    monkeypatch.setattr(admin_endpoint, "build_issue_provider_adapter", lambda _: adapter)

    created = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["bug"]["external_issue_provider"] == "github"
    assert created_body["bug"]["external_issue_id"] == "42"
    assert created_body["bug"]["external_issue_state"] == "open"
    assert created_body["operation"]["status"] == "succeeded"
    assert created_body["operation"]["operation_key_redacted"] is True
    assert len(adapter.create_calls) == 1
    external_text = "\n".join(adapter.create_calls[0])
    assert "private evidence" not in external_text
    assert "private notes" not in external_text
    assert "internal/path" not in external_text
    assert "github-test-token" not in external_text

    duplicate_create = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert duplicate_create.status_code == 409
    assert duplicate_create.json()["detail"]["code"] == "external_issue_already_bound"
    assert len(adapter.create_calls) == 1

    local_closed = client.patch(
        f"/api/admin/bugs/{bug['id']}",
        headers=_auth_header(token),
        json={"status": "closed"},
    )
    assert local_closed.status_code == 200
    assert local_closed.json()["external_sync_revision"] == 2
    status_sync = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/status",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert status_sync.status_code == 200
    assert status_sync.json()["bug"]["status"] == "closed"
    assert status_sync.json()["bug"]["external_issue_state"] == "closed"
    assert adapter.status_calls == [("42", "closed")]
    repeated_status = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/status",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert repeated_status.status_code == 200
    assert repeated_status.json()["recovered"] is True
    assert adapter.status_calls == [("42", "closed")]

    rebound = client.patch(
        f"/api/admin/bugs/{bug['id']}",
        headers=_auth_header(token),
        json={
            "external_issue_provider": "github",
            "external_issue_id": "43",
            "external_issue_url": "https://github.com/example/astra/issues/43",
        },
    )
    assert rebound.status_code == 200
    assert rebound.json()["external_sync_revision"] == 3
    rebound_status = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/status",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert rebound_status.status_code == 200
    assert rebound_status.json()["recovered"] is False
    assert adapter.status_calls == [("42", "closed"), ("43", "closed")]

    comment_text = "Regression is fixed in the local validation suite."
    comment_sync = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/comments",
        headers=_auth_header(token),
        json={"confirm_external_sync": True, "comment": comment_text},
    )
    assert comment_sync.status_code == 200
    assert comment_sync.json()["operation"]["external_comment_id"] == "9001"
    repeated_comment = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/comments",
        headers=_auth_header(token),
        json={"confirm_external_sync": True, "comment": comment_text},
    )
    assert repeated_comment.status_code == 200
    assert repeated_comment.json()["recovered"] is True
    assert len(adapter.comment_calls) == 1

    sensitive = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/comments",
        headers=_auth_header(token),
        json={"confirm_external_sync": True, "comment": "Authorization: Bearer should-not-leave"},
    )
    assert sensitive.status_code == 422
    assert sensitive.json()["detail"]["code"] == "external_issue_comment_sensitive"
    assert len(adapter.comment_calls) == 1

    operations = client.get(
        f"/api/admin/bugs/{bug['id']}/external-sync-operations",
        headers=_auth_header(token),
    )
    assert operations.status_code == 200
    assert operations.json()["total"] == 4
    response_text = operations.text
    assert comment_text not in response_text
    assert "private evidence" not in response_text
    assert "private notes" not in response_text
    assert "github-test-token" not in response_text

    audits = client.get(
        f"/api/admin/audit-logs?resource_type=bug_record&resource_id={bug['id']}&limit=50",
        headers=_auth_header(token),
    )
    assert audits.status_code == 200
    audit_text = audits.text
    assert comment_text not in audit_text
    assert "should-not-leave" not in audit_text
    assert "private evidence" not in audit_text


def test_ambiguous_issue_creation_never_blindly_retries_or_mutates_local_bug(client, monkeypatch):
    token = _bootstrap_admin(client)
    bug = _create_bug(client, token, title="Ambiguous provider response")
    _configure_issue_sync()
    adapter = _AmbiguousCreateAdapter()
    monkeypatch.setattr(admin_endpoint, "build_issue_provider_adapter", lambda _: adapter)

    first = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert first.status_code == 409
    assert first.json()["detail"]["code"] == "provider_network_error"
    assert first.json()["detail"]["ambiguous"] is True
    second = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "external_issue_sync_ambiguous"
    assert len(adapter.create_calls) == 1

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored_bug = db.get(BugRecord, bug["id"])
        operation = db.scalar(select(BugExternalSyncOperation))
        assert stored_bug.title == "Ambiguous provider response"
        assert stored_bug.status == "open"
        assert stored_bug.external_issue_id is None
        assert operation.status == "ambiguous"
        assert operation.attempt_count == 1
        assert operation.last_error_code == "provider_network_error"


def test_issue_status_sync_rejects_opposite_provider_receipt_state(client, monkeypatch):
    token = _bootstrap_admin(client)
    bug = _create_bug(client, token, title="Receipt state mismatch")
    _configure_issue_sync()
    initial_adapter = _FakeIssueAdapter()
    monkeypatch.setattr(admin_endpoint, "build_issue_provider_adapter", lambda _: initial_adapter)
    created = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/create",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert created.status_code == 200
    closed = client.patch(
        f"/api/admin/bugs/{bug['id']}",
        headers=_auth_header(token),
        json={"status": "closed"},
    )
    assert closed.status_code == 200

    wrong_state_adapter = _WrongStateReceiptAdapter()
    monkeypatch.setattr(admin_endpoint, "build_issue_provider_adapter", lambda _: wrong_state_adapter)
    synced = client.post(
        f"/api/admin/bugs/{bug['id']}/external-sync/status",
        headers=_auth_header(token),
        json={"confirm_external_sync": True},
    )
    assert synced.status_code == 409
    assert synced.json()["detail"]["code"] == "external_issue_response_state_mismatch"
    assert synced.json()["detail"]["ambiguous"] is True

    with get_session_factory(get_settings().database_url)() as db:
        stored_bug = db.get(BugRecord, bug["id"])
        operation = db.scalar(
            select(BugExternalSyncOperation)
            .where(BugExternalSyncOperation.operation == "status")
            .order_by(BugExternalSyncOperation.id.desc())
        )
        assert stored_bug.external_issue_state == "open"
        assert operation.status == "ambiguous"
        assert operation.last_error_code == "external_issue_response_state_mismatch"


def test_github_provider_uses_versioned_authenticated_contract_without_local_sensitive_fields(monkeypatch):
    captured = {}

    def fake_open(request, timeout, allowed_origin):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["allowed_origin"] = allowed_origin
        return _FakeGitHubResponse(
            {
                "number": 42,
                "html_url": "https://github.com/example/astra/issues/42",
                "state": "open",
                "updated_at": "2026-07-10T10:00:00Z",
            }
        )

    monkeypatch.setattr(external_issue_providers, "_open_github_request", fake_open)
    adapter = external_issue_providers.GitHubIssueProviderAdapter(
        api_url="https://api.github.com",
        web_url="https://github.com",
        owner="example",
        repo="astra",
        token="provider-secret-token",
        api_version="2026-03-10",
        timeout_seconds=8,
    )
    receipt = adapter.create_issue(title="[P1] Contract", body="Safe body")
    assert receipt.issue_id == "42"
    assert receipt.issue_url == "https://github.com/example/astra/issues/42"
    request = captured["request"]
    assert request.full_url == "https://api.github.com/repos/example/astra/issues"
    assert request.get_header("Authorization") == "Bearer provider-secret-token"
    assert request.get_header("X-github-api-version") == "2026-03-10"
    assert captured["timeout"] == 8
    assert captured["allowed_origin"] == "https://api.github.com/"
    assert json.loads(request.data) == {"title": "[P1] Contract", "body": "Safe body"}
    assert b"provider-secret-token" not in request.data

    assert external_issue_providers._safe_repository_issue_url(
        "https://github.com/example/astra/issues/42",
        base_url="https://github.com",
        owner="example",
        repo="astra",
        issue_id="42",
    )
    assert not external_issue_providers._safe_repository_issue_url(
        "https://github.com/example/astra/issues/42?token=unsafe",
        base_url="https://github.com",
        owner="example",
        repo="astra",
        issue_id="42",
    )
