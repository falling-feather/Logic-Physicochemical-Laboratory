from types import SimpleNamespace

from scripts.auth_security_drill import run_auth_security_drill


def test_auth_security_drill_reports_ready_production_posture_without_secret_values():
    report = run_auth_security_drill(settings=_settings())

    assert report["ok"] is True
    assert report["environment"]["production_like"] is True
    assert report["admin_bootstrap"]["token_configured"] is True
    assert report["admin_bootstrap"]["token_value_returned"] is False
    assert report["session_cookie"]["cookie_secure_expected"] is True
    assert report["session_cookie"]["cookie_http_only"] is True
    assert report["session_cookie"]["frontend_local_storage_allowed"] is False
    assert report["password_reset"]["return_token_blocked_in_production"] is True
    assert report["audit_redaction"]["audit_ip_hash_salt_is_default"] is False
    assert report["audit_redaction"]["audit_trust_forwarded_for"] is True
    assert report["audit_redaction"]["audit_trusted_proxy_hosts_configured"] is True
    assert report["sensitive_fields_returned"] is False
    report_text = str(report)
    assert _settings().admin_bootstrap_token not in report_text
    assert "audit-prod-salt" not in report_text


def test_auth_security_drill_flags_unsafe_production_token_and_reset_settings():
    report = run_auth_security_drill(
        settings=_settings(
            admin_bootstrap_token="short",
            password_reset_return_token_for_dev=True,
            audit_ip_hash_salt="astra-dev-audit-salt",
        )
    )

    assert report["ok"] is False
    assert report["admin_bootstrap"]["ok"] is False
    assert report["admin_bootstrap"]["token_looks_weak_or_placeholder"] is True
    assert report["password_reset"]["return_token_blocked_in_production"] is False
    assert report["audit_redaction"]["audit_ip_hash_salt_is_default"] is True


def test_auth_security_drill_flags_forwarded_for_without_trusted_proxy_hosts():
    report = run_auth_security_drill(
        settings=_settings(
            audit_trust_forwarded_for=True,
            audit_trusted_proxy_hosts="",
        )
    )

    assert report["ok"] is False
    assert report["audit_redaction"]["ok"] is False
    assert report["audit_redaction"]["status"] == "unsafe_forwarded_for"
    assert report["audit_redaction"]["audit_trust_forwarded_for"] is True
    assert report["audit_redaction"]["audit_trusted_proxy_hosts_configured"] is False


def test_auth_security_drill_can_require_production_and_bootstrap_token():
    dev_report = run_auth_security_drill(
        settings=_settings(environment="development", admin_bootstrap_token=None),
        require_production=True,
        require_admin_bootstrap_token=True,
    )

    assert dev_report["ok"] is False
    assert dev_report["environment"]["status"] == "not_production"
    assert dev_report["admin_bootstrap"]["required"] is True
    assert dev_report["admin_bootstrap"]["token_configured"] is False


def test_auth_security_drill_allows_nonproduction_without_bootstrap_token():
    report = run_auth_security_drill(settings=_settings(environment="development", admin_bootstrap_token=None))

    assert report["ok"] is True
    assert report["environment"]["production_like"] is False
    assert report["admin_bootstrap"]["required"] is False
    assert report["cleanup_operations"]["default_mode"] == "dry_run"


def _settings(**overrides):
    values = {
        "environment": "production",
        "admin_bootstrap_token": "prod-bootstrap-token-123456789012345678901234567890",
        "session_cookie_name": "astra_session",
        "session_days": 7,
        "session_last_seen_update_seconds": 300,
        "password_reset_token_ttl_seconds": 1800,
        "password_reset_request_cooldown_seconds": 300,
        "password_reset_token_retention_days": 30,
        "password_reset_return_token_for_dev": False,
        "login_max_attempts": 5,
        "login_lockout_seconds": 900,
        "login_attempt_window_seconds": 900,
        "audit_ip_hash_salt": "audit-prod-salt-12345678901234567890",
        "audit_trust_forwarded_for": True,
        "audit_trusted_proxy_hosts": "127.0.0.1,10.0.0.10",
    }
    values.update(overrides)
    return SimpleNamespace(**values)
