from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import PointLedger, User
from app.schemas.course import PointLedgerRead
from app.services.access_control import get_class, require_class_teacher_or_admin, teacher_class_ids


router = APIRouter()


@router.get("/ledger", response_model=list[PointLedgerRead])
def list_point_ledger(
    user_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PointLedger]:
    statement = select(PointLedger).order_by(PointLedger.id)
    if current_user.role == "student":
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Students can only view their own points")
        statement = statement.where(PointLedger.user_id == current_user.id)
        if class_id is not None:
            statement = statement.where(PointLedger.class_id == class_id)
        return list(db.scalars(statement).all())

    if class_id is not None:
        class_group = get_class(db, class_id)
        require_class_teacher_or_admin(
            db,
            current_user,
            class_group,
            detail="Point ledger requires class teacher scope",
        )
        statement = statement.where(PointLedger.class_id == class_id)
    elif current_user.role != "admin":
        class_ids = teacher_class_ids(db, current_user.id)
        if not class_ids:
            return []
        statement = statement.where(PointLedger.class_id.in_(class_ids))

    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    return list(db.scalars(statement).all())
