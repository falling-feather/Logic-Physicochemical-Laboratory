from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.core.security import hash_password, password_strength_errors
from app.db.session import get_db
from app.models import (
    AuditLog,
    Assignment,
    BugRecord,
    ClassGroup,
    ClassJoinRequest,
    ClassMembership,
    ContentDraft,
    ContentPageRecord,
    ContentPageVersion,
    Course,
    CourseClass,
    CourseUnit,
    LearningEvent,
    PointLedger,
    School,
    SchoolMembership,
    Submission,
    User,
)
from app.schemas.admin import (
    AdminBootstrapRequest,
    AdminClassPage,
    AdminClassJoinRequestPage,
    AdminClassJoinRequestRead,
    AdminClassJoinRequestReview,
    AdminClassStats,
    AdminContentPageRead,
    AdminContentPagePage,
    AdminContentPageVersionPage,
    AdminContentPageVersionRead,
    AdminContentDraftPage,
    AdminContentDraftRead,
    AdminPendingSubmissionQueue,
    AdminPendingSubmissionRead,
    AdminSchoolPage,
    AdminSchoolStats,
    AdminStats,
    AdminUserRead,
    AdminUserPage,
    AdminUserUpdate,
    AuditLogPage,
    AuditLogRead,
    BugRecordCreate,
    BugRecordPage,
    BugRecordRead,
    BugRecordUpdate,
)
from app.services.audit import record_audit_log
from app.services.class_join_requests import (
    apply_class_join_request_review,
    normalize_class_role,
    normalize_join_request_status,
)


router = APIRouter()
PENDING_SUBMISSION_STATUSES = ["submitted", "returned"]


@router.post("/bootstrap", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: AdminBootstrapRequest, request: Request, db: Session = Depends(get_db)) -> User:
    if _active_admin_count(db) > 0:
        raise HTTPException(status_code=409, detail="Admin bootstrap is already complete")

    settings = get_settings()
    if settings.admin_bootstrap_token:
        if payload.bootstrap_token != settings.admin_bootstrap_token:
            raise HTTPException(status_code=403, detail="Invalid admin bootstrap token")
    elif settings.environment.lower() in {"production", "prod"}:
        raise HTTPException(status_code=403, detail="Admin bootstrap token is required in production")

    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=422, detail="Username is required")
    _enforce_password_strength(payload.password, username)
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
    db.flush()
    record_audit_log(
        db,
        actor=user,
        action="admin.bootstrap",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot={"after": {"username": user.username, "role": user.role, "status": user.status}},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=AdminUserPage)
def list_users(
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUserPage:
    _require_admin(current_user)
    statement = select(User).order_by(User.id)
    if role is not None:
        statement = statement.where(User.role == role.strip().lower())
    if status_filter is not None:
        statement = statement.where(User.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(User.username.ilike(pattern), User.display_name.ilike(pattern)))
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminUserPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _require_admin(current_user)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    before = _user_snapshot(user)
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

    after = _user_snapshot(user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.update",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot=_change_snapshot(before, after),
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/schools", response_model=AdminSchoolPage)
def list_admin_schools(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminSchoolPage:
    _require_admin(current_user)
    statement = select(School).order_by(School.id)
    if status_filter is not None:
        statement = statement.where(School.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(School.name.ilike(pattern), School.region.ilike(pattern)))
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminSchoolPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.get("/schools/{school_id}/stats", response_model=AdminSchoolStats)
def read_admin_school_stats(
    school_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminSchoolStats:
    _require_admin(current_user)
    school = _get_school(db, school_id)
    return AdminSchoolStats(
        school_id=school.id,
        school_name=school.name,
        region=school.region,
        status=school.status,
        total_classes=_count(db, ClassGroup, ClassGroup.school_id == school.id),
        active_classes=_count(db, ClassGroup, ClassGroup.school_id == school.id, ClassGroup.status == "active"),
        active_students=_distinct_count(
            db,
            SchoolMembership.user_id,
            SchoolMembership.school_id == school.id,
            SchoolMembership.role == "student",
            SchoolMembership.status == "active",
        ),
        active_teachers=_distinct_count(
            db,
            SchoolMembership.user_id,
            SchoolMembership.school_id == school.id,
            SchoolMembership.role.in_(["admin", "teacher"]),
            SchoolMembership.status == "active",
        ),
        total_courses=_count(db, Course, Course.school_id == school.id),
        active_courses=_count(db, Course, Course.school_id == school.id, Course.status != "archived"),
        total_assignments=_school_assignment_count(db, school.id),
        active_assignments=_school_assignment_count(db, school.id, active_only=True),
        total_learning_events=_count(db, LearningEvent, LearningEvent.school_id == school.id),
        complete_learning_events=_count(
            db,
            LearningEvent,
            LearningEvent.school_id == school.id,
            LearningEvent.event_type == "complete",
        ),
        total_submissions=_school_submission_count(db, school.id),
        graded_submissions=_school_submission_count(db, school.id, statuses=["graded"]),
        returned_submissions=_school_submission_count(db, school.id, statuses=["returned"]),
        pending_submissions=_school_submission_count(db, school.id, statuses=PENDING_SUBMISSION_STATUSES),
        total_points=_sum_int(db, PointLedger.delta, PointLedger.school_id == school.id),
    )


@router.get("/classes", response_model=AdminClassPage)
def list_admin_classes(
    school_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminClassPage:
    _require_admin(current_user)
    statement = select(ClassGroup).order_by(ClassGroup.id)
    if school_id is not None:
        statement = statement.where(ClassGroup.school_id == school_id)
    if status_filter is not None:
        statement = statement.where(ClassGroup.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ClassGroup.name.ilike(pattern),
                ClassGroup.grade.ilike(pattern),
                ClassGroup.term.ilike(pattern),
            )
        )
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminClassPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.get("/classes/{class_id}/stats", response_model=AdminClassStats)
def read_admin_class_stats(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminClassStats:
    _require_admin(current_user)
    class_group = _get_class(db, class_id)
    active_students = _distinct_count(
        db,
        ClassMembership.user_id,
        ClassMembership.class_id == class_group.id,
        ClassMembership.role == "student",
        ClassMembership.status == "active",
    )
    active_assignments = _class_assignment_count(db, class_group.id, active_only=True)
    expected_submissions = active_students * active_assignments
    pending_submissions = _count(
        db,
        Submission,
        Submission.class_id == class_group.id,
        Submission.status.in_(PENDING_SUBMISSION_STATUSES),
    )
    total_points = _sum_int(db, PointLedger.delta, PointLedger.class_id == class_group.id)
    return AdminClassStats(
        class_id=class_group.id,
        class_name=class_group.name,
        school_id=class_group.school_id,
        grade=class_group.grade,
        term=class_group.term,
        status=class_group.status,
        active_students=active_students,
        active_teachers=_distinct_count(
            db,
            ClassMembership.user_id,
            ClassMembership.class_id == class_group.id,
            ClassMembership.role.in_(["admin", "teacher"]),
            ClassMembership.status == "active",
        ),
        active_courses=_class_course_count(db, class_group.id),
        active_assignments=active_assignments,
        expected_submissions=expected_submissions,
        total_learning_events=_count(db, LearningEvent, LearningEvent.class_id == class_group.id),
        complete_learning_events=_count(
            db,
            LearningEvent,
            LearningEvent.class_id == class_group.id,
            LearningEvent.event_type == "complete",
        ),
        total_submissions=_count(db, Submission, Submission.class_id == class_group.id),
        graded_submissions=_count(
            db,
            Submission,
            Submission.class_id == class_group.id,
            Submission.status == "graded",
        ),
        returned_submissions=_count(
            db,
            Submission,
            Submission.class_id == class_group.id,
            Submission.status == "returned",
        ),
        pending_submissions=pending_submissions,
        pending_submission_ratio=_divide(pending_submissions, expected_submissions),
        total_points=total_points,
        average_points_per_student=_divide(total_points, active_students),
        average_score_percent=_class_average_score_percent(db, class_group.id),
    )


@router.get("/class-join-requests", response_model=AdminClassJoinRequestPage)
def list_admin_class_join_requests(
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    user_id: int | None = Query(default=None),
    role: str | None = Query(default=None),
    status_filter: str | None = Query(default="pending", alias="status"),
    q: str | None = Query(default=None, max_length=160),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminClassJoinRequestPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = (
        select(ClassJoinRequest, School, ClassGroup, User)
        .join(School, School.id == ClassJoinRequest.school_id)
        .join(ClassGroup, ClassGroup.id == ClassJoinRequest.class_id)
        .join(User, User.id == ClassJoinRequest.user_id)
        .order_by(ClassJoinRequest.created_at.desc(), ClassJoinRequest.id.desc())
    )
    if school_id is not None:
        statement = statement.where(ClassJoinRequest.school_id == school_id)
    if class_id is not None:
        statement = statement.where(ClassJoinRequest.class_id == class_id)
    if user_id is not None:
        statement = statement.where(ClassJoinRequest.user_id == user_id)
    if role is not None:
        statement = statement.where(ClassJoinRequest.role == normalize_class_role(role))
    if status_filter is not None:
        statement = statement.where(ClassJoinRequest.status == normalize_join_request_status(status_filter))
    if from_at is not None:
        statement = statement.where(ClassJoinRequest.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(ClassJoinRequest.created_at <= to_at)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                School.name.ilike(pattern),
                ClassGroup.name.ilike(pattern),
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
                ClassJoinRequest.message.ilike(pattern),
            )
        )
    total = _statement_count(db, statement)
    rows = db.execute(statement.offset(offset).limit(limit)).all()
    items = [
        _admin_class_join_request_read(join_request, school, class_group, user)
        for join_request, school, class_group, user in rows
    ]
    return AdminClassJoinRequestPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.patch("/class-join-requests/{join_request_id}", response_model=AdminClassJoinRequestRead)
def review_admin_class_join_request(
    join_request_id: int,
    payload: AdminClassJoinRequestReview,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminClassJoinRequestRead:
    _require_admin(current_user)
    row = db.execute(
        select(ClassJoinRequest, School, ClassGroup, User)
        .join(School, School.id == ClassJoinRequest.school_id)
        .join(ClassGroup, ClassGroup.id == ClassJoinRequest.class_id)
        .join(User, User.id == ClassJoinRequest.user_id)
        .where(ClassJoinRequest.id == join_request_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Class join request not found")

    join_request, school, class_group, applicant = row
    apply_class_join_request_review(
        db,
        join_request=join_request,
        reviewer=current_user,
        request=request,
        next_status=payload.status,
        note=payload.note,
        approval_source="admin_queue",
    )
    db.commit()
    db.refresh(join_request)
    return _admin_class_join_request_read(join_request, school, class_group, applicant)


@router.get("/content/pages", response_model=AdminContentPagePage)
def list_admin_content_pages(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPagePage:
    _require_admin(current_user)
    records = db.scalars(select(ContentPageRecord).order_by(ContentPageRecord.slug)).all()
    items = [
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
    if status_filter is not None:
        normalized_status = status_filter.strip().lower()
        items = [item for item in items if item.status == normalized_status]
    if q is not None and q.strip():
        normalized_query = q.strip().lower()
        items = [
            item
            for item in items
            if normalized_query in item.slug.lower()
            or normalized_query in item.title.lower()
            or normalized_query in item.galaxy.lower()
            or normalized_query in item.subject.lower()
            or normalized_query in item.layout.lower()
        ]
    total = len(items)
    page_items = items[offset : offset + limit]
    return AdminContentPagePage(
        items=page_items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(page_items)),
    )


@router.get("/content/drafts", response_model=AdminContentDraftPage)
def list_admin_content_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    script_review_status: str | None = Query(default=None),
    author_user_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentDraftPage:
    _require_admin(current_user)
    statement = (
        select(ContentDraft, User)
        .join(User, User.id == ContentDraft.author_user_id)
        .order_by(ContentDraft.created_at.desc(), ContentDraft.id.desc())
    )
    if status_filter is not None:
        statement = statement.where(ContentDraft.status == status_filter.strip().lower())
    if script_review_status is not None:
        statement = statement.where(ContentDraft.script_review_status == script_review_status.strip().lower())
    if author_user_id is not None:
        statement = statement.where(ContentDraft.author_user_id == author_user_id)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ContentDraft.target_slug.ilike(pattern),
                ContentDraft.title.ilike(pattern),
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
            )
        )
    total = _statement_count(db, statement)
    rows = db.execute(statement.offset(offset).limit(limit)).all()
    items = [_admin_content_draft_read(draft, author) for draft, author in rows]
    return AdminContentDraftPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/content/page-versions", response_model=AdminContentPageVersionPage)
def list_admin_content_page_versions(
    slug: str | None = Query(default=None, max_length=180),
    source_draft_id: int | None = Query(default=None),
    restored_from_version_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPageVersionPage:
    _require_admin(current_user)
    statement = select(ContentPageVersion).order_by(
        ContentPageVersion.published_at.desc(),
        ContentPageVersion.id.desc(),
    )
    if slug is not None and slug.strip():
        statement = statement.where(ContentPageVersion.slug == slug.strip("/"))
    if source_draft_id is not None:
        statement = statement.where(ContentPageVersion.source_draft_id == source_draft_id)
    if restored_from_version_id is not None:
        statement = statement.where(ContentPageVersion.restored_from_version_id == restored_from_version_id)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ContentPageVersion.slug.ilike(pattern),
                ContentPageVersion.version.ilike(pattern),
                ContentPageVersion.note.ilike(pattern),
            )
        )
    total = _statement_count(db, statement)
    versions = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_content_page_version_read(version) for version in versions]
    return AdminContentPageVersionPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/stats", response_model=AdminStats)
def read_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminStats:
    _require_admin(current_user)
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
        pending_class_join_requests=_count(db, ClassJoinRequest, ClassJoinRequest.status == "pending"),
        total_content_pages=_count(db, ContentPageRecord),
        total_content_drafts=_count(db, ContentDraft),
        total_content_page_versions=_count(db, ContentPageVersion),
        pending_script_reviews=_count(db, ContentDraft, ContentDraft.script_review_status == "pending"),
        total_courses=_count(db, Course),
        total_assignments=_count(db, Assignment),
        total_learning_events=_count(db, LearningEvent),
        total_submissions=_count(db, Submission),
        total_point_ledger_entries=_count(db, PointLedger),
        total_bug_records=_count(db, BugRecord),
        open_bug_records=_count(db, BugRecord, BugRecord.status != "closed"),
        total_audit_logs=_count(db, AuditLog),
    )


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    actor_user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    event_result: str | None = Query(default=None),
    failure_reason: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if actor_user_id is not None:
        statement = statement.where(AuditLog.actor_user_id == actor_user_id)
    if action is not None:
        statement = statement.where(AuditLog.action == action.strip())
    if resource_type is not None:
        statement = statement.where(AuditLog.resource_type == resource_type.strip())
    if resource_id is not None:
        statement = statement.where(AuditLog.resource_id == resource_id.strip())
    if school_id is not None:
        statement = statement.where(AuditLog.school_id == school_id)
    if class_id is not None:
        statement = statement.where(AuditLog.class_id == class_id)
    if event_result is not None:
        statement = statement.where(AuditLog.event_result == event_result.strip())
    if failure_reason is not None:
        statement = statement.where(AuditLog.failure_reason == failure_reason.strip())
    if request_id is not None:
        statement = statement.where(AuditLog.request_id == request_id.strip())
    if from_at is not None:
        statement = statement.where(AuditLog.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(AuditLog.created_at <= to_at)
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.get("/submissions/pending", response_model=AdminPendingSubmissionQueue)
def list_pending_submissions(
    school_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    assignment_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    status_filter: Literal["submitted", "returned", "graded"] | None = Query(default=None, alias="status"),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    order_by: Literal["submitted_at", "graded_at", "due_at"] = Query(default="submitted_at"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminPendingSubmissionQueue:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    _validate_pending_submission_filters(db, school_id, class_id, course_id, assignment_id)

    criteria = _pending_submission_criteria(
        school_id=school_id,
        class_id=class_id,
        course_id=course_id,
        assignment_id=assignment_id,
        student_id=student_id,
        status_filter=status_filter,
        from_at=from_at,
        to_at=to_at,
    )
    total = _pending_submission_total(db, criteria)
    order_column = {
        "submitted_at": Submission.submitted_at,
        "graded_at": Submission.graded_at,
        "due_at": Assignment.due_at,
    }[order_by]
    order_clause = order_column.desc() if order == "desc" else order_column.asc()
    rows = db.execute(
        select(Submission, Assignment, Course, ClassGroup, User)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .outerjoin(ClassGroup, ClassGroup.id == Submission.class_id)
        .join(User, User.id == Submission.student_id)
        .where(*criteria)
        .order_by(order_clause, Submission.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    items = [
        AdminPendingSubmissionRead(
            id=submission.id,
            assignment_id=assignment.id,
            assignment_title=assignment.title,
            student_id=student.id,
            student_username=student.username,
            student_display_name=student.display_name,
            class_id=submission.class_id,
            class_name=class_group.name if class_group is not None else None,
            school_id=course.school_id,
            course_id=course.id,
            course_title=course.title,
            status=submission.status,
            score=submission.score,
            submitted_at=submission.submitted_at,
            graded_at=submission.graded_at,
            due_at=assignment.due_at,
        )
        for submission, assignment, course, class_group, student in rows
    ]
    next_offset = _next_offset(total, offset, len(items))
    return AdminPendingSubmissionQueue(items=items, total=total, limit=limit, offset=offset, next_offset=next_offset)


@router.get("/bugs", response_model=BugRecordPage)
def list_bug_records(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecordPage:
    _require_admin(current_user)
    statement = select(BugRecord).order_by(BugRecord.id)
    if status_filter is not None:
        statement = statement.where(BugRecord.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                BugRecord.title.ilike(pattern),
                BugRecord.category.ilike(pattern),
                BugRecord.source.ilike(pattern),
                BugRecord.evidence.ilike(pattern),
                BugRecord.notes.ilike(pattern),
            )
        )
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return BugRecordPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.post("/bugs", response_model=BugRecordRead, status_code=status.HTTP_201_CREATED)
def create_bug_record(
    payload: BugRecordCreate,
    request: Request,
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
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="admin.bug.create",
        resource_type="bug_record",
        resource_id=bug.id,
        event_result="success",
        request=request,
        snapshot={"after": _bug_snapshot(bug)},
    )
    db.commit()
    db.refresh(bug)
    return bug


@router.patch("/bugs/{bug_id}", response_model=BugRecordRead)
def update_bug_record(
    bug_id: int,
    payload: BugRecordUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugRecord:
    _require_admin(current_user)
    bug = db.get(BugRecord, bug_id)
    if bug is None:
        raise HTTPException(status_code=404, detail="Bug record not found")

    before = _bug_snapshot(bug)
    for field in ("title", "category", "source", "evidence", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(bug, field, _strip_required(value) if field in {"title", "category"} else _strip_optional(value))
    if payload.severity is not None:
        bug.severity = payload.severity
    if payload.status is not None:
        bug.status = payload.status

    after = _bug_snapshot(bug)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.bug.update",
        resource_type="bug_record",
        resource_id=bug.id,
        event_result="success",
        request=request,
        snapshot=_change_snapshot(before, after),
    )
    db.commit()
    db.refresh(bug)
    return bug


def _get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return school


def _get_class(db: Session, class_id: int) -> ClassGroup:
    class_group = db.get(ClassGroup, class_id)
    if class_group is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_group


def _admin_class_join_request_read(
    join_request: ClassJoinRequest,
    school: School,
    class_group: ClassGroup,
    applicant: User,
) -> AdminClassJoinRequestRead:
    return AdminClassJoinRequestRead(
        id=join_request.id,
        school_id=join_request.school_id,
        school_name=school.name,
        class_id=join_request.class_id,
        class_name=class_group.name,
        user_id=join_request.user_id,
        user_username=applicant.username,
        user_display_name=applicant.display_name,
        role=join_request.role,
        status=join_request.status,
        message=join_request.message,
        requested_by_user_id=join_request.requested_by_user_id,
        reviewed_by_user_id=join_request.reviewed_by_user_id,
        reviewed_at=join_request.reviewed_at,
        review_note=join_request.review_note,
        created_at=join_request.created_at,
        updated_at=join_request.updated_at,
    )


def _admin_content_draft_read(draft: ContentDraft, author: User) -> AdminContentDraftRead:
    return AdminContentDraftRead(
        id=draft.id,
        author_user_id=draft.author_user_id,
        author_username=author.username,
        author_display_name=author.display_name,
        target_slug=draft.target_slug,
        title=draft.title,
        status=draft.status,
        allow_script=draft.allow_script,
        script_review_status=draft.script_review_status,
        script_reviewed_by_user_id=draft.script_reviewed_by_user_id,
        script_reviewed_at=draft.script_reviewed_at,
        script_review_note=draft.script_review_note,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _admin_content_page_version_read(version: ContentPageVersion) -> AdminContentPageVersionRead:
    return AdminContentPageVersionRead(
        id=version.id,
        page_id=version.page_id,
        slug=version.slug,
        title=str(version.schema_json.get("title", version.slug)),
        status=version.status,
        version=version.version,
        schema_hash=version.schema_hash,
        source_draft_id=version.source_draft_id,
        restored_from_version_id=version.restored_from_version_id,
        published_by_user_id=version.published_by_user_id,
        published_at=version.published_at,
        note=version.note,
        created_at=version.created_at,
    )


def _distinct_count(db: Session, column: Any, *criteria: Any) -> int:
    statement = select(func.count(func.distinct(column)))
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(db.scalar(statement) or 0)


def _sum_int(db: Session, column: Any, *criteria: Any) -> int:
    statement = select(func.coalesce(func.sum(column), 0))
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(db.scalar(statement) or 0)


def _school_assignment_count(db: Session, school_id: int, active_only: bool = False) -> int:
    statement = (
        select(func.count(func.distinct(Assignment.id)))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .where(Course.school_id == school_id)
    )
    if active_only:
        statement = statement.where(Assignment.status == "active", Course.status != "archived")
    return int(db.scalar(statement) or 0)


def _class_course_count(db: Session, class_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(Course.id)))
            .select_from(Course)
            .join(CourseClass, CourseClass.course_id == Course.id)
            .where(
                CourseClass.class_id == class_id,
                CourseClass.status == "active",
                Course.status != "archived",
            )
        )
        or 0
    )


def _class_assignment_count(db: Session, class_id: int, active_only: bool = False) -> int:
    statement = (
        select(func.count(func.distinct(Assignment.id)))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .join(CourseClass, CourseClass.course_id == Course.id)
        .where(CourseClass.class_id == class_id, CourseClass.status == "active")
    )
    if active_only:
        statement = statement.where(Assignment.status == "active", Course.status != "archived")
    return int(db.scalar(statement) or 0)


def _school_submission_count(db: Session, school_id: int, statuses: list[str] | None = None) -> int:
    statement = (
        select(func.count(func.distinct(Submission.id)))
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .where(Course.school_id == school_id)
    )
    if statuses is not None:
        statement = statement.where(Submission.status.in_(statuses))
    return int(db.scalar(statement) or 0)


def _class_average_score_percent(db: Session, class_id: int) -> float:
    score_total, max_score_total = db.execute(
        select(
            func.coalesce(func.sum(Submission.score), 0),
            func.coalesce(func.sum(Assignment.max_score), 0),
        )
        .select_from(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Submission.class_id == class_id, Submission.status == "graded")
    ).one()
    return _percent(float(score_total or 0), float(max_score_total or 0))


def _pending_submission_criteria(
    *,
    school_id: int | None,
    class_id: int | None,
    course_id: int | None,
    assignment_id: int | None,
    student_id: int | None,
    status_filter: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> list[Any]:
    criteria: list[Any] = []
    if status_filter is None:
        criteria.append(Submission.status.in_(PENDING_SUBMISSION_STATUSES))
    else:
        criteria.append(Submission.status == status_filter)
    if school_id is not None:
        criteria.append(Course.school_id == school_id)
    if class_id is not None:
        criteria.append(Submission.class_id == class_id)
    if course_id is not None:
        criteria.append(Course.id == course_id)
    if assignment_id is not None:
        criteria.append(Submission.assignment_id == assignment_id)
    if student_id is not None:
        criteria.append(Submission.student_id == student_id)
    if from_at is not None:
        criteria.append(Submission.submitted_at >= from_at)
    if to_at is not None:
        criteria.append(Submission.submitted_at <= to_at)
    return criteria


def _pending_submission_total(db: Session, criteria: list[Any]) -> int:
    return int(
        db.scalar(
            select(func.count(Submission.id))
            .select_from(Submission)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
            .join(Course, Course.id == CourseUnit.course_id)
            .where(*criteria)
        )
        or 0
    )


def _validate_pending_submission_filters(
    db: Session,
    school_id: int | None,
    class_id: int | None,
    course_id: int | None,
    assignment_id: int | None,
) -> None:
    if school_id is not None:
        _get_school(db, school_id)
    class_group = _get_class(db, class_id) if class_id is not None else None
    course = db.get(Course, course_id) if course_id is not None else None
    if course_id is not None and course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    assignment_course_id = None
    assignment_school_id = None
    if assignment_id is not None:
        assignment_course_id, assignment_school_id = _assignment_course_refs(db, assignment_id)

    if class_group is not None and school_id is not None and class_group.school_id != school_id:
        raise HTTPException(status_code=422, detail="Class does not belong to requested school")
    if course is not None and school_id is not None and course.school_id != school_id:
        raise HTTPException(status_code=422, detail="Course does not belong to requested school")
    if course is not None and class_group is not None and course.school_id != class_group.school_id:
        raise HTTPException(status_code=422, detail="Course does not belong to requested class school")
    if assignment_school_id is not None and school_id is not None and assignment_school_id != school_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested school")
    if assignment_course_id is not None and course_id is not None and assignment_course_id != course_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested course")
    if assignment_school_id is not None and class_group is not None and assignment_school_id != class_group.school_id:
        raise HTTPException(status_code=422, detail="Assignment does not belong to requested class school")


def _assignment_course_refs(db: Session, assignment_id: int) -> tuple[int, int]:
    row = db.execute(
        select(Course.id.label("course_id"), Course.school_id.label("school_id"))
        .select_from(Assignment)
        .join(CourseUnit, CourseUnit.id == Assignment.unit_id)
        .join(Course, Course.id == CourseUnit.course_id)
        .where(Assignment.id == assignment_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return int(row.course_id), int(row.school_id)


def _divide(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _percent(numerator: int | float, denominator: int | float) -> float:
    return round(_divide(numerator, denominator) * 100, 2)


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _enforce_password_strength(password: str, username: str) -> None:
    errors = password_strength_errors(password, username=username)
    if errors:
        raise HTTPException(status_code=422, detail={"password": errors})


def _active_admin_count(db: Session) -> int:
    return _count(db, User, User.role == "admin", User.status == "active")


def _count(db: Session, model, *criteria: Any) -> int:
    statement = select(func.count()).select_from(model)
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(db.scalar(statement) or 0)


def _statement_count(db: Session, statement: Any) -> int:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    return int(db.scalar(count_statement) or 0)


def _next_offset(total: int, offset: int, item_count: int) -> int | None:
    next_offset = offset + item_count
    return next_offset if next_offset < total else None


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _strip_required(value: str) -> str:
    return value.strip()


def _user_snapshot(user: User) -> dict[str, str]:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


def _bug_snapshot(bug: BugRecord) -> dict[str, str | None]:
    return {
        "title": bug.title,
        "category": bug.category,
        "severity": bug.severity,
        "status": bug.status,
        "source": bug.source,
        "evidence": bug.evidence,
        "notes": bug.notes,
    }


def _change_snapshot(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = {
        key: {"from": before.get(key), "to": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
    return {"before": before, "after": after, "changes": changes}
