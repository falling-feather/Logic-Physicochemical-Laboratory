from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def normalize_username(username: str) -> str:
    return username.strip().lower()


def require_normalized_username(username: str, *, min_length: int = 1) -> str:
    normalized = normalize_username(username)
    if not normalized:
        raise HTTPException(status_code=422, detail="Username is required")
    if len(normalized) < min_length:
        raise HTTPException(status_code=422, detail=f"Username must be at least {min_length} characters")
    return normalized


def find_user_by_normalized_username(db: Session, username: str) -> User | None:
    return db.scalar(
        select(User)
        .where(User.normalized_username == normalize_username(username))
        .order_by(User.id)
        .limit(1)
    )
