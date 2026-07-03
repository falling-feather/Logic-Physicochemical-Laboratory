from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    Assignment,
    BugRecord,
    ClassGroup,
    ContentPageRecord,
    Course,
    LearningEvent,
    PointLedger,
    School,
    Submission,
    User,
)
from app.schemas.admin import (
    AdminBootstrapRequest,
    AdminContentPageRead,
    AdminStats,
    AdminUserRead,
    AdminUserUpdate,
    BugRecordCreate,
    BugRecordRead,
    BugRecordUpdate,
)
from app.schemas.school import ClassRead, SchoolRead
from app.services.content_catalog import ensure_seed_pages


router = APIRouter()


@router.post("/bootstrap", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: AdminBootstrapRequest, db: Session = Depends(get_db)) -> User:
    if _active_admin_count(db) > 0:
        raise HTTPException(status_code=409, detail="Admin bootstrap is already complete")

    settings = get_settings()
    if settings.admin_bootstrap_token:
        if payload.bootstrap_token != settings.admin_bootstrap_token:
            raise HTTPException(status_code=403, detail="Invalid admin bootstrap token")
    elif settings.environment.lower() in {"production", "prod"}:
        raise HTTPException(status_code=403, detail="Admin bootstrap token is required in production")

    username = payload.username.strip()
    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        display_name=payload.display_name.strip(),
        role="admin",
        status="active",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    _require_admin(current_user)
    statement = select(User).order_by(User.id)
    if role is not None:
        statement = statement.where(User.role == role.strip().lower())
    if status_filter is not None:
        statement = statement.where(User.status == status_filter.strip().lower())
    return list(db.scalars(statement).all())


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _require_admin(current_user)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    next_role = payload.role or user.role
    next_status = payload.status or user.status
    if user.role == "admin" and (next_role != "admin" or next_status != "active"):
        if _active_admin_count(db) <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove the last active admin")

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.status is not None:
        user.status = payload.status

    db.commit()
    db.refresh(user)
    return user


@router.get("/schools", response_model=list[SchoolRead])
def list_admin_schools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[School]:
    _require_admin(current_user)
    return list(db.scalars(select(School).order_by(School.id)).all())


@router.get("/classes", response_model=list[ClassRead])
def list_admin_classes(
    school_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClassGroup]:
    _require_admin(current_user)
    statement = select(ClassGroup).order_by(ClassGroup.id)
    if school_id is not None:
        statement = statement.where(ClassGroup.school_id == school_id)
    return list(db.scalars(statement).all())


@router.get("/content/pages", response_model=list[AdminContentPageRead])
def list_admin_content_pages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdminContentPageRead]:
    _require_admin(current_user)
    ensure_seed_pages(db)
    records = db.scalars(select(ContentPageRecord).order_by(ContentPageRecord.slug)).all()
    return [
        AdminContentPageRead(
            id=record.id,
            slug=record.slug,
            title=str(record.schema_json.get("title", record.slug)),
            galaxy=str(record.schema_json.get("galaxy", "")),
            subject=str(record.schema_json.get("subject", "")),
            layout=str(record.schema_json.get("layout", "")),
            status=record.status,
            version=record.version,
            updated_at=record.updated_at,
        )
        for record in records
    ]


@router.get("/stats", response_model=AdminStats)
def read_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminStats:
    _require_admin(current_user)
    ensure_seed_pages(db)
    users_by_role = {
        str(role): int(count)
        for role, count in db.execute(select(User.role, func.count()).group_by(User.role)).all()
    }
    return AdminStats(
        total_users=_count(db, User),
        active_users=_count(db, User, User.status == "active"),
        users_by_role=users_by_role,
        total_schools=_count(db, School),
        total_classes=_count(db, ClassGroup),
        total_content_pages=_count(db, ContentPageRecord),
        total_courses=_count(db, Course),
        total_assignments=_count(db, Assignment),
        total_learning_events=_count(db, LearningEvent),
        total_submissions=_count(db, Submission),
        total_point_ledger_entries=_count(db, PointLedger),
        total_bug_records=_count(db, BugRecord),
        open_bug_records=_count(db, BugRecord, BugRecord.status != "closed"),
    )


@router.get("/bugs", response_model=list[BugRecordRead])
def list_bug_records(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BugRecord]:
    _require_admin(current_user)
    statement = select(BugRecord).order_by(BugRecord.id)
    if status_filter is not None:
        statement = statement.where(BugRecord.status == status_filter.strip().lower())
    return list(db.scalars(statement).all())


@router.post("/bugs", response_model=BugRecordRead, status_code=status.HTTP_201_CREATED)
def create_bug_record(
    payload: BugRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecord:
    _require_admin(current_user)
    bug = BugRecord(
        title=payload.title.strip(),
        category=payload.category.strip(),
        severity=payload.severity,
        status=payload.status,
        source=_strip_optional(payload.source),
        evidence=_strip_optional(payload.evidence),
        notes=_strip_optional(payload.notes),
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


@router.patch("/bugs/{bug_id}", response_model=BugRecordRead)
def update_bug_record(
    bug_id: int,
    payload: BugRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecord:
    _require_admin(current_user)
    bug = db.get(BugRecord, bug_id)
    if bug is None:
        raise HTTPException(status_code=404, detail="Bug record not found")

    for field in ("title", "category", "source", "evidence", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(bug, field, _strip_required(value) if field in {"title", "category"} else _strip_optional(value))
    if payload.severity is not None:
        bug.severity = payload.severity
    if payload.status is not None:
        bug.status = payload.status

    db.commit()
    db.refresh(bug)
    return bug


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _active_admin_count(db: Session) -> int:
    return _count(db, User, User.role == "admin", User.status == "active")


def _count(db: Session, model, *criteria: Any) -> int:
    statement = select(func.count()).select_from(model)
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(db.scalar(statement) or 0)


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _strip_required(value: str) -> str:
    return value.strip()
