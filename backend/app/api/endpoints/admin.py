from datetime import datetime
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.endpoints import (
    admin_alerts,
    admin_audit,
    admin_background_tasks,
    admin_content,
    admin_organizations,
    admin_snapshot_tasks,
    admin_users,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    AuditLog,
    Assignment,
    BugExternalSyncOperation,
    BugRecord,
    ClassGroup,
    ClassJoinRequest,
    ContentDraft,
    ContentPageRecord,
    ContentPageVersion,
    Course,
    CourseUnit,
    LearningEvent,
    PointLedger,
    School,
    Submission,
    User,
)
from app.schemas.admin import (
    AdminPendingSubmissionQueue,
    AdminPendingSubmissionRead,
    AdminStats,
    BugRecordCreate,
    BugExternalCommentSyncRequest,
    BugExternalSyncOperationPage,
    BugExternalSyncOperationRead,
    BugExternalSyncRequest,
    BugExternalSyncResponse,
    BugRecordPage,
    BugRecordRead,
    BugRecordUpdate,
)
from app.services.admin_common import (
    PENDING_SUBMISSION_STATUSES,
    change_snapshot as _change_snapshot,
    contains_pattern as _contains_pattern,
    count_rows as _count,
    next_offset as _next_offset,
    require_admin as _require_admin,
    statement_count as _statement_count,
)
from app.services.audit import record_audit_log
from app.services.bug_external_sync import (
    BugExternalSyncError,
    BugExternalSyncResult,
    bug_external_sync_operation_read,
    create_external_issue_for_bug,
    sync_external_issue_comment_for_bug,
    sync_external_issue_status_for_bug,
)
from app.services.external_issue_providers import (
    build_issue_provider_adapter,
    external_issue_sync_posture,
)
from app.services.backend_performance import build_backend_performance_report
from app.services.access_control import (
    require_class_teacher_or_admin_by_id,
    teacher_class_ids,
)
from app.services.text import require_trimmed_text
router = APIRouter()
router.include_router(admin_users.router)
router.include_router(admin_organizations.router)
router.include_router(admin_content.router)
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


@router.get("/performance/report")
def get_backend_performance_report(
    request: Request,
    include_explain: bool = Query(default=True),
    include_benchmark: bool = Query(default=True),
    require_mysql: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_admin(current_user)
    report = build_backend_performance_report(
        db,
        settings=get_settings(),
        include_explain=include_explain,
        include_benchmark=include_benchmark,
        require_mysql=require_mysql,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.performance.report",
        resource_type="backend_performance",
        event_result="success" if report["ok"] else "failure",
        failure_reason=None if report["ok"] else report["status"],
        request=request,
        snapshot={
            "status": report["status"],
            "dialect": report["dialect"],
            "require_mysql": require_mysql,
            "include_explain": include_explain,
            "include_benchmark": include_benchmark,
            "summary": report["summary"],
            "deferred_risk_codes": [item["code"] for item in report["deferred_risks"]],
            "sql_text_returned": False,
            "database_url_returned": False,
        },
    )
    db.commit()
    return report


router.include_router(admin_snapshot_tasks.router)


router.include_router(admin_alerts.router)

router.include_router(admin_background_tasks.router)

router.include_router(admin_audit.router)




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
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    scoped_class_ids: list[int] | None = None
    if current_user.role == "admin":
        _validate_pending_submission_filters(db, school_id, class_id, course_id, assignment_id)
    elif current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Pending submissions require class teacher scope")
    elif status_filter == "graded":
        raise HTTPException(status_code=403, detail="Graded submission queue requires admin role")
    elif class_id is not None:
        require_class_teacher_or_admin_by_id(
            db,
            current_user,
            class_id,
            detail="Pending submissions require class teacher scope",
        )
        scoped_class_ids = [class_id]
    else:
        scoped_class_ids = teacher_class_ids(db, current_user.id)

    criteria = _pending_submission_criteria(
        school_id=school_id,
        class_id=class_id,
        scoped_class_ids=scoped_class_ids,
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
        pattern = _contains_pattern(q)
        statement = statement.where(
            or_(
                BugRecord.title.ilike(pattern, escape="~"),
                BugRecord.category.ilike(pattern, escape="~"),
                BugRecord.source.ilike(pattern, escape="~"),
                BugRecord.external_issue_provider.ilike(pattern, escape="~"),
                BugRecord.external_issue_id.ilike(pattern, escape="~"),
                BugRecord.external_issue_url.ilike(pattern, escape="~"),
                BugRecord.evidence.ilike(pattern, escape="~"),
                BugRecord.notes.ilike(pattern, escape="~"),
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
    title = require_trimmed_text(payload.title, "Bug title is required")
    category = require_trimmed_text(payload.category, "Bug category is required")
    bug = BugRecord(
        title=title,
        category=category,
        severity=payload.severity,
        status=payload.status,
        source=_strip_optional(payload.source),
        external_issue_provider=_normalize_issue_provider(payload.external_issue_provider),
        external_issue_id=_strip_optional(payload.external_issue_id),
        external_issue_url=_strip_optional(payload.external_issue_url),
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
    authoritative_before = _bug_authority_snapshot(bug)
    for field in (
        "title",
        "category",
        "source",
        "external_issue_provider",
        "external_issue_id",
        "external_issue_url",
        "evidence",
        "notes",
    ):
        value = getattr(payload, field)
        if value is not None:
            if field == "title":
                value = require_trimmed_text(value, "Bug title is required")
            elif field == "category":
                value = require_trimmed_text(value, "Bug category is required")
            elif field == "external_issue_provider":
                value = _normalize_issue_provider(value)
            else:
                value = _strip_optional(value)
            setattr(bug, field, value)
    if payload.severity is not None:
        bug.severity = payload.severity
    if payload.status is not None:
        bug.status = payload.status
    if _bug_authority_snapshot(bug) != authoritative_before:
        bug.external_sync_revision += 1

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


@router.get("/bugs/external-sync/posture")
def get_bug_external_sync_posture(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_admin(current_user)
    return external_issue_sync_posture(get_settings())


@router.get(
    "/bugs/{bug_id}/external-sync-operations",
    response_model=BugExternalSyncOperationPage,
)
def list_bug_external_sync_operations(
    bug_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncOperationPage:
    _require_admin(current_user)
    if db.get(BugRecord, bug_id) is None:
        raise HTTPException(status_code=404, detail="Bug record not found")
    statement = (
        select(BugExternalSyncOperation)
        .where(BugExternalSyncOperation.bug_record_id == bug_id)
        .order_by(BugExternalSyncOperation.id.desc())
    )
    total = _statement_count(db, statement)
    operations = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return BugExternalSyncOperationPage(
        items=[BugExternalSyncOperationRead(**bug_external_sync_operation_read(item)) for item in operations],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(operations)),
    )


@router.post("/bugs/{bug_id}/external-sync/create", response_model=BugExternalSyncResponse)
def create_bug_external_issue(
    bug_id: int,
    payload: BugExternalSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="create",
        execute=lambda: create_external_issue_for_bug(
            db,
            bug_id=bug_id,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


@router.post("/bugs/{bug_id}/external-sync/status", response_model=BugExternalSyncResponse)
def sync_bug_external_issue_status(
    bug_id: int,
    payload: BugExternalSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="status",
        execute=lambda: sync_external_issue_status_for_bug(
            db,
            bug_id=bug_id,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


@router.post("/bugs/{bug_id}/external-sync/comments", response_model=BugExternalSyncResponse)
def sync_bug_external_issue_comment(
    bug_id: int,
    payload: BugExternalCommentSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BugExternalSyncResponse:
    _require_admin(current_user)
    if not payload.confirm_external_sync:
        raise HTTPException(status_code=422, detail="confirm_external_sync must be true")
    normalized_comment = payload.comment.strip()
    return _run_bug_external_sync_action(
        db,
        bug_id=bug_id,
        actor=current_user,
        request=request,
        operation="comment",
        audit_context={
            "comment_sha256": sha256(normalized_comment.encode("utf-8")).hexdigest(),
            "comment_length": len(normalized_comment),
        },
        execute=lambda: sync_external_issue_comment_for_bug(
            db,
            bug_id=bug_id,
            comment=normalized_comment,
            settings=get_settings(),
            created_by_user_id=current_user.id,
            adapter_factory=build_issue_provider_adapter,
        ),
    )


def _run_bug_external_sync_action(
    db: Session,
    *,
    bug_id: int,
    actor: User,
    request: Request,
    operation: str,
    execute: Any,
    audit_context: dict[str, Any] | None = None,
) -> BugExternalSyncResponse:
    action = f"admin.bug.external_sync.{operation}"
    try:
        result: BugExternalSyncResult = execute()
    except BugExternalSyncError as exc:
        db.rollback()
        if exc.code == "bug_record_not_found":
            raise HTTPException(status_code=404, detail="Bug record not found") from None
        record_audit_log(
            db,
            actor=actor,
            action=action,
            resource_type="bug_record",
            resource_id=bug_id,
            event_result="failure",
            failure_reason=exc.code,
            request=request,
            snapshot={
                "operation": operation,
                "operation_id": exc.operation_id,
                "retryable": exc.retryable,
                "ambiguous": exc.ambiguous,
                **(audit_context or {}),
            },
        )
        db.commit()
        raise HTTPException(
            status_code=_bug_external_sync_error_status(exc),
            detail={
                "code": exc.code,
                "retryable": exc.retryable,
                "ambiguous": exc.ambiguous,
                "operation_id": exc.operation_id,
                "posture": external_issue_sync_posture(get_settings()),
            },
        ) from None
    operation_read = bug_external_sync_operation_read(result.operation)
    record_audit_log(
        db,
        actor=actor,
        action=action,
        resource_type="bug_record",
        resource_id=bug_id,
        event_result="success",
        request=request,
        snapshot={
            "operation": operation,
            "operation_id": result.operation.id,
            "operation_status": result.operation.status,
            "provider": result.operation.provider,
            "external_issue_id": result.operation.external_issue_id,
            "external_state": result.operation.external_state,
            "recovered": result.recovered,
            **(audit_context or {}),
        },
    )
    db.commit()
    db.refresh(result.bug)
    return BugExternalSyncResponse(
        bug=result.bug,
        operation=BugExternalSyncOperationRead(**operation_read),
        recovered=result.recovered,
        posture=external_issue_sync_posture(get_settings()),
    )


def _bug_external_sync_error_status(error: BugExternalSyncError) -> int:
    if error.code in {
        "external_issue_comment_empty",
        "external_issue_comment_sensitive",
        "external_issue_title_sensitive",
    }:
        return 422
    if error.ambiguous or error.code in {
        "external_issue_already_bound",
        "external_issue_binding_invalid",
        "external_issue_not_bound",
        "external_issue_provider_mismatch",
        "external_issue_sync_ambiguous",
        "external_issue_sync_disabled",
        "external_issue_sync_not_configured",
    }:
        return 409
    return 502


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


def _pending_submission_criteria(
    *,
    school_id: int | None,
    class_id: int | None,
    scoped_class_ids: list[int] | None = None,
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
    if scoped_class_ids is not None:
        criteria.append(Submission.class_id.in_(scoped_class_ids))
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






def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalize_issue_provider(value: str | None) -> str | None:
    normalized = _strip_optional(value)
    if normalized is None:
        return None
    return normalized.lower()


def _bug_snapshot(bug: BugRecord) -> dict[str, Any]:
    return {
        "title": bug.title,
        "category": bug.category,
        "severity": bug.severity,
        "status": bug.status,
        "source": bug.source,
        "external_issue_provider": bug.external_issue_provider,
        "external_issue_id": bug.external_issue_id,
        "external_issue_url": bug.external_issue_url,
        "external_issue_state": bug.external_issue_state,
        "external_issue_synced_at": bug.external_issue_synced_at.isoformat()
        if bug.external_issue_synced_at is not None
        else None,
        "external_sync_revision": bug.external_sync_revision,
        "evidence": bug.evidence,
        "notes": bug.notes,
    }


def _bug_authority_snapshot(bug: BugRecord) -> tuple[str | None, ...]:
    return (
        bug.title,
        bug.category,
        bug.severity,
        bug.status,
        bug.source,
        bug.external_issue_provider,
        bug.external_issue_id,
        bug.external_issue_url,
    )
