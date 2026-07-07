import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password, hash_token
from app.db.session import get_session_factory
from app.models import PasswordResetToken, User
from app.services.password_reset_tokens import cleanup_password_reset_tokens
from scripts.cleanup_password_reset_tokens import main as cleanup_main


def test_password_reset_cleanup_dry_run_does_not_delete_or_expose_sensitive_fields(client):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user()
        db.add(user)
        db.flush()
        db.add_all(
            [
                _reset_token(user.id, "old-used", expires_at=now + timedelta(days=1), used_at=now - timedelta(days=40)),
                _reset_token(user.id, "old-expired", expires_at=now - timedelta(days=45), used_at=None),
                _reset_token(user.id, "recent-used", expires_at=now - timedelta(days=1), used_at=now - timedelta(days=3)),
                _reset_token(user.id, "recent-expired", expires_at=now - timedelta(days=3), used_at=None),
                _reset_token(user.id, "active", expires_at=now + timedelta(days=1), used_at=None),
            ]
        )
        db.commit()

    report = cleanup_password_reset_tokens(before_at=cutoff, limit=5000, apply=False)

    assert report["ok"] is True
    assert report["status"] == "dry_run"
    assert report["policy"]["source"] == "before"
    assert report["total_candidates"] == 2
    assert report["selected_count"] == 2
    assert report["deleted_count"] == 0
    assert report["truncated"] is False
    report_json = json.dumps(report, ensure_ascii=False)
    assert "cleanup_owner" not in report_json
    assert "198.51.100.44" not in report_json
    assert "cleanup-agent" not in report_json

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 5


def test_password_reset_cleanup_apply_deletes_only_terminal_tokens_past_cutoff(client):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user(username="cleanup_apply_owner")
        db.add(user)
        db.flush()
        keep_active = _reset_token(user.id, "keep-active", expires_at=now + timedelta(days=1), used_at=None)
        keep_recent_used = _reset_token(
            user.id,
            "keep-recent-used",
            expires_at=now - timedelta(days=20),
            used_at=now - timedelta(days=3),
        )
        delete_used = _reset_token(
            user.id,
            "delete-used",
            expires_at=now + timedelta(days=1),
            used_at=now - timedelta(days=60),
        )
        delete_expired = _reset_token(
            user.id,
            "delete-expired",
            expires_at=now - timedelta(days=60),
            used_at=None,
        )
        db.add_all([keep_active, keep_recent_used, delete_used, delete_expired])
        db.commit()
        keep_ids = {keep_active.id, keep_recent_used.id}

    report = cleanup_password_reset_tokens(retention_days=30, limit=5000, apply=True, generated_at=now)

    assert report["ok"] is True
    assert report["status"] == "deleted"
    assert report["policy"]["source"] == "query"
    assert report["policy"]["retention_days"] == 30
    assert report["total_candidates"] == 2
    assert report["selected_count"] == 2
    assert report["deleted_count"] == 2

    with session_factory() as db:
        remaining_ids = set(db.scalars(select(PasswordResetToken.id)).all())
        assert remaining_ids == keep_ids


def test_password_reset_cleanup_limit_and_cli_validation(client):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        user = _cleanup_user(username="cleanup_limit_owner")
        db.add(user)
        db.flush()
        db.add_all(
            [
                _reset_token(user.id, "limit-old-1", expires_at=now - timedelta(days=45), used_at=None),
                _reset_token(user.id, "limit-old-2", expires_at=now - timedelta(days=46), used_at=None),
            ]
        )
        db.commit()

    report = cleanup_password_reset_tokens(before_at=cutoff, limit=1, apply=True)

    assert report["status"] == "deleted"
    assert report["total_candidates"] == 2
    assert report["selected_count"] == 1
    assert report["deleted_count"] == 1
    assert report["truncated"] is True
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 1

    assert cleanup_main(["--before", cutoff.isoformat(), "--retention-days", "30"]) == 1
    assert cleanup_main(["--limit", "0"]) == 1


def _cleanup_user(username: str = "cleanup_owner") -> User:
    return User(
        username=username,
        normalized_username=username,
        display_name="Cleanup Owner",
        role="teacher",
        password_hash=hash_password("secret123"),
    )


def _reset_token(
    user_id: int,
    token: str,
    *,
    expires_at: datetime,
    used_at: datetime | None,
) -> PasswordResetToken:
    return PasswordResetToken(
        user_id=user_id,
        token_hash=hash_token(token),
        requested_username="cleanup_owner",
        requested_ip_hash=hash_token("198.51.100.44"),
        user_agent="cleanup-agent",
        expires_at=expires_at,
        used_at=used_at,
    )
