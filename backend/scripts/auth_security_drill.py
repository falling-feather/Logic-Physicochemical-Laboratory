from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.core.config import get_settings


DEFAULT_AUDIT_IP_HASH_SALT = "astra-dev-audit-salt"
PLACEHOLDER_BOOTSTRAP_TOKENS = {
    "admin",
    "astra",
    "bootstrap",
    "changeme",
    "password",
    "secret",
    "test",
}


def run_auth_security_drill(
    *,
    settings: Any | None = None,
    require_production: bool = False,
    require_admin_bootstrap_token: bool = False,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    production_like = _is_production_like(resolved_settings.environment)
    environment = _environment_report(
        resolved_settings.environment,
        require_production=require_production,
        production_like=production_like,
    )
    admin_bootstrap = _admin_bootstrap_report(
        resolved_settings.admin_bootstrap_token,
        production_like=production_like,
        require_admin_bootstrap_token=require_admin_bootstrap_token,
    )
    session_cookie = _session_cookie_report(
        cookie_name=resolved_settings.session_cookie_name,
        session_days=resolved_settings.session_days,
        last_seen_update_seconds=resolved_settings.session_last_seen_update_seconds,
        production_like=production_like,
    )
    password_reset = _password_reset_report(
        token_ttl_seconds=resolved_settings.password_reset_token_ttl_seconds,
        cooldown_seconds=resolved_settings.password_reset_request_cooldown_seconds,
        retention_days=resolved_settings.password_reset_token_retention_days,
        return_token_for_dev=resolved_settings.password_reset_return_token_for_dev,
        production_like=production_like,
    )
    login_lockout = _login_lockout_report(
        max_attempts=resolved_settings.login_max_attempts,
        lockout_seconds=resolved_settings.login_lockout_seconds,
        window_seconds=resolved_settings.login_attempt_window_seconds,
    )
    audit_redaction = _audit_redaction_report(
        audit_ip_hash_salt=resolved_settings.audit_ip_hash_salt,
        production_like=production_like,
    )
    cleanup_operations = _cleanup_operations_report()
    sections = {
        "environment": environment,
        "admin_bootstrap": admin_bootstrap,
        "session_cookie": session_cookie,
        "password_reset": password_reset,
        "login_lockout": login_lockout,
        "audit_redaction": audit_redaction,
        "cleanup_operations": cleanup_operations,
    }
    return {
        "ok": all(bool(section["ok"]) for section in sections.values()),
        "sensitive_fields_returned": False,
        **sections,
    }


def _environment_report(environment: str, *, require_production: bool, production_like: bool) -> dict[str, Any]:
    ok = (not require_production) or production_like
    return {
        "ok": ok,
        "environment": environment,
        "production_like": production_like,
        "require_production": require_production,
        "status": "ready" if ok else "not_production",
    }


def _admin_bootstrap_report(
    admin_bootstrap_token: str | None,
    *,
    production_like: bool,
    require_admin_bootstrap_token: bool,
) -> dict[str, Any]:
    token_configured = bool(admin_bootstrap_token)
    weak_or_placeholder = _bootstrap_token_looks_weak(admin_bootstrap_token)
    required = production_like or require_admin_bootstrap_token
    ok = (not required or token_configured) and (not token_configured or not weak_or_placeholder)
    return {
        "ok": ok,
        "status": "ready" if ok else "needs_rotation_or_configuration",
        "token_configured": token_configured,
        "token_value_returned": False,
        "token_looks_weak_or_placeholder": weak_or_placeholder,
        "required": required,
        "policy": "production bootstrap requires one-time ASTRA_ADMIN_BOOTSTRAP_TOKEN and must not use placeholders",
    }


def _session_cookie_report(
    *,
    cookie_name: str,
    session_days: int,
    last_seen_update_seconds: int,
    production_like: bool,
) -> dict[str, Any]:
    cookie_name_ok = bool(cookie_name.strip())
    session_days_ok = 1 <= session_days <= 30
    last_seen_ok = last_seen_update_seconds >= 0
    ok = cookie_name_ok and session_days_ok and last_seen_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "invalid_policy",
        "cookie_name_configured": cookie_name_ok,
        "cookie_secure_expected": production_like,
        "cookie_samesite": "lax",
        "cookie_http_only": True,
        "session_days": session_days,
        "session_days_ok": session_days_ok,
        "last_seen_update_seconds": last_seen_update_seconds,
        "last_seen_update_seconds_ok": last_seen_ok,
        "frontend_local_storage_allowed": False,
        "storage_policy": "use HttpOnly cookie for browser session continuity; do not persist bearer tokens in localStorage",
    }


def _password_reset_report(
    *,
    token_ttl_seconds: int,
    cooldown_seconds: int,
    retention_days: int,
    return_token_for_dev: bool,
    production_like: bool,
) -> dict[str, Any]:
    ttl_ok = 60 <= token_ttl_seconds <= 3600
    cooldown_ok = cooldown_seconds >= 0
    retention_ok = retention_days >= 1
    dev_return_ok = (not production_like) or (not return_token_for_dev)
    ok = ttl_ok and cooldown_ok and retention_ok and dev_return_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "unsafe_policy",
        "token_ttl_seconds": token_ttl_seconds,
        "token_ttl_seconds_ok": ttl_ok,
        "request_cooldown_seconds": cooldown_seconds,
        "request_cooldown_seconds_ok": cooldown_ok,
        "token_retention_days": retention_days,
        "token_retention_days_ok": retention_ok,
        "return_token_for_dev": return_token_for_dev,
        "return_token_blocked_in_production": dev_return_ok,
        "token_replay_policy": "row-lock token lookup, one-time used_at consumption, session revoke after success",
    }


def _login_lockout_report(*, max_attempts: int, lockout_seconds: int, window_seconds: int) -> dict[str, Any]:
    max_attempts_ok = 1 <= max_attempts <= 20
    lockout_ok = lockout_seconds > 0
    window_ok = window_seconds > 0
    ok = max_attempts_ok and lockout_ok and window_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "invalid_policy",
        "max_attempts": max_attempts,
        "max_attempts_ok": max_attempts_ok,
        "lockout_seconds": lockout_seconds,
        "lockout_seconds_ok": lockout_ok,
        "attempt_window_seconds": window_seconds,
        "attempt_window_seconds_ok": window_ok,
    }


def _audit_redaction_report(*, audit_ip_hash_salt: str, production_like: bool) -> dict[str, Any]:
    salt_configured = bool(audit_ip_hash_salt.strip())
    default_salt = audit_ip_hash_salt == DEFAULT_AUDIT_IP_HASH_SALT
    salt_ok = salt_configured and ((not production_like) or (not default_salt))
    return {
        "ok": salt_ok,
        "status": "ready" if salt_ok else "needs_secret_rotation",
        "audit_ip_hash_salt_configured": salt_configured,
        "audit_ip_hash_salt_is_default": default_salt,
        "sensitive_fields_returned": False,
        "redacted_fields": [
            "password",
            "password_hash",
            "session_token",
            "token_hash",
            "reset_token",
            "bootstrap_token",
            "requested_ip_hash",
            "user_agent",
        ],
    }


def _cleanup_operations_report() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "ready",
        "password_reset_token_cleanup": "python -m scripts.cleanup_password_reset_tokens --apply",
        "expired_auth_session_cleanup": "python -m scripts.cleanup_auth_sessions --apply",
        "default_mode": "dry_run",
        "external_delivery": "P4_LOWEST_PRIORITY_DEFERRED",
    }


def _bootstrap_token_looks_weak(token: str | None) -> bool:
    if not token:
        return False
    stripped = token.strip()
    normalized = stripped.lower()
    if len(stripped) < 32:
        return True
    return normalized in PLACEHOLDER_BOOTSTRAP_TOKENS or "changeme" in normalized or "placeholder" in normalized


def _is_production_like(environment: str) -> bool:
    return environment.strip().lower() in {"production", "prod"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report authentication/session production-readiness posture.")
    parser.add_argument("--require-production", action="store_true", help="Fail unless ASTRA_ENVIRONMENT is production/prod.")
    parser.add_argument(
        "--require-admin-bootstrap-token",
        action="store_true",
        help="Fail unless ASTRA_ADMIN_BOOTSTRAP_TOKEN is configured and non-placeholder.",
    )
    args = parser.parse_args(argv)
    report = run_auth_security_drill(
        require_production=args.require_production,
        require_admin_bootstrap_token=args.require_admin_bootstrap_token,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
