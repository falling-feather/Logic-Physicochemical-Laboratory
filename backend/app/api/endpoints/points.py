from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ClassGroup, PointLedger, SchoolMembership, User
from app.schemas.course import PointLedgerRead


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
        class_group = _get_class(db, class_id)
        _require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})
        statement = statement.where(PointLedger.class_id == class_id)
    elif current_user.role != "admin":
        school_ids = _teacher_school_ids(db, current_user.id)
        if not school_ids:
            return []
        statement = statement.where(PointLedger.school_id.in_(school_ids))

    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    return list(db.scalars(statement).all())


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _teacher_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.role.in_(["admin", "teacher"]),
                SchoolMembership.status == "active",
            )
        ).all()
    )


def _require_school_role(db: Session, user: User, school_id: int, roles: set[str]) -> None:
    if user.role == "admin":
        return
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.role.in_(roles),
            SchoolMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="School role is outside current user scope")
