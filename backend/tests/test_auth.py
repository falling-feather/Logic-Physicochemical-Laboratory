from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuthSession, LoginAttempt


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
