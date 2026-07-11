import json
from datetime import UTC, datetime

from pydantic import SecretStr

from app.core.config import Settings
from app.services.rc_external_scope import build_rc_external_scope_report
from scripts import rc_external_scope_gate


def test_first_rc_with_no_external_channels_is_ready_and_side_effect_free():
    report = build_rc_external_scope_report(
        Settings(_env_file=None),
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
        generated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["phase"] == "V6.6.63"
    assert report["scope_frozen"] is True
    assert report["first_rc_external_channels"] == []
    assert report["unselected_external_channels"] == [
        "alert_webhook",
        "github_issue_sync",
        "audit_anchor",
    ]
    assert all(item["status"] == "passed" for item in report["channels"].values())
    assert all(item["release_outbound_allowed"] is False for item in report["channels"].values())
    assert report["network_requests_performed"] == 0
    assert report["side_effects_performed"] == []
    assert report["no_outbound_side_effects_expected"] is True
    assert report["sensitive_fields_returned"] is False
    assert report["sensitive_values_returned"] is False


def test_unselected_enabled_channel_blocks_scope_drift_without_leaking_configuration():
    secret_url = "https://alerts.example.invalid/private-hook"
    secret_token = "alert-token-must-not-leak"
    settings = Settings(
        _env_file=None,
        alert_delivery_enabled=True,
        alert_delivery_webhook_url=secret_url,
        alert_delivery_webhook_token=SecretStr(secret_token),
    )

    report = build_rc_external_scope_report(
        settings,
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
    )
    serialized = json.dumps(report)

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert report["channels"]["alert_webhook"]["reason"] == "unselected_channel_enabled"
    assert secret_url not in serialized
    assert secret_token not in serialized


def test_selected_channel_requires_real_staging_readback_confirmation():
    settings = _configured_github_settings()

    report = build_rc_external_scope_report(
        settings,
        selected_channels=("github_issue_sync",),
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
    )

    assert report["ok"] is False
    assert report["status"] == "missing_evidence"
    assert report["channels"]["github_issue_sync"]["reason"] == "staging_readback_not_confirmed"
    assert report["channels"]["github_issue_sync"]["release_outbound_allowed"] is False


def test_selected_configured_channel_passes_with_staging_readback_without_leaking_secrets():
    settings = _configured_github_settings()

    report = build_rc_external_scope_report(
        settings,
        selected_channels=("github_issue_sync",),
        staging_readback_confirmations=("github_issue_sync",),
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
    )
    serialized = json.dumps(report)

    assert report["ok"] is True
    assert report["channels"]["github_issue_sync"]["release_outbound_allowed"] is True
    assert report["no_outbound_side_effects_expected"] is False
    assert "private-owner" not in serialized
    assert "private-repo" not in serialized
    assert "github-token-must-not-leak" not in serialized


def test_readback_for_unselected_channel_is_rejected_as_scope_mismatch():
    report = build_rc_external_scope_report(
        Settings(_env_file=None),
        staging_readback_confirmations=("audit_anchor",),
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
    )

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert report["blockers"][-1]["reason"] == "readback_confirmed_for_unselected_channel"


def test_rc_external_scope_cli_returns_json_for_invalid_now(capsys):
    exit_code = rc_external_scope_gate.main(["--now", "not-a-date"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["ok"] is False
    assert output["status"] == "invalid_argument"
    assert output["sensitive_values_returned"] is False


def _configured_github_settings() -> Settings:
    return Settings(
        _env_file=None,
        external_issue_sync_enabled=True,
        external_issue_sync_github_owner="private-owner",
        external_issue_sync_github_repo="private-repo",
        external_issue_sync_github_token=SecretStr("github-token-must-not-leak"),
    )
