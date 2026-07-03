from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog, AuthSession, LoginAttempt


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_logout(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "teacher01",
            "password": "secret123",
            "display_name": "Teacher One",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    assert register.json()["role"] == "teacher"

    login = client.post(
        "/api/auth/login",
        json={"username": "teacher01", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/users/me", headers=_auth_header(token))
    assert me.status_code == 200
    assert me.json()["username"] == "teacher01"

    logout = client.post("/api/auth/logout", headers=_auth_header(token))
    assert logout.status_code == 200

    after_logout = client.get("/api/users/me", headers=_auth_header(token))
    assert after_logout.status_code == 401


def test_auth_events_record_audit_metadata(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "audit_teacher",
            "password": "secret123",
            "display_name": "Audit Teacher",
            "role": "teacher",
        },
    )
    assert register.status_code == 201

    login = client.post(
        "/api/auth/login",
        headers={
            "X-Request-ID": "auth-login-request",
            "X-Forwarded-For": "203.0.113.10, 10.0.0.1",
            "User-Agent": "pytest-auth-agent",
        },
        json={"username": "audit_teacher", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.headers["X-Request-ID"] == "auth-login-request"
    token = login.json()["access_token"]

    logout = client.post(
        "/api/auth/logout",
        headers={**_auth_header(token), "X-Request-ID": "auth-logout-request"},
    )
    assert logout.status_code == 200

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        login_audit = db.scalar(select(AuditLog).where(AuditLog.action == "auth.login.success"))
        assert login_audit is not None
        assert login_audit.actor_role == "teacher"
        assert login_audit.event_result == "success"
        assert login_audit.request_id == "auth-login-request"
        assert login_audit.client_ip_hash is not None
        assert "203.0.113.10" not in login_audit.client_ip_hash
        assert len(login_audit.client_ip_hash) == 64
        assert login_audit.user_agent == "pytest-auth-agent"
        assert login_audit.request_method == "POST"
        assert login_audit.request_path == "/api/auth/login"
        assert "password" not in login_audit.snapshot_json
        assert "access_token" not in login_audit.snapshot_json

        logout_audit = db.scalar(select(AuditLog).where(AuditLog.action == "auth.logout"))
        assert logout_audit is not None
        assert logout_audit.event_result == "success"
        assert logout_audit.request_id == "auth-logout-request"
        assert logout_audit.snapshot_json["revoked_sessions"] >= 1


def test_public_register_rejects_admin_role(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "admin01",
            "password": "secret123",
            "display_name": "Admin One",
            "role": "admin",
        },
    )

    assert response.status_code == 422


def test_register_rejects_weak_password(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "weak_teacher",
            "password": "12345678",
            "display_name": "Weak Teacher",
            "role": "teacher",
        },
    )

    assert response.status_code == 422
    assert "Password must include at least one letter" in response.json()["detail"]["password"]


def test_register_rejects_blank_username_after_trimming(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "   ",
            "password": "secret123",
            "display_name": "Blank Username",
            "role": "teacher",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Username is required"


def test_login_rate_limit_locks_and_recovers_after_window(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "rate_teacher",
            "password": "secret123",
            "display_name": "Rate Teacher",
            "role": "teacher",
        },
    )
    assert register.status_code == 201

    max_attempts = get_settings().login_max_attempts
    for _ in range(max_attempts - 1):
        response = client.post("/api/auth/login", json={"username": "rate_teacher", "password": "wrong-secret"})
        assert response.status_code == 401

    locked = client.post("/api/auth/login", json={"username": "rate_teacher", "password": "wrong-secret"})
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0

    correct_while_locked = client.post("/api/auth/login", json={"username": "rate_teacher", "password": "secret123"})
    assert correct_while_locked.status_code == 429

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.username == "rate_teacher"))
        assert attempt is not None
        attempt.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    recovered = client.post("/api/auth/login", json={"username": "rate_teacher", "password": "secret123"})
    assert recovered.status_code == 200

    with session_factory() as db:
        attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.username == "rate_teacher"))
        assert attempt is not None
        assert attempt.failure_count == 0
        assert attempt.locked_until is None
        assert attempt.last_failed_at is None
        failed_audits = db.scalars(
            select(AuditLog).where(AuditLog.action == "auth.login.failed").order_by(AuditLog.id)
        ).all()
        locked_audits = db.scalars(
            select(AuditLog).where(AuditLog.action == "auth.login.locked").order_by(AuditLog.id)
        ).all()
        assert len(failed_audits) == max_attempts - 1
        assert all(audit.event_result == "failure" for audit in failed_audits)
        assert all(audit.failure_reason == "invalid_credentials" for audit in failed_audits)
        assert len(locked_audits) == 2
        assert all(audit.event_result == "blocked" for audit in locked_audits)
        assert all(audit.failure_reason == "account_locked" for audit in locked_audits)


def test_login_revokes_expired_sessions(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "session_teacher",
            "password": "secret123",
            "display_name": "Session Teacher",
            "role": "teacher",
        },
    )
    assert register.status_code == 201

    first_login = client.post("/api/auth/login", json={"username": "session_teacher", "password": "secret123"})
    assert first_login.status_code == 200

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    second_login = client.post("/api/auth/login", json={"username": "session_teacher", "password": "secret123"})
    assert second_login.status_code == 200

    with session_factory() as db:
        sessions = db.scalars(select(AuthSession).order_by(AuthSession.id)).all()
        assert len(sessions) == 2
        assert sessions[0].revoked_at is not None
        assert sessions[1].revoked_at is None
