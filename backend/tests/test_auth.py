from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import AuditLog, AuthSession, LoginAttempt, User


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


def test_session_management_requires_authentication(client):
    sessions = client.get("/api/auth/sessions")
    assert sessions.status_code == 401

    revoke = client.delete("/api/auth/sessions/1")
    assert revoke.status_code == 401


def test_login_records_session_device_metadata_and_last_seen(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "device_session_owner",
            "password": "secret123",
            "display_name": "Device Session Owner",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={
            "X-Device-Name": "Teacher Lab Laptop",
            "User-Agent": "pytest-login-agent",
            "X-Forwarded-For": "203.0.113.20, 10.0.0.1",
        },
        json={"username": "device_session_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    sessions_response = client.get(
        "/api/auth/sessions",
        headers={**_auth_header(token), "User-Agent": "pytest-followup-agent"},
    )
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert len(sessions) == 1
    assert sessions[0]["device_label"] == "Teacher Lab Laptop"
    assert sessions[0]["user_agent"] == "pytest-login-agent"
    assert sessions[0]["last_seen_at"] is not None
    assert sessions[0]["is_current"] is True

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        assert auth_session.device_label == "Teacher Lab Laptop"
        assert auth_session.user_agent == "pytest-login-agent"
        assert auth_session.last_seen_at is not None
        assert auth_session.last_seen_ip_hash is not None
        assert len(auth_session.last_seen_ip_hash) == 64
        assert "203.0.113.20" not in auth_session.last_seen_ip_hash


def test_authenticated_request_refreshes_session_last_seen(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "last_seen_owner",
            "password": "secret123",
            "display_name": "Last Seen Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    login = client.post("/api/auth/login", json={"username": "last_seen_owner", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    old_seen = datetime(2000, 1, 1, tzinfo=UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        auth_session.last_seen_at = old_seen
        auth_session.last_seen_ip_hash = "old"
        db.commit()

    me = client.get(
        "/api/users/me",
        headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.10", "User-Agent": "pytest-me-agent"},
    )
    assert me.status_code == 200

    with session_factory() as db:
        refreshed_session = db.scalar(select(AuthSession))
        assert refreshed_session is not None
        assert refreshed_session.last_seen_at is not None
        assert refreshed_session.last_seen_at.year >= 2026
        assert refreshed_session.last_seen_ip_hash is not None
        assert refreshed_session.last_seen_ip_hash != "old"
        assert "198.51.100.10" not in refreshed_session.last_seen_ip_hash


def test_session_last_seen_refresh_is_throttled_for_same_ip(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "last_seen_throttle_owner",
            "password": "secret123",
            "display_name": "Last Seen Throttle Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "198.51.100.50"},
        json={"username": "last_seen_throttle_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        recent_seen = datetime.now(UTC)
        auth_session.last_seen_at = recent_seen
        existing_ip_hash = auth_session.last_seen_ip_hash
        db.commit()
        stored_recent_seen = auth_session.last_seen_at

    me = client.get("/api/users/me", headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.50"})
    assert me.status_code == 200

    with session_factory() as db:
        throttled_session = db.scalar(select(AuthSession))
        assert throttled_session is not None
        assert throttled_session.last_seen_at == stored_recent_seen
        assert throttled_session.last_seen_ip_hash == existing_ip_hash


def test_session_last_seen_refreshes_after_throttle_window(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "last_seen_window_owner",
            "password": "secret123",
            "display_name": "Last Seen Window Owner",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "198.51.100.60"},
        json={"username": "last_seen_window_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    stale_seen = datetime.now(UTC) - timedelta(seconds=get_settings().session_last_seen_update_seconds + 1)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        auth_session.last_seen_at = stale_seen
        existing_ip_hash = auth_session.last_seen_ip_hash
        db.commit()
        stored_stale_seen = auth_session.last_seen_at

    me = client.get("/api/users/me", headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.60"})
    assert me.status_code == 200

    with session_factory() as db:
        refreshed_session = db.scalar(select(AuthSession))
        assert refreshed_session is not None
        assert refreshed_session.last_seen_at is not None
        assert refreshed_session.last_seen_at != stored_stale_seen
        assert refreshed_session.last_seen_ip_hash == existing_ip_hash


def test_session_last_seen_refreshes_when_missing(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "missing_last_seen_owner",
            "password": "secret123",
            "display_name": "Missing Last Seen Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "198.51.100.70"},
        json={"username": "missing_last_seen_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        auth_session.last_seen_at = None
        auth_session.last_seen_ip_hash = None
        db.commit()

    me = client.get("/api/users/me", headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.70"})
    assert me.status_code == 200

    with session_factory() as db:
        refreshed_session = db.scalar(select(AuthSession))
        assert refreshed_session is not None
        assert refreshed_session.last_seen_at is not None
        assert refreshed_session.last_seen_ip_hash is not None


def test_session_last_seen_refreshes_when_ip_hash_changes_inside_window(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "last_seen_ip_change_owner",
            "password": "secret123",
            "display_name": "Last Seen IP Change Owner",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "198.51.100.80"},
        json={"username": "last_seen_ip_change_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        recent_seen = datetime.now(UTC)
        auth_session.last_seen_at = recent_seen
        old_ip_hash = auth_session.last_seen_ip_hash
        db.commit()
        stored_recent_seen = auth_session.last_seen_at

    me = client.get("/api/users/me", headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.81"})
    assert me.status_code == 200

    with session_factory() as db:
        refreshed_session = db.scalar(select(AuthSession))
        assert refreshed_session is not None
        assert refreshed_session.last_seen_at != stored_recent_seen
        assert refreshed_session.last_seen_ip_hash != old_ip_hash


def test_session_last_seen_throttle_can_be_disabled(client, monkeypatch):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "last_seen_no_throttle_owner",
            "password": "secret123",
            "display_name": "Last Seen No Throttle Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    login = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "198.51.100.90"},
        json={"username": "last_seen_no_throttle_owner", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        recent_seen = datetime.now(UTC)
        auth_session.last_seen_at = recent_seen
        existing_ip_hash = auth_session.last_seen_ip_hash
        db.commit()
        stored_recent_seen = auth_session.last_seen_at

    monkeypatch.setenv("ASTRA_SESSION_LAST_SEEN_UPDATE_SECONDS", "0")
    get_settings.cache_clear()
    me = client.get("/api/users/me", headers={**_auth_header(token), "X-Forwarded-For": "198.51.100.90"})
    assert me.status_code == 200

    with session_factory() as db:
        refreshed_session = db.scalar(select(AuthSession))
        assert refreshed_session is not None
        assert refreshed_session.last_seen_at != stored_recent_seen
        assert refreshed_session.last_seen_ip_hash == existing_ip_hash


def test_user_can_list_and_revoke_individual_sessions(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "session_owner",
            "password": "secret123",
            "display_name": "Session Owner",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    first_login = client.post("/api/auth/login", json={"username": "session_owner", "password": "secret123"})
    assert first_login.status_code == 200
    first_token = first_login.json()["access_token"]
    second_login = client.post("/api/auth/login", json={"username": "session_owner", "password": "secret123"})
    assert second_login.status_code == 200
    second_token = second_login.json()["access_token"]

    sessions_response = client.get("/api/auth/sessions", headers=_auth_header(second_token))
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert len(sessions) == 2
    assert sum(1 for auth_session in sessions if auth_session["is_current"]) == 1
    old_session = next(auth_session for auth_session in sessions if not auth_session["is_current"])

    revoke = client.delete(
        f"/api/auth/sessions/{old_session['id']}",
        headers={**_auth_header(second_token), "X-Request-ID": "session-revoke-request"},
    )
    assert revoke.status_code == 200
    assert revoke.json() == {
        "status": "ok",
        "revoked_session_id": old_session["id"],
        "is_current": False,
    }

    old_token_me = client.get("/api/users/me", headers=_auth_header(first_token))
    assert old_token_me.status_code == 401
    current_token_me = client.get("/api/users/me", headers=_auth_header(second_token))
    assert current_token_me.status_code == 200

    active_sessions = client.get("/api/auth/sessions", headers=_auth_header(second_token))
    assert active_sessions.status_code == 200
    assert len(active_sessions.json()) == 1
    assert active_sessions.json()[0]["is_current"] is True

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        revoked_session = db.get(AuthSession, old_session["id"])
        assert revoked_session is not None
        assert revoked_session.revoked_at is not None
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "auth.session.revoke"))
        assert audit is not None
        assert audit.resource_type == "auth_session"
        assert audit.resource_id == str(old_session["id"])
        assert audit.request_id == "session-revoke-request"
        assert audit.snapshot_json == {
            "revoked_session_id": old_session["id"],
            "is_current": False,
            "revoked_sessions": 1,
        }


def test_user_can_revoke_current_session(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "current_session_owner",
            "password": "secret123",
            "display_name": "Current Session Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    login = client.post("/api/auth/login", json={"username": "current_session_owner", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    sessions_response = client.get("/api/auth/sessions", headers=_auth_header(token))
    assert sessions_response.status_code == 200
    current_session = sessions_response.json()[0]
    assert current_session["is_current"] is True

    revoke = client.delete(f"/api/auth/sessions/{current_session['id']}", headers=_auth_header(token))
    assert revoke.status_code == 200
    assert revoke.json()["is_current"] is True
    assert get_settings().session_cookie_name in revoke.headers["set-cookie"]

    after_revoke = client.get("/api/users/me", headers=_auth_header(token))
    assert after_revoke.status_code == 401
    sessions_after_revoke = client.get("/api/auth/sessions", headers=_auth_header(token))
    assert sessions_after_revoke.status_code == 401


def test_user_cannot_revoke_another_users_session(client):
    owner_register = client.post(
        "/api/auth/register",
        json={
            "username": "session_boundary_owner",
            "password": "secret123",
            "display_name": "Session Boundary Owner",
            "role": "teacher",
        },
    )
    assert owner_register.status_code == 201
    other_register = client.post(
        "/api/auth/register",
        json={
            "username": "session_boundary_other",
            "password": "secret123",
            "display_name": "Session Boundary Other",
            "role": "teacher",
        },
    )
    assert other_register.status_code == 201
    owner_login = client.post(
        "/api/auth/login",
        json={"username": "session_boundary_owner", "password": "secret123"},
    )
    assert owner_login.status_code == 200
    owner_token = owner_login.json()["access_token"]
    other_login = client.post(
        "/api/auth/login",
        json={"username": "session_boundary_other", "password": "secret123"},
    )
    assert other_login.status_code == 200
    other_token = other_login.json()["access_token"]

    other_sessions = client.get("/api/auth/sessions", headers=_auth_header(other_token))
    assert other_sessions.status_code == 200
    other_session_id = other_sessions.json()[0]["id"]

    revoke = client.delete(f"/api/auth/sessions/{other_session_id}", headers=_auth_header(owner_token))
    assert revoke.status_code == 404

    other_me = client.get("/api/users/me", headers=_auth_header(other_token))
    assert other_me.status_code == 200
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        other_session = db.get(AuthSession, other_session_id)
        assert other_session is not None
        assert other_session.revoked_at is None
        audits = db.scalars(select(AuditLog).where(AuditLog.action == "auth.session.revoke")).all()
        assert audits == []


def test_user_cannot_revoke_expired_session(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "expired_session_owner",
            "password": "secret123",
            "display_name": "Expired Session Owner",
            "role": "student",
        },
    )
    assert register.status_code == 201
    first_login = client.post("/api/auth/login", json={"username": "expired_session_owner", "password": "secret123"})
    assert first_login.status_code == 200
    second_login = client.post("/api/auth/login", json={"username": "expired_session_owner", "password": "secret123"})
    assert second_login.status_code == 200
    second_token = second_login.json()["access_token"]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        sessions = db.scalars(select(AuthSession).order_by(AuthSession.id)).all()
        assert len(sessions) == 2
        expired_session_id = sessions[0].id
        active_session_id = sessions[1].id
        sessions[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    listed = client.get("/api/auth/sessions", headers=_auth_header(second_token))
    assert listed.status_code == 200
    assert [auth_session["id"] for auth_session in listed.json()] == [active_session_id]

    revoke = client.delete(f"/api/auth/sessions/{expired_session_id}", headers=_auth_header(second_token))
    assert revoke.status_code == 404

    with session_factory() as db:
        expired_session = db.get(AuthSession, expired_session_id)
        assert expired_session is not None
        assert expired_session.revoked_at is None
        audits = db.scalars(select(AuditLog).where(AuditLog.action == "auth.session.revoke")).all()
        assert audits == []


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


def test_register_rejects_short_username_after_normalization(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": " A ",
            "password": "secret123",
            "display_name": "Short Username",
            "role": "teacher",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Username must be at least 3 characters"


def test_register_rejects_blank_display_name_after_trimming(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "blank_display_teacher",
            "password": "secret123",
            "display_name": "   ",
            "role": "teacher",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Display name is required"


def test_register_normalizes_username_and_rejects_case_variant(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "MixedTeacher",
            "password": "secret123",
            "display_name": "Mixed Teacher",
            "role": "teacher",
        },
    )
    assert register.status_code == 201
    assert register.json()["username"] == "mixedteacher"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored = db.scalar(select(User).where(User.username == "mixedteacher"))
        assert stored is not None
        assert stored.normalized_username == "mixedteacher"

    uppercase_login = client.post(
        "/api/auth/login",
        json={"username": "MIXEDTEACHER", "password": "secret123"},
    )
    assert uppercase_login.status_code == 200
    assert uppercase_login.json()["user"]["username"] == "mixedteacher"

    duplicate = client.post(
        "/api/auth/register",
        json={
            "username": "mixedteacher",
            "password": "secret123",
            "display_name": "Duplicate Teacher",
            "role": "teacher",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Username already exists"


def test_user_normalized_username_unique_constraint_blocks_case_variants(client):
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            User(
                username="DbCaseTeacher",
                normalized_username="dbcaseteacher",
                password_hash=hash_password("secret123"),
                display_name="DB Case Teacher",
                role="teacher",
            )
        )
        db.commit()

        db.add(
            User(
                username="dbcaseteacher_shadow",
                normalized_username="dbcaseteacher",
                password_hash=hash_password("secret123"),
                display_name="DB Duplicate Teacher",
                role="teacher",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_login_finds_legacy_mixed_case_user_by_normalized_username(client):
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            User(
                username="LegacyTeacher",
                normalized_username="legacyteacher",
                password_hash=hash_password("secret123"),
                display_name="Legacy Teacher",
                role="teacher",
            )
        )
        db.commit()

    login = client.post(
        "/api/auth/login",
        json={"username": "legacyteacher", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "LegacyTeacher"

    duplicate = client.post(
        "/api/auth/register",
        json={
            "username": "LEGACYTEACHER",
            "password": "secret123",
            "display_name": "Duplicate Legacy",
            "role": "teacher",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Username already exists"


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


def test_login_rate_limit_uses_normalized_username(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "CaseLockTeacher",
            "password": "secret123",
            "display_name": "Case Lock Teacher",
            "role": "teacher",
        },
    )
    assert register.status_code == 201

    max_attempts = get_settings().login_max_attempts
    variants = ["CASELOCKTEACHER", "caselockteacher", "CaseLockTeacher"]
    for index in range(max_attempts):
        response = client.post(
            "/api/auth/login",
            json={"username": variants[index % len(variants)], "password": "wrong-secret"},
        )
        assert response.status_code == (429 if index == max_attempts - 1 else 401)

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        attempts = db.scalars(select(LoginAttempt).order_by(LoginAttempt.id)).all()
        assert [attempt.username for attempt in attempts] == ["caselockteacher"]
        assert [attempt.normalized_username for attempt in attempts] == ["caselockteacher"]
        assert attempts[0].failure_count == max_attempts
        assert attempts[0].locked_until is not None


def test_login_attempt_normalized_username_unique_constraint_blocks_case_variants(client):
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(LoginAttempt(username="CaseLockBucket", normalized_username="caselockbucket", failure_count=1))
        db.commit()

        db.add(LoginAttempt(username="caselockbucket_shadow", normalized_username="caselockbucket", failure_count=1))
        with pytest.raises(IntegrityError):
            db.commit()


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
