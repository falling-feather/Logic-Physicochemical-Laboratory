from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SecurityControlLock


ADMIN_AUTHORITY_LOCK = "admin-authority"


def acquire_security_control_lock(db: Session, name: str) -> SecurityControlLock:
    lock_name = name.strip().lower()
    if not lock_name or len(lock_name) > 80:
        raise ValueError("Invalid security control lock name")
    statement = (
        select(SecurityControlLock)
        .where(SecurityControlLock.name == lock_name)
        .with_for_update()
    )
    row = db.scalar(statement)
    if row is None:
        try:
            with db.begin_nested():
                db.add(SecurityControlLock(name=lock_name))
                db.flush()
        except IntegrityError:
            pass
        row = db.scalar(statement)
    if row is None:
        raise RuntimeError("Security control lock is unavailable")
    return row
