from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import PointLedger, User
from app.schemas.course import PointLedgerRead
from app.services.access_control import get_class, require_school_role, teacher_school_ids


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
        require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})
        statement = statement.where(PointLedger.class_id == class_id)
    elif current_user.role != "admin":
        school_ids = teacher_school_ids(db, current_user.id)
        if not school_ids:
            return []
        statement = statement.where(PointLedger.school_id.in_(school_ids))

    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    return list(db.scalars(statement).all())
