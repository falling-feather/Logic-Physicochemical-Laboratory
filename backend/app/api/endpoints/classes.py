from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ClassGroup, ClassMembership, SchoolMembership, User
from app.schemas.school import ClassCreate, ClassJoinRequest, ClassRead, MembershipRead


router = APIRouter()


@router.get("", response_model=list[ClassRead])
def list_classes(
    school_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassGroup]:
    statement = select(ClassGroup).order_by(ClassGroup.id)
    if school_id is not None:
        _require_school_member(db, current_user, school_id)
        statement = statement.where(ClassGroup.school_id == school_id)
    elif current_user.role != "admin":
        school_ids = _visible_school_ids(db, current_user.id)
        if not school_ids:
            return []
        statement = statement.where(ClassGroup.school_id.in_(school_ids))
    return list(db.scalars(statement).all())


@router.post("", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassGroup:
    _require_school_role(db, current_user, payload.school_id, {"admin", "teacher"})
    existing = db.scalar(
        select(ClassGroup).where(
            ClassGroup.school_id == payload.school_id,
            ClassGroup.name == payload.name.strip(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Class already exists in this school")

    class_group = ClassGroup(
        school_id=payload.school_id,
        name=payload.name.strip(),
        grade=(payload.grade or "").strip() or None,
        term=(payload.term or "").strip() or None,
    )
    db.add(class_group)
    db.flush()
    _ensure_school_membership(db, payload.school_id, current_user.id, "teacher")
    _ensure_class_membership(db, class_group.id, current_user.id, "teacher")
    db.commit()
    db.refresh(class_group)
    return class_group


@router.post("/{class_id}/join", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
def join_class(
    class_id: int,
    payload: ClassJoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassMembership:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")

    role = payload.role.strip().lower()
    if role not in {"student", "teacher"}:
        raise HTTPException(status_code=422, detail="Unsupported class role")
    if role == "teacher" and current_user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Only teachers can join with teacher role")
    if role == "teacher" and current_user.role != "admin":
        _require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})

    _ensure_school_membership(db, class_group.school_id, current_user.id, role)
    membership = _ensure_class_membership(db, class_group.id, current_user.id, role)
    db.commit()
    db.refresh(membership)
    return membership


def _visible_school_ids(db: Session, user_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SchoolMembership.school_id).where(
                SchoolMembership.user_id == user_id,
                SchoolMembership.status == "active",
            )
        ).all()
    )


def _require_school_member(db: Session, user: User, school_id: int) -> None:
    if user.role == "admin":
        return
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user.id,
            SchoolMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="School is outside current user scope")


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


def _ensure_school_membership(db: Session, school_id: int, user_id: int, role: str) -> SchoolMembership:
    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.user_id == user_id,
            SchoolMembership.role == role,
        )
    )
    if membership is None:
        membership = SchoolMembership(school_id=school_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
    return membership


def _ensure_class_membership(db: Session, class_id: int, user_id: int, role: str) -> ClassMembership:
    membership = db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user_id,
            ClassMembership.role == role,
        )
    )
    if membership is None:
        membership = ClassMembership(class_id=class_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
    return membership
