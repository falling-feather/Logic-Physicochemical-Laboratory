import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.db.session import get_session_factory
from app.models import AuthSession, User
from app.services.auth_sessions import cleanup_expired_auth_sessions
from scripts.cleanup_auth_sessions import main as cleanup_main


def test_auth_session_cleanup_dry_run_does_not_revoke_or_expose_sensitive_fields(client):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user()
        db.add(user)
        db.flush()
        db.add_all(
            [
                _auth_session(user.id, "old-expired", expires_at=now - timedelta(days=2)),
                _auth_session(user.id, "active", expires_at=now + timedelta(days=1)),
                _auth_session(
                    user.id,
                    "already-revoked",
                    expires_at=now - timedelta(days=3),
                    revoked_at=now - timedelta(days=1),
                ),
            ]
        )
        db.commit()

    report = cleanup_expired_auth_sessions(before_at=now, limit=5000, apply=False)

    assert report["ok"] is True
    assert report["status"] == "dry_run"
    assert report["policy"]["source"] == "before"
    assert report["total_candidates"] == 1
    assert report["selected_count"] == 1
    assert report["revoked_count"] == 0
    assert report["sensitive_fields_returned"] is False
    report_json = json.dumps(report, ensure_ascii=False)
    assert "old-expired" not in report_json
    assert "cleanup-session-agent" not in report_json
    assert "198.51.100.88" not in report_json
    assert hash_token("old-expired") not in report_json

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))) == 2


def test_auth_session_cleanup_apply_revokes_only_expired_unrevoked_sessions(client):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user(username="auth_cleanup_apply_owner")
        db.add(user)
        db.flush()
        revoke_one = _auth_session(user.id, "revoke-one", expires_at=now - timedelta(days=2))
        revoke_two = _auth_session(user.id, "revoke-two", expires_at=now - timedelta(days=3))
        keep_active = _auth_session(user.id, "keep-active", expires_at=now + timedelta(days=1))
        keep_revoked = _auth_session(
            user.id,
            "keep-revoked",
            expires_at=now - timedelta(days=4),
            revoked_at=now - timedelta(days=1),
        )
        db.add_all([revoke_one, revoke_two, keep_active, keep_revoked])
        db.commit()
        revoke_ids = {revoke_one.id, revoke_two.id}
        keep_active_id = keep_active.id
        keep_revoked_id = keep_revoked.id

    report = cleanup_expired_auth_sessions(limit=5000, apply=True, generated_at=now)

    assert report["ok"] is True
    assert report["status"] == "revoked"
    assert report["policy"]["source"] == "generated_at"
    assert report["total_candidates"] == 2
    assert report["selected_count"] == 2
    assert report["revoked_count"] == 2
    assert report["truncated"] is False

    with session_factory() as db:
        revoked_ids = set(
            db.scalars(
                select(AuthSession.id)
                .where(AuthSession.id.in_(revoke_ids))
                .where(AuthSession.revoked_at.is_not(None))
            ).all()
        )
        active_session = db.get(AuthSession, keep_active_id)
        already_revoked = db.get(AuthSession, keep_revoked_id)
        assert revoked_ids == revoke_ids
        assert active_session is not None
        assert active_session.revoked_at is None
        assert already_revoked is not None
        assert already_revoked.revoked_at is not None


def test_auth_session_cleanup_limit_and_cli_validation(client):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user(username="auth_cleanup_limit_owner")
        db.add(user)
        db.flush()
        db.add_all(
            [
                _auth_session(user.id, "limit-one", expires_at=now - timedelta(days=2)),
                _auth_session(user.id, "limit-two", expires_at=now - timedelta(days=3)),
            ]
        )
        db.commit()

    report = cleanup_expired_auth_sessions(before_at=now, limit=1, apply=True)

    assert report["status"] == "revoked"
    assert report["total_candidates"] == 2
    assert report["selected_count"] == 1
    assert report["revoked_count"] == 1
    assert report["truncated"] is True
    assert cleanup_main(["--before", now.isoformat()]) == 0
    assert cleanup_main(["--limit", "0"]) == 1


def _cleanup_user(username: str = "auth_cleanup_owner") -> User:
    return User(
        username=username,
        normalized_username=username,
        display_name="Auth Cleanup Owner",
        role="teacher",
        password_hash=hash_password("secret123"),
    )


def _auth_session(
    user_id: int,
    token: str,
    *,
    expires_at: datetime,
    revoked_at: datetime | None = None,
) -> AuthSession:
    return AuthSession(
        user_id=user_id,
        token_hash=hash_token(token),
        device_label="cleanup-device",
        user_agent="cleanup-session-agent",
        last_seen_ip_hash=hash_token("198.51.100.88"),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
