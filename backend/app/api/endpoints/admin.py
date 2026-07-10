import csv
import io
import json
import re
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import get_settings
from app.core.security import hash_password, password_strength_errors
from app.db.session import get_db
from app.models import (
    AdminAlertOutboxDispatchPlan,
    AdminAlertOutboxEntry,
    AuthSession,
    AuditLog,
    Assignment,
    AssignmentClassPolicy,
    BackgroundTask,
    BackgroundTaskAttempt,
    BugExternalSyncOperation,
    BugRecord,
    ClassGroup,
    ClassJoinRequest,
    ClassMembership,
    ContentDraft,
    ContentPageRecord,
    ContentPageVersion,
    ContentScriptAsset,
    ContentScriptAssetScanRun,
    Course,
    CourseClass,
    CourseUnit,
    LearningEvent,
    LoginAttempt,
    KnowledgeSnapshotRun,
    PointLedger,
    School,
    SchoolMembership,
    Submission,
    User,
)
from app.schemas.admin import (
    AdminBootstrapRequest,
    AdminClassJoinRequestPage,
    AdminClassJoinRequestRead,
    AdminClassJoinRequestReview,
    AdminClassPage,
    AdminClassStats,
    AdminContentPagePage,
    AdminContentPageRead,
    AdminContentScriptAssetAuditIssueRead,
    AdminContentScriptAssetAuditReport,
    AdminContentScriptAssetPage,
    AdminContentScriptAssetRead,
    AdminContentScriptAssetScanAlertCandidate,
    AdminContentScriptAssetScanAlertOutboxRequest,
    AdminContentScriptAssetScanAlertReport,
    AdminContentScriptAssetScanHealthItem,
    AdminContentScriptAssetScanHealthReport,
    AdminContentScriptAssetScanQueueItem,
    AdminContentScriptAssetScanQueueReport,
    AdminContentScriptAssetScanRunPage,
    AdminContentScriptAssetScanRunRead,
    AdminContentScriptAssetScanRunStatusBucket,
    AdminContentScriptAssetRemoteDriftIssueRead,
    AdminContentScriptAssetRemoteDriftReport,
    AdminContentScriptAssetRemoteDriftScanRequest,
    AdminContentPageVersionDiff,
    AdminContentPageVersionDiffItem,
    AdminContentPageVersionSemanticDiff,
    AdminContentPageVersionSemanticFieldChange,
    AdminContentPageVersionSemanticSectionChange,
    AdminContentPageVersionSemanticSourceChange,
    AdminContentScriptHostPolicyPage,
    AdminContentScriptHostPolicyRead,
    AdminContentScriptHostPolicyUpdate,
    AdminContentPageVersionPage,
    AdminContentPageVersionRead,
    AdminKnowledgeSnapshotRunHealthReport,
    AdminKnowledgeSnapshotRunHealthItem,
    AdminKnowledgeSnapshotRunAlertCandidate,
    AdminKnowledgeSnapshotRunAlertReport,
    AdminKnowledgeSnapshotRunAlertOutboxRequest,
    AdminKnowledgeSnapshotRunPage,
    AdminKnowledgeSnapshotRunQueueItem,
    AdminKnowledgeSnapshotRunQueueReport,
    AdminKnowledgeSnapshotRunRead,
    AdminKnowledgeSnapshotRunRequeueRequest,
    AdminKnowledgeSnapshotRunStatusBucket,
    AdminContentDraftPage,
    AdminContentDraftRead,
    AdminPendingSubmissionQueue,
    AdminPendingSubmissionRead,
    AdminSchoolPage,
    AdminSchoolStats,
    AdminStats,
    AdminUserPage,
    AdminUserPasswordReset,
    AdminUserPasswordResetResponse,
    AdminUserRead,
    AdminUserUpdate,
    AdminAlertOutboxBulkReviewRequest,
    AdminAlertOutboxBulkReviewResponse,
    AdminAlertOutboxDispatchDryRunItem,
    AdminAlertOutboxDispatchDryRunReport,
    AdminAlertOutboxDispatchDryRunRequest,
    AdminAlertOutboxDispatchPlanCreateRequest,
    AdminAlertOutboxDispatchPlanPage,
    AdminAlertOutboxDispatchPlanRead,
    AdminAlertOutboxDispatchPlanValidateRequest,
    AdminAlertOutboxDispatchPlanValidationReport,
    AdminAlertOutboxExternalDispatchItem,
    AdminAlertOutboxExternalDispatchReport,
    AdminAlertOutboxExternalDispatchRequest,
    AdminAlertOutboxEntryRead,
    AdminAlertOutboxPage,
    AdminAlertOutboxQueueItem,
    AdminAlertOutboxQueueReport,
    AdminAlertOutboxStatusBucket,
    AdminAlertOutboxReviewRequest,
    AdminAlertOutboxWriteResponse,
    AdminBackgroundTaskActionRequest,
    AdminBackgroundTaskAttemptRead,
    AdminBackgroundTaskEnqueueRequest,
    AdminBackgroundTaskPage,
    AdminBackgroundTaskQueueReport,
    AdminBackgroundTaskRead,
    AdminContentScriptScanTaskEnqueueRequest,
    AdminKnowledgeSnapshotTaskEnqueueRequest,
    AuditLogExport,
    AuditLogExportItem,
    AuditLogChainVerification,
    AuditLogFrequencyCandidate,
    AuditLogFrequencyReport,
    AuditLogPage,
    AuditLogRead,
    AuditLogReport,
    AuditLogReportBucket,
    AuditLogRetentionPlan,
    AuditLogRetentionPolicy,
    AuditLogRetentionSummary,
    AuditLogActionReport,
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
from app.services.audit import record_audit_log
from app.services.bug_external_sync import (
    BugExternalSyncError,
    BugExternalSyncResult,
    bug_external_sync_operation_read,
    create_external_issue_for_bug,
    sync_external_issue_comment_for_bug,
    sync_external_issue_status_for_bug,
)
from app.services.assignment_policies import (
    assignment_class_effective_status_expression,
    assignment_class_is_assigned_expression,
)
from app.services.admin_alert_outbox import (
    admin_alert_outbox_write_snapshot,
    enqueue_content_script_remote_drift_alert_outbox,
    enqueue_knowledge_snapshot_alert_outbox,
)
from app.services.alert_delivery import (
    AlertDeliveryError,
    alert_delivery_posture,
    build_alert_delivery_adapter,
    build_alert_delivery_envelope,
)
from app.services.background_tasks import (
    cancel_background_task,
    enqueue_background_task,
    retry_background_task,
)
from app.services.external_issue_providers import (
    build_issue_provider_adapter,
    external_issue_sync_posture,
)
from app.services.backend_performance import build_backend_performance_report
from app.services.access_control import (
    require_class_teacher_or_admin_by_id,
    require_school_teacher_or_admin,
    teacher_class_ids,
)
from app.services.audit_chain import verify_audit_log_chain
from app.services.class_join_requests import (
    apply_class_join_request_review,
    normalize_class_role,
    normalize_join_request_status,
)
from app.services.text import require_trimmed_text
from app.services.users import find_user_by_normalized_username, require_normalized_username
from app.services.knowledge_snapshot_runs import (
    cancel_knowledge_snapshot_run,
    requeue_knowledge_snapshot_run,
    snapshot_run_key,
    snapshot_window,
)
from app.services.knowledge_snapshot_leases import (
    knowledge_snapshot_lease_has_any_field,
    knowledge_snapshot_lease_is_complete,
    knowledge_snapshot_lease_is_expired,
    knowledge_snapshot_lease_missing_fields,
)
from app.services.knowledge_snapshot_scheduler import (
    SnapshotScheduleConfig,
    SnapshotScheduleJob,
    due_snapshot_jobs,
    should_run_snapshot_job,
)
from app.services.content_script_assets import (
    ContentScriptAssetMirrorAuditIssue,
    ContentScriptAssetMirrorAuditReport,
    ContentScriptAssetRemoteDriftIssue,
    ContentScriptAssetRemoteDriftReport,
    audit_current_content_script_asset_mirrors,
)
from app.services.content_script_asset_scan_runs import (
    ContentScriptAssetScanAlertCandidate as ContentScriptAssetScanAlertCandidateRow,
    ContentScriptAssetScanAlertReport as ContentScriptAssetScanAlertReportRow,
    ContentScriptAssetScanHealthItem as ContentScriptAssetScanHealthItemRow,
    ContentScriptAssetScanHealthReport as ContentScriptAssetScanHealthReportRow,
    ContentScriptAssetScanQueueItem as ContentScriptAssetScanQueueItemRow,
    ContentScriptAssetScanQueueReport as ContentScriptAssetScanQueueReportRow,
    build_content_script_asset_scan_alert_report,
    build_content_script_asset_scan_health_report,
    build_content_script_asset_scan_queue_report,
    content_script_asset_scan_alert_snapshot,
    content_script_asset_scan_health_snapshot,
    content_script_asset_scan_queue_snapshot,
    content_script_asset_scan_run_snapshot,
    list_content_script_asset_scan_runs,
    run_content_script_asset_remote_drift_scan,
)
from app.services.content_script_host_policies import (
    ContentScriptHostPolicyRow,
    content_script_host_policy_snapshot,
    list_content_script_host_policy_rows,
    normalize_content_script_source_host,
    upsert_content_script_host_policy,
)


router = APIRouter()
PENDING_SUBMISSION_STATUSES = ["submitted", "returned"]
_DIFF_MISSING = object()
_CONTENT_METADATA_FIELDS = ("slug", "galaxy", "subject", "title", "layout", "status", "version", "summary")
_CONTENT_SECTION_FIELDS = ("sectionId", "type", "title", "summary", "experimentId", "questionSetId")
_CONTENT_COURSE_UNIT_FIELDS = ("courseId", "unitId", "order", "title")
_CONTENT_SOURCE_FIELDS = ("sourceId", "label", "url")
_CONTENT_DIFF_SENSITIVE_FIELD_TOKENS = (
    "authorization",
    "apikey",
    "api_key",
    "accesskey",
    "access_key",
    "credential",
    "crossorigin",
    "integrity",
    "password",
    "privatekey",
    "private_key",
    "sandbox",
    "script",
    "secret",
    "token",
)
_AUDIT_LOG_CSV_FIELDS = (
    "id",
    "actor_user_id",
    "actor_role",
    "action",
    "resource",
    "resource_type",
    "resource_id",
    "school_id",
    "class_id",
    "event_result",
    "failure_reason",
    "request_id",
    "client_ip_hash",
    "user_agent",
    "request_method",
    "request_path",
    "prev_hash",
    "current_hash",
    "snapshot_json",
    "created_at",
)
_AUDIT_LOG_REPORT_CSV_FIELDS = ("section", "key", "total", "success", "failure", "other", "latest_at")


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

    username = require_normalized_username(payload.username, min_length=3)
    display_name = require_trimmed_text(payload.display_name, "Display name is required")
    _enforce_password_strength(payload.password, username)
    existing = find_user_by_normalized_username(db, username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=username,
        normalized_username=username,
        display_name=display_name,
        role="admin",
        status="active",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
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
        user.display_name = require_trimmed_text(payload.display_name, "Display name is required")
    if payload.role is not None:
        user.role = payload.role
    if payload.status is not None:
        user.status = payload.status

    after = _user_snapshot(user)
    snapshot = _change_snapshot(before, after)
    revoked_sessions = _revoke_user_sessions(db, user) if payload.status == "disabled" else 0
    if revoked_sessions:
        snapshot["revoked_sessions"] = revoked_sessions
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.update",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot=snapshot,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/password-reset", response_model=AdminUserPasswordResetResponse)
def reset_user_password(
    user_id: int,
    payload: AdminUserPasswordReset,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUserPasswordResetResponse:
    _require_admin(current_user)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    _enforce_password_strength(payload.password, user.username)
    user.password_hash = hash_password(payload.password)
    cleared_login_attempt = _clear_user_login_attempt(db, user)
    revoked_sessions = _revoke_user_sessions(db, user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.password_reset",
        resource_type="user",
        resource_id=user.id,
        event_result="success",
        request=request,
        snapshot={
            "user": _user_snapshot(user),
            "revoked_sessions": revoked_sessions,
            "cleared_login_attempt": cleared_login_attempt,
        },
    )
    db.commit()
    return AdminUserPasswordResetResponse(
        user_id=user.id,
        revoked_sessions=revoked_sessions,
        cleared_login_attempt=cleared_login_attempt,
    )


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
    school = require_school_teacher_or_admin(db, current_user, school_id)
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
    class_group = require_class_teacher_or_admin_by_id(db, current_user, class_id)
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
    statement = select(ContentPageRecord).order_by(ContentPageRecord.slug)
    if status_filter is not None:
        statement = statement.where(ContentPageRecord.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = _contains_pattern(q)
        searchable_fields = [
            ContentPageRecord.slug,
            _content_page_schema_text("title"),
            _content_page_schema_text("galaxy"),
            _content_page_schema_text("subject"),
            _content_page_schema_text("layout"),
        ]
        statement = statement.where(or_(*(field.ilike(pattern, escape="~") for field in searchable_fields)))

    total = _statement_count(db, statement)
    records = list(db.scalars(statement.offset(offset).limit(limit)).all())
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
            schema_hash=record.schema_hash,
            current_version_id=record.current_version_id,
            published_by_user_id=record.published_by_user_id,
            published_at=record.published_at,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    return AdminContentPagePage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/content/drafts", response_model=AdminContentDraftPage)
def list_admin_content_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    script_review_status: str | None = Query(default=None),
    script_risk_level: str | None = Query(default=None),
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
    if script_risk_level is not None:
        statement = statement.where(ContentDraft.script_risk_level == script_risk_level.strip().lower())
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


@router.get("/content/script-assets", response_model=AdminContentScriptAssetPage)
def list_admin_content_script_assets(
    request: Request,
    slug: str | None = Query(default=None, max_length=180),
    source_host: str | None = Query(default=None, max_length=255),
    sandbox_id: str | None = Query(default=None, max_length=32),
    page_id: int | None = Query(default=None, ge=1),
    page_version_id: int | None = Query(default=None, ge=1),
    published_by_user_id: int | None = Query(default=None, ge=1),
    policy_version: str | None = Query(default=None, max_length=64),
    policy_context_hash: str | None = Query(default=None, min_length=64, max_length=64),
    asset_sha256: str | None = Query(default=None, min_length=64, max_length=64),
    reference_value_sha256: str | None = Query(default=None, min_length=64, max_length=64),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")

    filters = _content_script_asset_filters(
        slug=slug,
        source_host=source_host,
        sandbox_id=sandbox_id,
        page_id=page_id,
        page_version_id=page_version_id,
        published_by_user_id=published_by_user_id,
        policy_version=policy_version,
        policy_context_hash=policy_context_hash,
        asset_sha256=asset_sha256,
        reference_value_sha256=reference_value_sha256,
        from_at=from_at,
        to_at=to_at,
        q=q,
    )
    statement = select(ContentScriptAsset).order_by(
        ContentScriptAsset.published_at.desc(),
        ContentScriptAsset.id.desc(),
    )
    statement = _apply_content_script_asset_filters(statement, filters)
    total = _statement_count(db, statement)
    assets = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_content_script_asset_read(asset) for asset in assets]

    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.inventory",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=_content_script_asset_inventory_snapshot(
            assets,
            filters=filters,
            total=total,
            limit=limit,
            offset=offset,
        ),
    )
    db.commit()
    return AdminContentScriptAssetPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/content/script-host-policies", response_model=AdminContentScriptHostPolicyPage)
def list_admin_content_script_host_policies(
    request: Request,
    source_host: str | None = Query(default=None, max_length=255),
    policy_status: Literal["trusted", "watch", "blocked", "unreviewed"] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptHostPolicyPage:
    _require_admin(current_user)
    try:
        page = list_content_script_host_policy_rows(
            db,
            allowed_hosts=get_settings().content_script_allowed_host_list,
            source_host=source_host,
            status=policy_status,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = [_admin_content_script_host_policy_read(item) for item in page.items]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_host_policy.list",
        resource_type="content_script_host_policy",
        event_result="success",
        request=request,
        snapshot={
            "filters": _content_script_host_policy_filters(
                source_host=source_host,
                policy_status=policy_status,
                q=q,
            ),
            "total": page.total,
            "limit": limit,
            "offset": offset,
            "item_count": len(items),
            "capabilities": {
                "mutation": False,
                "allows_host": False,
                "blocks_publish_when_status_blocked": True,
            },
        },
    )
    db.commit()
    return AdminContentScriptHostPolicyPage(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(page.total, offset, len(items)),
    )


@router.patch("/content/script-host-policies/{source_host}", response_model=AdminContentScriptHostPolicyRead)
def update_admin_content_script_host_policy(
    request: Request,
    source_host: str = Path(..., min_length=1, max_length=255),
    payload: AdminContentScriptHostPolicyUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptHostPolicyRead:
    _require_admin(current_user)
    try:
        normalized_host = normalize_content_script_source_host(source_host)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    before_page = list_content_script_host_policy_rows(
        db,
        allowed_hosts=get_settings().content_script_allowed_host_list,
        source_host=normalized_host,
        limit=1,
        offset=0,
    )
    before = _admin_content_script_host_policy_read(before_page.items[0]).model_dump(mode="json") if before_page.items else None
    try:
        policy = upsert_content_script_host_policy(
            db,
            source_host=normalized_host,
            status=payload.status,
            reason=payload.reason,
            reviewer=current_user,
        )
        db.flush()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_page = list_content_script_host_policy_rows(
        db,
        allowed_hosts=get_settings().content_script_allowed_host_list,
        source_host=normalized_host,
        limit=1,
        offset=0,
    )
    after = _admin_content_script_host_policy_read(after_page.items[0])
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_host_policy.update",
        resource_type="content_script_host_policy",
        resource_id=policy.id,
        event_result="success",
        request=request,
        snapshot={
            "before": before,
            "after": after.model_dump(mode="json"),
            "policy": content_script_host_policy_snapshot(policy),
            "capabilities": {
                "allows_host": False,
                "blocks_publish_when_status_blocked": policy.status == "blocked",
                "external_network": False,
                "mutation": True,
            },
        },
    )
    db.commit()
    db.refresh(policy)
    return after


@router.get("/content/script-assets/mirror-audit", response_model=AdminContentScriptAssetAuditReport)
def read_admin_content_script_asset_audit(
    request: Request,
    slug: str | None = Query(default=None, max_length=180),
    source_host: str | None = Query(default=None, max_length=255),
    issue_code: str | None = Query(default=None, max_length=80),
    severity: Literal["critical", "warning", "info"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetAuditReport:
    _require_admin(current_user)
    report = audit_current_content_script_asset_mirrors(
        db,
        slug=slug,
        source_host=source_host,
        issue_code=issue_code,
        severity=severity,
    )
    issues = report.issues[offset : offset + limit]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.mirror_audit",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=_content_script_asset_mirror_audit_snapshot(
            report,
            slug=slug,
            source_host=source_host,
            issue_code=issue_code,
            severity=severity,
            limit=limit,
            offset=offset,
            item_count=len(issues),
        ),
    )
    db.commit()
    return AdminContentScriptAssetAuditReport(
        generated_at=report.generated_at,
        total_pages_scanned=report.total_pages_scanned,
        total_external_references=report.total_external_references,
        total_issues=report.total_issues,
        issue_counts_by_code=report.issue_counts_by_code,
        issue_counts_by_severity=report.issue_counts_by_severity,
        items=[_admin_content_script_asset_audit_issue_read(issue) for issue in issues],
        limit=limit,
        offset=offset,
        next_offset=_next_offset(report.total_issues, offset, len(issues)),
    )


@router.get("/content/script-assets/remote-drift-scan-runs", response_model=AdminContentScriptAssetScanRunPage)
def list_admin_content_script_asset_remote_drift_scan_runs(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanRunPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    page = list_content_script_asset_scan_runs(
        db,
        status=status_filter,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
        offset=offset,
    )
    items = [_admin_content_script_asset_scan_run_read(run) for run in page.items]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.list",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot={
            "filters": _content_script_asset_scan_run_filters(
                status_filter=status_filter,
                trigger_source=trigger_source,
                alert_status=alert_status,
                from_at=from_at,
                to_at=to_at,
            ),
            "total": page.total,
            "limit": limit,
            "offset": offset,
            "item_count": len(items),
            "capabilities": {
                "mutation": False,
                "external_network": False,
                "external_alerts": False,
                "automatic_actions": False,
            },
        },
    )
    db.commit()
    return AdminContentScriptAssetScanRunPage(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(page.total, offset, len(items)),
    )


@router.get(
    "/content/script-assets/remote-drift-scan-runs/health",
    response_model=AdminContentScriptAssetScanHealthReport,
)
def read_admin_content_script_asset_remote_drift_scan_run_health(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    problem_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanHealthReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    report = build_content_script_asset_scan_health_report(
        db,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=problem_limit,
        generated_at=now_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.health_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_health_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_health_report(report)


@router.get(
    "/content/script-assets/remote-drift-scan-runs/queue",
    response_model=AdminContentScriptAssetScanQueueReport,
)
def read_admin_content_script_asset_remote_drift_scan_run_queue(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanQueueReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    report = build_content_script_asset_scan_queue_report(
        db,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        generated_at=now_at,
        scheduler_enabled=settings.content_script_remote_drift_scheduler_enabled,
        scheduler_interval_seconds=settings.content_script_remote_drift_scheduler_interval_seconds,
        scheduler_lease_seconds=settings.content_script_remote_drift_scheduler_lease_seconds,
        scheduler_scan_limit=settings.content_script_remote_drift_scheduler_scan_limit,
        scheduler_source_host=settings.content_script_remote_drift_scheduler_source_host,
        scheduler_slug=settings.content_script_remote_drift_scheduler_slug,
        scheduler_actor_user_id=settings.content_script_remote_drift_scheduler_actor_user_id,
        item_limit=item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.queue_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_queue_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_queue_report(report)


@router.get("/content/script-assets/remote-drift-alerts", response_model=AdminContentScriptAssetScanAlertReport)
def read_admin_content_script_asset_remote_drift_alerts(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    recent_run_limit: int = Query(default=20, ge=1, le=100),
    candidate_limit: int = Query(default=20, ge=0, le=100),
    now_at: datetime | None = Query(default=None, alias="now"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanAlertReport:
    _require_admin(current_user)
    report = build_content_script_asset_scan_alert_report(
        db,
        recent_run_limit=recent_run_limit,
        candidate_limit=candidate_limit,
        generated_at=now_at,
        trigger_source=trigger_source,
        alert_status=alert_status,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_alert_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_alert_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_alert_report(report)


@router.post("/content/script-assets/remote-drift-alerts/outbox", response_model=AdminAlertOutboxWriteResponse)
def enqueue_admin_content_script_asset_remote_drift_alert_outbox(
    request_body: AdminContentScriptAssetScanAlertOutboxRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxWriteResponse:
    _require_admin(current_user)
    if not request_body.confirm_observe_only:
        raise HTTPException(status_code=422, detail="confirm_observe_only must be true")
    report = build_content_script_asset_scan_alert_report(
        db,
        recent_run_limit=request_body.recent_run_limit,
        candidate_limit=request_body.candidate_limit,
        generated_at=request_body.now_at,
        trigger_source=request_body.trigger_source,
        alert_status=request_body.alert_status,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
    )
    write_result = enqueue_content_script_remote_drift_alert_outbox(
        db,
        report=report,
        actor=current_user,
        status=request_body.status,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.content_script_asset_remote_drift.enqueue",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=admin_alert_outbox_write_snapshot(write_result),
    )
    db.commit()
    for entry in write_result.entries:
        db.refresh(entry)
    return _admin_alert_outbox_write_response(write_result)


@router.post("/content/script-assets/remote-drift-scan", response_model=AdminContentScriptAssetRemoteDriftReport)
def scan_admin_content_script_asset_remote_drift(
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetRemoteDriftReport:
    _require_admin(current_user)
    if not request_body.confirm_external_network:
        raise HTTPException(status_code=422, detail="confirm_external_network must be true")
    execution = run_content_script_asset_remote_drift_scan(
        creator=current_user,
        db=db,
        trigger_source="manual",
        slug=request_body.slug,
        source_host=request_body.source_host,
        issue_code=request_body.issue_code,
        severity=request_body.severity,
        scan_limit=request_body.limit,
        scan_offset=request_body.offset,
    )
    report = execution.report
    scan_run = execution.run
    audit_snapshot = _content_script_asset_remote_drift_scan_snapshot(
        report,
        request_body=request_body,
        item_count=len(report.issues),
    )
    audit_snapshot["scan_run"] = content_script_asset_scan_run_snapshot(scan_run)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=audit_snapshot,
    )
    db.commit()
    return AdminContentScriptAssetRemoteDriftReport(
        scan_run_id=scan_run.id,
        scan_run_key=scan_run.run_key,
        generated_at=report.generated_at,
        total_pages_scanned=report.total_pages_scanned,
        total_external_references=report.total_external_references,
        total_scanned_references=report.total_scanned_references,
        total_remote_fetches=report.total_remote_fetches,
        total_skipped_references=report.total_skipped_references,
        total_issues=report.total_issues,
        issue_counts_by_code=report.issue_counts_by_code,
        issue_counts_by_severity=report.issue_counts_by_severity,
        items=[_admin_content_script_asset_remote_drift_issue_read(issue) for issue in report.issues],
        limit=request_body.limit,
        offset=request_body.offset,
        next_offset=_next_offset(
            report.total_external_references,
            request_body.offset,
            report.total_scanned_references,
        ),
    )


@router.get("/content/page-versions/{version_id}/diff", response_model=AdminContentPageVersionDiff)
def read_admin_content_page_version_diff(
    version_id: int,
    base_version_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPageVersionDiff:
    _require_admin(current_user)
    target_version = db.get(ContentPageVersion, version_id)
    if target_version is None:
        raise HTTPException(status_code=404, detail="Content page version not found")

    if base_version_id is None:
        base_version = _linked_previous_content_page_version(db, target_version) or target_version
    else:
        base_version = db.get(ContentPageVersion, base_version_id)
    if base_version is None:
        raise HTTPException(status_code=404, detail="Base content page version not found")
    if base_version.slug != target_version.slug:
        raise HTTPException(status_code=422, detail="Content page versions must share the same slug")

    changes = _content_schema_diff(base_version.schema_json, target_version.schema_json)
    semantic = _content_schema_semantic_diff(base_version.schema_json, target_version.schema_json)
    return AdminContentPageVersionDiff(
        slug=target_version.slug,
        base_version_id=base_version.id,
        base_version=base_version.version,
        base_schema_hash=base_version.schema_hash,
        target_version_id=target_version.id,
        target_version=target_version.version,
        target_schema_hash=target_version.schema_hash,
        change_count=len(changes),
        changes=changes,
        semantic=semantic,
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


@router.get("/knowledge-snapshot-runs", response_model=AdminKnowledgeSnapshotRunPage)
def list_knowledge_snapshot_runs(
    granularity: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(KnowledgeSnapshotRun).order_by(
        KnowledgeSnapshotRun.started_at.desc(),
        KnowledgeSnapshotRun.id.desc(),
    )
    if granularity is not None:
        statement = statement.where(KnowledgeSnapshotRun.granularity == granularity.strip().lower())
    if status_filter is not None:
        statement = statement.where(KnowledgeSnapshotRun.status == status_filter.strip().lower())
    if trigger_source is not None:
        statement = statement.where(KnowledgeSnapshotRun.trigger_source == trigger_source.strip().lower())
    if from_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at >= from_at)
    if to_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at <= to_at)
    total = _statement_count(db, statement)
    runs = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminKnowledgeSnapshotRunPage(
        items=[_admin_knowledge_snapshot_run_read(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(runs)),
    )


@router.get("/knowledge-snapshot-runs/health", response_model=AdminKnowledgeSnapshotRunHealthReport)
def read_knowledge_snapshot_run_health(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    problem_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunHealthReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=problem_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.health_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_health_snapshot(report),
    )
    db.commit()
    return report


@router.get("/knowledge-snapshot-runs/queue", response_model=AdminKnowledgeSnapshotRunQueueReport)
def read_knowledge_snapshot_run_queue(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunQueueReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters["now"] = now_at.isoformat() if now_at is not None else None
    report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=item_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.queue_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_queue_snapshot(report),
    )
    db.commit()
    return report


@router.get("/knowledge-snapshot-runs/alerts", response_model=AdminKnowledgeSnapshotRunAlertReport)
def read_knowledge_snapshot_run_alerts(
    request: Request,
    granularity: str | None = Query(default=None),
    trigger_source: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    candidate_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunAlertReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    generated_at = now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=granularity,
        trigger_source=trigger_source,
        from_at=from_at,
        to_at=to_at,
    )
    filters["now"] = now_at.isoformat() if now_at is not None else None
    health_report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=100,
        generated_at=generated_at,
    )
    queue_report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=100,
        generated_at=generated_at,
    )
    report = _knowledge_snapshot_run_alert_report(
        health_report=health_report,
        queue_report=queue_report,
        candidate_limit=candidate_limit,
        generated_at=generated_at,
        filters=filters,
        lease_expiring_seconds=lease_expiring_seconds,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.alert_report",
        resource_type="knowledge_snapshot_run",
        event_result="success",
        request=request,
        snapshot=_knowledge_snapshot_run_alert_snapshot(report),
    )
    db.commit()
    return report


@router.post("/knowledge-snapshot-runs/alerts/outbox", response_model=AdminAlertOutboxWriteResponse)
def enqueue_knowledge_snapshot_run_alert_outbox(
    request_body: AdminKnowledgeSnapshotRunAlertOutboxRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxWriteResponse:
    _require_admin(current_user)
    if not request_body.confirm_observe_only:
        raise HTTPException(status_code=422, detail="confirm_observe_only must be true")
    if (
        request_body.from_at is not None
        and request_body.to_at is not None
        and request_body.from_at > request_body.to_at
    ):
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    settings = get_settings()
    generated_at = request_body.now_at or datetime.now(UTC)
    statement = _knowledge_snapshot_run_statement(
        granularity=request_body.granularity,
        trigger_source=request_body.trigger_source,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
    )
    filters = _knowledge_snapshot_run_filters(
        granularity=request_body.granularity,
        trigger_source=request_body.trigger_source,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
    )
    filters["now"] = request_body.now_at.isoformat() if request_body.now_at is not None else None
    health_report = _knowledge_snapshot_run_health_report(
        db,
        statement=statement,
        filters=filters,
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        lease_expiring_seconds=request_body.lease_expiring_seconds,
        problem_limit=100,
        generated_at=generated_at,
    )
    queue_report = _knowledge_snapshot_run_queue_report(
        db,
        statement=statement,
        filters=filters,
        schedule_config=_knowledge_snapshot_schedule_config(settings),
        retry_attempts=settings.knowledge_snapshot_retry_attempts,
        lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
        item_limit=100,
        generated_at=generated_at,
    )
    alert_report = _knowledge_snapshot_run_alert_report(
        health_report=health_report,
        queue_report=queue_report,
        candidate_limit=request_body.candidate_limit,
        generated_at=generated_at,
        filters=filters,
        lease_expiring_seconds=request_body.lease_expiring_seconds,
    )
    write_result = enqueue_knowledge_snapshot_alert_outbox(
        db,
        report=alert_report,
        actor=current_user,
        status=request_body.status,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.knowledge_snapshot_run.enqueue",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=admin_alert_outbox_write_snapshot(write_result),
    )
    db.commit()
    for entry in write_result.entries:
        db.refresh(entry)
    return _admin_alert_outbox_write_response(write_result)


@router.post("/knowledge-snapshot-runs/{run_id}/cancel", response_model=AdminKnowledgeSnapshotRunRead)
def cancel_admin_knowledge_snapshot_run(
    run_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunRead:
    _require_admin(current_user)
    run = db.get(KnowledgeSnapshotRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Knowledge snapshot run not found")
    previous_status = run.status
    try:
        cancel_knowledge_snapshot_run(run, cancelled_by_user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=409, detail="Knowledge snapshot run cannot be cancelled")
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.cancel",
        resource_type="knowledge_snapshot_run",
        resource_id=run.id,
        event_result="success",
        request=request,
        snapshot={
            "run_id": run.id,
            "run_key": run.run_key,
            "granularity": run.granularity,
            "trigger_source": run.trigger_source,
            "previous_status": previous_status,
            "status": run.status,
            "cleared_lease": True,
        },
    )
    db.commit()
    db.refresh(run)
    return _admin_knowledge_snapshot_run_read(run)


@router.post("/knowledge-snapshot-runs/{run_id}/requeue", response_model=AdminKnowledgeSnapshotRunRead)
def requeue_admin_knowledge_snapshot_run(
    run_id: int,
    payload: AdminKnowledgeSnapshotRunRequeueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminKnowledgeSnapshotRunRead:
    _require_admin(current_user)
    run = db.get(KnowledgeSnapshotRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Knowledge snapshot run not found")
    previous_status = run.status
    had_scheduler_lease = any(
        (
            run.scheduler_lease_owner,
            run.scheduler_lease_token,
            run.scheduler_lease_expires_at,
            run.scheduler_heartbeat_at,
        )
    )
    settings = get_settings()
    try:
        requeue_knowledge_snapshot_run(
            run,
            requeued_by_user_id=current_user.id,
            lease_seconds=settings.knowledge_snapshot_scheduler_lease_seconds,
            reason=payload.reason,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Knowledge snapshot run cannot be requeued")
    record_audit_log(
        db,
        actor=current_user,
        action="admin.knowledge_snapshot_run.requeue",
        resource_type="knowledge_snapshot_run",
        resource_id=run.id,
        event_result="success",
        request=request,
        snapshot={
            "run_id": run.id,
            "run_key": run.run_key,
            "granularity": run.granularity,
            "trigger_source": run.trigger_source,
            "previous_status": previous_status,
            "status": run.status,
            "attempt_count": run.attempt_count,
            "cleared_lease": previous_status != "pending" and had_scheduler_lease,
            "reason_provided": bool(payload.reason and payload.reason.strip()),
        },
    )
    db.commit()
    db.refresh(run)
    return _admin_knowledge_snapshot_run_read(run)


@router.get("/alert-outbox", response_model=AdminAlertOutboxPage)
def list_admin_alert_outbox(
    request: Request,
    source_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=24),
    action_hint: str | None = Query(default=None, max_length=40),
    event_code: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    statement = select(AdminAlertOutboxEntry)
    filters = {
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "status": status.strip() if status is not None and status.strip() else None,
        "severity": severity.strip() if severity is not None and severity.strip() else None,
        "action_hint": action_hint.strip() if action_hint is not None and action_hint.strip() else None,
        "event_code": event_code.strip() if event_code is not None and event_code.strip() else None,
        "from": from_at,
        "to": to_at,
    }
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if filters["status"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.status == filters["status"])
    if filters["severity"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.severity == filters["severity"])
    if filters["action_hint"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.action_hint == filters["action_hint"])
    if filters["event_code"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.event_code == filters["event_code"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    statement = statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.list",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_list",
            "filters": {key: value for key, value in filters.items() if value is not None},
            "total": total,
            "item_count": len(items),
            "external_delivery": False,
        },
    )
    db.commit()
    return AdminAlertOutboxPage(
        items=[_admin_alert_outbox_entry_read(entry) for entry in items],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/alert-outbox/queue", response_model=AdminAlertOutboxQueueReport)
def get_admin_alert_outbox_queue(
    request: Request,
    source_type: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None),
    stale_after_hours: int = Query(default=24, ge=1, le=720),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxQueueReport:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    generated_at = now_at or datetime.now(UTC)
    filters = {
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from": from_at,
        "to": to_at,
        "now_at": generated_at,
        "stale_after_hours": stale_after_hours,
        "item_limit": item_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    report = _admin_alert_outbox_queue_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        stale_after_hours=stale_after_hours,
        item_limit=item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.queue_report",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_queue_snapshot(report),
    )
    db.commit()
    return report


@router.post("/alert-outbox/dispatch-dry-run", response_model=AdminAlertOutboxDispatchDryRunReport)
def dry_run_admin_alert_outbox_dispatch(
    request_body: AdminAlertOutboxDispatchDryRunRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchDryRunReport:
    _require_admin(current_user)
    if not request_body.confirm_dry_run:
        raise HTTPException(status_code=422, detail="confirm_dry_run must be true")
    if request_body.from_at is not None and request_body.to_at is not None and request_body.from_at > request_body.to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    unique_entry_ids: list[int] | None = None
    if request_body.entry_ids is not None:
        unique_entry_ids = list(dict.fromkeys(request_body.entry_ids))
        if len(unique_entry_ids) != len(request_body.entry_ids):
            raise HTTPException(status_code=422, detail="entry_ids must be unique")
    generated_at = request_body.now_at or datetime.now(UTC)
    filters = {
        "entry_ids": unique_entry_ids,
        "source_type": (
            request_body.source_type.strip()
            if request_body.source_type is not None and request_body.source_type.strip()
            else None
        ),
        "from_at": request_body.from_at,
        "to_at": request_body.to_at,
        "now_at": generated_at,
        "item_limit": request_body.item_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if unique_entry_ids is not None:
        statement = statement.where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if request_body.from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= request_body.from_at)
    if request_body.to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= request_body.to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    if unique_entry_ids is not None:
        found_ids = {entry.id for entry in entries}
        missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
            )
    report = _admin_alert_outbox_dispatch_dry_run_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        item_limit=request_body.item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_dry_run",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_dry_run_snapshot(report),
    )
    db.commit()
    return report


@router.post("/alert-outbox/dispatch-plans", response_model=AdminAlertOutboxDispatchPlanRead)
def create_admin_alert_outbox_dispatch_plan(
    request_body: AdminAlertOutboxDispatchPlanCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanRead:
    _require_admin(current_user)
    if not request_body.confirm_create_plan:
        raise HTTPException(status_code=422, detail="confirm_create_plan must be true")
    entries, filters, generated_at = _admin_alert_outbox_dispatch_entries_for_request(
        db,
        entry_ids=request_body.entry_ids,
        source_type=request_body.source_type,
        from_at=request_body.from_at,
        to_at=request_body.to_at,
        now_at=request_body.now_at,
        entry_limit=request_body.entry_limit,
    )
    report = _admin_alert_outbox_dispatch_dry_run_report(
        entries,
        generated_at=generated_at,
        filters=filters,
        item_limit=request_body.entry_limit,
    )
    if report.ready_count == 0 and not request_body.allow_empty_plan:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "No ready alert outbox entries to plan",
                "dry_run_status": report.dry_run_status,
                "blocked_reason_counts": report.blocked_reason_counts,
            },
        )
    ready_entries = _sort_admin_alert_outbox_queue_items(
        [entry for entry in entries if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at)]
    )[: request_body.entry_limit]
    ready_entry_ids = [entry.id for entry in ready_entries]
    plan = AdminAlertOutboxDispatchPlan(
        plan_key=_admin_alert_outbox_dispatch_plan_key(generated_at),
        plan_status="created",
        dry_run_status=report.dry_run_status,
        source_type=filters.get("source_type"),
        filters_json={
            key: _admin_alert_outbox_snapshot_value(value)
            for key, value in {**report.filters, "entry_limit": request_body.entry_limit}.items()
        },
        policy_json={
            **report.policy,
            "writes_dispatch_plan": True,
            "writes_outbox_state": False,
            "ready_entry_id_limit": request_body.entry_limit,
            "allow_empty_plan": request_body.allow_empty_plan,
        },
        ready_entry_ids_json=ready_entry_ids,
        ready_entry_payload_hashes_json={str(entry.id): entry.payload_hash for entry in ready_entries},
        blocked_reason_counts_json=report.blocked_reason_counts,
        total_count=report.total_count,
        active_count=report.active_count,
        ready_count=report.ready_count,
        blocked_count=report.blocked_count,
        expired_count=report.expired_count,
        not_due_count=report.not_due_count,
        terminal_count=report.terminal_count,
        external_delivery_count=report.external_delivery_count,
        generated_at=generated_at,
        created_by_user_id=current_user.id,
    )
    db.add(plan)
    db.flush()
    response = _admin_alert_outbox_dispatch_plan_read(plan)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.create",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_plan_snapshot(response),
    )
    db.commit()
    return response


@router.get("/alert-outbox/dispatch-plans", response_model=AdminAlertOutboxDispatchPlanPage)
def list_admin_alert_outbox_dispatch_plans(
    request: Request,
    plan_status: str | None = Query(default=None, max_length=32),
    dry_run_status: str | None = Query(default=None, max_length=32),
    source_type: str | None = Query(default=None, max_length=80),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanPage:
    _require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    statement = select(AdminAlertOutboxDispatchPlan).order_by(
        AdminAlertOutboxDispatchPlan.generated_at.desc(),
        AdminAlertOutboxDispatchPlan.id.desc(),
    )
    filters = {
        "plan_status": plan_status.strip() if plan_status is not None and plan_status.strip() else None,
        "dry_run_status": dry_run_status.strip() if dry_run_status is not None and dry_run_status.strip() else None,
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from_at": from_at,
        "to_at": to_at,
        "limit": limit,
        "offset": offset,
    }
    if filters["plan_status"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.plan_status == filters["plan_status"])
    if filters["dry_run_status"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.dry_run_status == filters["dry_run_status"])
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.generated_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxDispatchPlan.generated_at <= to_at)
    total = _statement_count(db, statement)
    plans = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_alert_outbox_dispatch_plan_read(plan) for plan in plans]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.list",
        resource_type="admin_alert_outbox_dispatch_plan",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_dispatch_plan_list",
            "filters": {
                key: _admin_alert_outbox_snapshot_value(value)
                for key, value in filters.items()
                if value is not None
            },
            "total": total,
            "returned_count": len(items),
        },
    )
    db.commit()
    return AdminAlertOutboxDispatchPlanPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(items)),
    )


@router.get("/alert-outbox/dispatch-plans/{plan_id}", response_model=AdminAlertOutboxDispatchPlanRead)
def get_admin_alert_outbox_dispatch_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanRead:
    _require_admin(current_user)
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    response = _admin_alert_outbox_dispatch_plan_read(plan)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.read",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_dispatch_plan_read",
            "plan_id": plan.id,
            "plan_key": plan.plan_key,
            "plan_status": plan.plan_status,
            "dry_run_status": plan.dry_run_status,
            "ready_count": plan.ready_count,
            "blocked_count": plan.blocked_count,
            "expired_count": plan.expired_count,
            "not_due_count": plan.not_due_count,
            "terminal_count": plan.terminal_count,
        },
    )
    db.commit()
    return response


@router.post(
    "/alert-outbox/dispatch-plans/{plan_id}/validate",
    response_model=AdminAlertOutboxDispatchPlanValidationReport,
)
def validate_admin_alert_outbox_dispatch_plan(
    plan_id: int,
    request_body: AdminAlertOutboxDispatchPlanValidateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxDispatchPlanValidationReport:
    _require_admin(current_user)
    if not request_body.confirm_validate_plan:
        raise HTTPException(status_code=422, detail="confirm_validate_plan must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    generated_at = request_body.now_at or datetime.now(UTC)
    report = _admin_alert_outbox_dispatch_plan_validation_report(plan, db, generated_at)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.dispatch_plan.validate",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success",
        request=request,
        snapshot=_admin_alert_outbox_dispatch_plan_validation_snapshot(report),
    )
    db.commit()
    return report


@router.post(
    "/alert-outbox/dispatch-plans/{plan_id}/dispatch",
    response_model=AdminAlertOutboxExternalDispatchReport,
)
def dispatch_admin_alert_outbox_plan(
    plan_id: int,
    request_body: AdminAlertOutboxExternalDispatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxExternalDispatchReport:
    _require_admin(current_user)
    if not request_body.confirm_external_dispatch:
        raise HTTPException(status_code=422, detail="confirm_external_dispatch must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    if plan.plan_status != "created":
        raise HTTPException(
            status_code=409,
            detail={"message": "Alert outbox dispatch plan is not dispatchable", "plan_status": plan.plan_status},
        )

    settings = get_settings()
    posture = alert_delivery_posture(settings)
    try:
        adapter = build_alert_delivery_adapter(settings)
    except AlertDeliveryError as exc:
        record_audit_log(
            db,
            actor=current_user,
            action="admin.alert_outbox.external_dispatch.blocked",
            resource_type="admin_alert_outbox_dispatch_plan",
            resource_id=plan.id,
            event_result="failure",
            failure_reason=exc.code,
            request=request,
            snapshot={
                "format": "admin_alert_outbox_external_dispatch_blocked",
                "plan_id": plan.id,
                "plan_key": plan.plan_key,
                "plan_status": plan.plan_status,
                "delivery_posture": posture,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={"message": "External alert delivery is unavailable", "code": exc.code, "posture": posture},
        ) from None

    started_at = datetime.now(UTC)
    validation = _admin_alert_outbox_dispatch_plan_validation_report(plan, db, started_at)
    if validation.validation_status != "valid" or not validation.ready_entry_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Alert outbox dispatch plan changed before dispatch",
                "validation_status": validation.validation_status,
                "blocked_reason_counts": validation.blocked_reason_counts,
            },
        )
    if len(validation.ready_entry_ids) > settings.alert_delivery_batch_limit:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Alert outbox dispatch plan exceeds configured batch limit",
                "ready_count": len(validation.ready_entry_ids),
                "batch_limit": settings.alert_delivery_batch_limit,
            },
        )
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.id.in_(validation.ready_entry_ids))
            .order_by(AdminAlertOutboxEntry.id.asc())
            .with_for_update()
        ).all()
    )
    if [entry.id for entry in entries] != sorted(validation.ready_entry_ids):
        raise HTTPException(status_code=409, detail="Alert outbox dispatch entries changed before claim")
    db.refresh(plan)
    planned_hashes = {str(key): str(value) for key, value in (plan.ready_entry_payload_hashes_json or {}).items()}
    if plan.plan_status != "created" or any(
        planned_hashes.get(str(entry.id)) != entry.payload_hash
        or not _admin_alert_outbox_entry_dispatch_ready(entry, started_at)
        for entry in entries
    ):
        raise HTTPException(status_code=409, detail="Alert outbox dispatch plan changed while claiming entries")

    plan.plan_status = "dispatching"
    for entry in entries:
        entry.status = "dispatching"
        entry.dispatch_mode = adapter.provider
        entry.delivery_target = adapter.delivery_target
        entry.external_delivery = True
        entry.attempt_count += 1
        entry.last_error_code = None
    db.commit()

    results: list[AdminAlertOutboxExternalDispatchItem] = []
    delivered_count = 0
    failed_count = 0
    for entry in entries:
        attempted_at = datetime.now(UTC)
        idempotency_key = sha256(
            f"astra-alert:{entry.id}:{entry.source_type}:{entry.event_code}:{entry.payload_hash}".encode("utf-8")
        ).hexdigest()
        try:
            receipt = adapter.deliver(
                build_alert_delivery_envelope(entry),
                idempotency_key=idempotency_key,
            )
        except AlertDeliveryError as exc:
            entry.status = "failed"
            entry.last_error_code = exc.code
            entry.available_at = (
                attempted_at + timedelta(seconds=settings.alert_delivery_retry_delay_seconds)
                if exc.retryable
                else None
            )
            failed_count += 1
            result = AdminAlertOutboxExternalDispatchItem(
                entry_id=entry.id,
                status="failed",
                attempt_count=entry.attempt_count,
                provider=adapter.provider,
                retryable=exc.retryable,
                last_error_code=exc.code,
            )
            record_audit_log(
                db,
                actor=current_user,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="failure",
                failure_reason=exc.code,
                request=request,
                snapshot={
                    "format": "admin_alert_outbox_external_dispatch_result",
                    "plan_id": plan.id,
                    "entry_id": entry.id,
                    "status": "failed",
                    "provider": adapter.provider,
                    "delivery_target": adapter.delivery_target,
                    "attempt_count": entry.attempt_count,
                    "retryable": exc.retryable,
                    "retry_available_at": entry.available_at.isoformat() if entry.available_at is not None else None,
                    "payload_hash_prefix": entry.payload_hash[:12],
                },
            )
        else:
            entry.status = "delivered"
            entry.last_error_code = None
            entry.available_at = None
            delivered_count += 1
            result = AdminAlertOutboxExternalDispatchItem(
                entry_id=entry.id,
                status="delivered",
                attempt_count=entry.attempt_count,
                provider=receipt.provider,
                retryable=False,
                receipt_hash_prefix=receipt.receipt_hash[:12],
            )
            record_audit_log(
                db,
                actor=current_user,
                action="admin.alert_outbox.external_dispatch",
                resource_type="admin_alert_outbox",
                resource_id=entry.id,
                event_result="success",
                request=request,
                snapshot={
                    "format": "admin_alert_outbox_external_dispatch_result",
                    "plan_id": plan.id,
                    "entry_id": entry.id,
                    "status": "delivered",
                    "provider": receipt.provider,
                    "delivery_target": adapter.delivery_target,
                    "attempt_count": entry.attempt_count,
                    "http_status": receipt.status_code,
                    "receipt_hash_prefix": receipt.receipt_hash[:12],
                    "payload_hash_prefix": entry.payload_hash[:12],
                },
            )
        db.commit()
        results.append(result)

    plan.plan_status = (
        "delivered"
        if delivered_count == len(entries)
        else "failed"
        if failed_count == len(entries)
        else "partial_failed"
    )
    completed_at = datetime.now(UTC)
    report = AdminAlertOutboxExternalDispatchReport(
        generated_at=completed_at,
        plan_id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        provider=adapter.provider,
        delivery_target=adapter.delivery_target,
        attempted_count=len(entries),
        delivered_count=delivered_count,
        failed_count=failed_count,
        policy={
            **posture,
            "explicit_confirmation": True,
            "automatic_dispatch": False,
            "idempotency_key_sent": True,
            "original_payload_included": False,
            "failure_affects_source_transaction": False,
            "failed_entry_manual_requeue": True,
        },
        items=results,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.external_dispatch_plan",
        resource_type="admin_alert_outbox_dispatch_plan",
        resource_id=plan.id,
        event_result="success" if failed_count == 0 else "failure",
        failure_reason="partial_or_total_delivery_failure" if failed_count else None,
        request=request,
        snapshot={
            "format": "admin_alert_outbox_external_dispatch_plan",
            "plan_id": report.plan_id,
            "plan_key": report.plan_key,
            "plan_status": report.plan_status,
            "provider": report.provider,
            "delivery_target": report.delivery_target,
            "attempted_count": report.attempted_count,
            "delivered_count": report.delivered_count,
            "failed_count": report.failed_count,
            "entry_ids": [item.entry_id for item in report.items],
            "policy": report.policy,
        },
    )
    db.commit()
    return report


@router.patch("/alert-outbox/reviews", response_model=AdminAlertOutboxBulkReviewResponse)
def review_admin_alert_outbox_entries(
    request_body: AdminAlertOutboxBulkReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxBulkReviewResponse:
    _require_admin(current_user)
    if not request_body.confirm_manual_review:
        raise HTTPException(status_code=422, detail="confirm_manual_review must be true")
    unique_entry_ids = list(dict.fromkeys(request_body.entry_ids))
    if len(unique_entry_ids) != len(request_body.entry_ids):
        raise HTTPException(status_code=422, detail="entry_ids must be unique")
    entries = list(
        db.scalars(
            select(AdminAlertOutboxEntry)
            .where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
            .order_by(AdminAlertOutboxEntry.id.asc())
        ).all()
    )
    found_ids = {entry.id for entry in entries}
    missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
        )
    reviewed_at = datetime.now(UTC)
    note = request_body.note.strip() if request_body.note is not None and request_body.note.strip() else None
    previous_status_counts: dict[str, int] = {}
    source_type_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    event_code_counts: dict[str, int] = {}
    for entry in entries:
        previous_status_counts[entry.status] = previous_status_counts.get(entry.status, 0) + 1
        source_type_counts[entry.source_type] = source_type_counts.get(entry.source_type, 0) + 1
        severity_counts[entry.severity] = severity_counts.get(entry.severity, 0) + 1
        event_code_counts[entry.event_code] = event_code_counts.get(entry.event_code, 0) + 1
        if request_body.status == "queued" and entry.status == "failed":
            entry.available_at = reviewed_at
        entry.status = request_body.status
        if request_body.status in {"planned", "queued"}:
            entry.dispatch_mode = "manual_review"
            entry.delivery_target = "admin_outbox"
            entry.external_delivery = False
        entry.reviewed_by_user_id = current_user.id
        entry.reviewed_at = reviewed_at
        entry.review_note = note
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.bulk_review",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_bulk_review",
            "entry_count": len(entries),
            "entry_ids": unique_entry_ids,
            "source_types": source_type_counts,
            "event_codes": event_code_counts,
            "severity_counts": severity_counts,
            "previous_status_counts": previous_status_counts,
            "status": request_body.status,
            "reviewed_by_user_id": current_user.id,
            "reviewed_at": reviewed_at.isoformat(),
            "note_provided": note is not None,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
            "external_delivery": False,
            "automatic_actions": False,
        },
    )
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return AdminAlertOutboxBulkReviewResponse(
        generated_at=reviewed_at,
        status=request_body.status,
        updated_count=len(entries),
        requested_count=len(unique_entry_ids),
        previous_status_counts=previous_status_counts,
        policy={
            "external_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
        },
        items=[_admin_alert_outbox_queue_item(entry) for entry in entries],
    )


@router.patch("/alert-outbox/{entry_id}", response_model=AdminAlertOutboxEntryRead)
def review_admin_alert_outbox_entry(
    entry_id: int,
    request_body: AdminAlertOutboxReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxEntryRead:
    _require_admin(current_user)
    if not request_body.confirm_manual_review:
        raise HTTPException(status_code=422, detail="confirm_manual_review must be true")
    entry = db.get(AdminAlertOutboxEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Alert outbox entry not found")
    previous_status = entry.status
    reviewed_at = datetime.now(UTC)
    note = request_body.note.strip() if request_body.note is not None and request_body.note.strip() else None
    if request_body.status == "queued" and previous_status == "failed":
        entry.available_at = reviewed_at
    entry.status = request_body.status
    if request_body.status in {"planned", "queued"}:
        entry.dispatch_mode = "manual_review"
        entry.delivery_target = "admin_outbox"
        entry.external_delivery = False
    entry.reviewed_by_user_id = current_user.id
    entry.reviewed_at = reviewed_at
    entry.review_note = note
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.review",
        resource_type="admin_alert_outbox",
        resource_id=str(entry.id),
        event_result="success",
        request=request,
        snapshot={
            "format": "admin_alert_outbox_review",
            "entry_id": entry.id,
            "source_type": entry.source_type,
            "source_id": entry.source_id,
            "source_key": entry.source_key,
            "event_code": entry.event_code,
            "severity": entry.severity,
            "action_hint": entry.action_hint,
            "previous_status": previous_status,
            "status": entry.status,
            "dispatch_mode": entry.dispatch_mode,
            "delivery_target": entry.delivery_target,
            "external_delivery": entry.external_delivery,
            "reviewed_by_user_id": current_user.id,
            "reviewed_at": reviewed_at.isoformat(),
            "note_provided": note is not None,
            "automatic_actions": False,
        },
    )
    db.commit()
    db.refresh(entry)
    return _admin_alert_outbox_entry_read(entry)


@router.post(
    "/background-tasks/alert-dispatch-plans/{plan_id}",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_alert_dispatch_plan_background_task(
    plan_id: int,
    request_body: AdminBackgroundTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    plan = db.get(AdminAlertOutboxDispatchPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Alert outbox dispatch plan not found")
    if plan.plan_status != "created":
        raise HTTPException(status_code=409, detail="Only created alert dispatch plans can be enqueued")
    result = enqueue_background_task(
        db,
        task_type="alert_outbox_dispatch_plan",
        idempotency_key=f"alert-dispatch-plan:{plan.id}:{plan.plan_key}",
        source_type="admin_alert_outbox_dispatch_plan",
        source_id=plan.id,
        payload={"plan_id": plan.id},
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "source_type": result.task.source_type,
            "source_id": result.task.source_id,
            "created": result.created,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/knowledge-snapshots",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_knowledge_snapshot_background_task(
    request_body: AdminKnowledgeSnapshotTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    result = enqueue_background_task(
        db,
        task_type="knowledge_snapshot_rebuild",
        idempotency_key=(
            f"knowledge-snapshot:{request_body.granularity}:{request_body.reference_date.isoformat()}"
        ),
        source_type="knowledge_snapshot_window",
        source_id=None,
        payload={
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
        },
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "granularity": request_body.granularity,
            "reference_date": request_body.reference_date.isoformat(),
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.post(
    "/background-tasks/content-script-scans",
    response_model=AdminBackgroundTaskRead,
)
def enqueue_content_script_scan_background_task(
    request_body: AdminContentScriptScanTaskEnqueueRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_enqueue:
        raise HTTPException(status_code=422, detail="confirm_enqueue must be true")
    payload = {
        "slug": request_body.slug.strip("/") if request_body.slug and request_body.slug.strip("/") else None,
        "source_host": request_body.source_host.strip().lower()
        if request_body.source_host and request_body.source_host.strip()
        else None,
        "scan_limit": request_body.scan_limit,
        "scan_offset": request_body.scan_offset,
    }
    scope_hash = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    result = enqueue_background_task(
        db,
        task_type="content_script_asset_scan",
        idempotency_key=f"content-script-scan:{request_body.request_key.strip()}:{scope_hash}",
        source_type="content_script_asset_scan_request",
        source_id=None,
        payload=payload,
        priority=request_body.priority,
        max_attempts=request_body.max_attempts,
        created_by_user_id=current_user.id,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.enqueue",
        resource_type="background_task",
        resource_id=result.task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": result.task.id,
            "task_type": result.task.task_type,
            "created": result.created,
            "filters": payload,
            "priority": result.task.priority,
            "max_attempts": result.task.max_attempts,
        },
    )
    db.commit()
    db.refresh(result.task)
    return _admin_background_task_read(result.task)


@router.get("/background-tasks", response_model=AdminBackgroundTaskPage)
def list_background_tasks(
    task_type: str | None = Query(default=None, max_length=80),
    task_status: str | None = Query(default=None, alias="status", max_length=32),
    source_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskPage:
    _require_admin(current_user)
    statement = select(BackgroundTask).order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
    if task_type:
        statement = statement.where(BackgroundTask.task_type == task_type.strip())
    if task_status:
        statement = statement.where(BackgroundTask.status == task_status.strip())
    if source_type:
        statement = statement.where(BackgroundTask.source_type == source_type.strip())
    total = _statement_count(db, statement)
    tasks = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AdminBackgroundTaskPage(
        items=[_admin_background_task_read(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
        next_offset=_next_offset(total, offset, len(tasks)),
    )


@router.get("/background-tasks/queue", response_model=AdminBackgroundTaskQueueReport)
def get_background_task_queue(
    now_at: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskQueueReport:
    _require_admin(current_user)
    generated_at = now_at or datetime.now(UTC)
    generated_at_value = _naive_utc(generated_at)
    by_status = {
        str(task_status): int(count)
        for task_status, count in db.execute(
            select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(BackgroundTask.status)
        ).all()
    }
    by_task_type = {
        str(task_type): int(count)
        for task_type, count in db.execute(
            select(BackgroundTask.task_type, func.count(BackgroundTask.id)).group_by(BackgroundTask.task_type)
        ).all()
    }
    ready_condition = and_(
        BackgroundTask.status.in_(["pending", "retry_wait"]),
        BackgroundTask.available_at <= generated_at_value,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    stale_condition = and_(
        BackgroundTask.status == "leased",
        BackgroundTask.lease_expires_at.is_not(None),
        BackgroundTask.lease_expires_at <= generated_at_value,
    )
    stale_claimable_condition = and_(
        stale_condition,
        BackgroundTask.attempt_count < BackgroundTask.max_attempts,
    )
    ready_count = int(db.scalar(select(func.count()).select_from(BackgroundTask).where(ready_condition)) or 0)
    stale_lease_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_condition)) or 0
    )
    stale_claimable_count = int(
        db.scalar(select(func.count()).select_from(BackgroundTask).where(stale_claimable_condition)) or 0
    )
    oldest_pending_ready = db.scalar(select(func.min(BackgroundTask.available_at)).where(ready_condition))
    oldest_stale_ready = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(stale_claimable_condition)
    )
    next_available_at = db.scalar(
        select(func.min(BackgroundTask.available_at)).where(
            BackgroundTask.status.in_(["pending", "retry_wait"]),
            BackgroundTask.available_at > generated_at_value,
        )
    )
    next_lease_expires_at = db.scalar(
        select(func.min(BackgroundTask.lease_expires_at)).where(
            BackgroundTask.status == "leased",
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at > generated_at_value,
        )
    )
    settings = get_settings()
    return AdminBackgroundTaskQueueReport(
        generated_at=generated_at,
        total_count=sum(by_status.values()),
        ready_count=ready_count + stale_claimable_count,
        leased_count=by_status.get("leased", 0),
        retry_wait_count=by_status.get("retry_wait", 0),
        succeeded_count=by_status.get("succeeded", 0),
        dead_letter_count=by_status.get("dead_letter", 0),
        cancelled_count=by_status.get("cancelled", 0),
        stale_lease_count=stale_lease_count,
        by_task_type=by_task_type,
        by_status=by_status,
        oldest_ready_at=_oldest_datetime([oldest_pending_ready, oldest_stale_ready]),
        next_available_at=next_available_at,
        next_lease_expires_at=next_lease_expires_at,
        policy={
            "queue_backend": "database",
            "execution_mode": "hybrid_domain_ledgers",
            "worker_enabled": settings.background_task_worker_enabled,
            "lease_seconds": settings.background_task_worker_lease_seconds,
            "batch_size": settings.background_task_worker_batch_size,
            "payload_redacted": True,
            "lease_token_returned": False,
        },
    )


@router.get("/background-tasks/{task_id}", response_model=AdminBackgroundTaskRead)
def get_background_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    return _admin_background_task_read(task)


@router.get("/background-tasks/{task_id}/attempts", response_model=list[AdminBackgroundTaskAttemptRead])
def list_background_task_attempts(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdminBackgroundTaskAttemptRead]:
    _require_admin(current_user)
    if db.get(BackgroundTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Background task not found")
    attempts = list(
        db.scalars(
            select(BackgroundTaskAttempt)
            .where(BackgroundTaskAttempt.task_id == task_id)
            .order_by(BackgroundTaskAttempt.attempt_number.desc())
        ).all()
    )
    return [_admin_background_task_attempt_read(attempt) for attempt in attempts]


@router.post("/background-tasks/{task_id}/retry", response_model=AdminBackgroundTaskRead)
def retry_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = retry_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.retry",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
            "attempt_count": task.attempt_count,
            "max_attempts": task.max_attempts,
        },
    )
    db.commit()
    return _admin_background_task_read(task)


@router.post("/background-tasks/{task_id}/cancel", response_model=AdminBackgroundTaskRead)
def cancel_background_task_admin(
    task_id: int,
    request_body: AdminBackgroundTaskActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminBackgroundTaskRead:
    _require_admin(current_user)
    if not request_body.confirm_action:
        raise HTTPException(status_code=422, detail="confirm_action must be true")
    try:
        task, applied = cancel_background_task(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Background task not found") from None
    record_audit_log(
        db,
        actor=current_user,
        action="admin.background_task.cancel",
        resource_type="background_task",
        resource_id=task.id,
        event_result="success",
        request=request,
        snapshot={
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "applied": applied,
            "reason_provided": bool(request_body.reason and request_body.reason.strip()),
        },
    )
    db.commit()
    return _admin_background_task_read(task)


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
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    items = list(db.scalars(statement.offset(offset).limit(limit)).all())
    return AuditLogPage(items=items, total=total, limit=limit, offset=offset, next_offset=_next_offset(total, offset, len(items)))


@router.get("/audit-logs/export", response_model=AuditLogExport)
def export_audit_logs(
    request: Request,
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
    include_snapshot: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogExport:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    items = [_audit_log_export_item(log, include_snapshot=include_snapshot) for log in logs]
    truncated = total > len(logs)
    exported_at = datetime.now(UTC)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.export",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_export_snapshot(
            export_format="json",
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
            include_snapshot=include_snapshot,
            limit=limit,
            total=total,
            exported_count=len(logs),
            truncated=truncated,
            exported_at=exported_at,
        ),
    )
    db.commit()
    return AuditLogExport(
        items=items,
        total=total,
        limit=limit,
        truncated=truncated,
        include_snapshot=include_snapshot,
        exported_at=exported_at,
    )


@router.get("/audit-logs/export.csv")
def export_audit_logs_csv(
    request: Request,
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
    include_snapshot: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    items = [_audit_log_export_item(log, include_snapshot=include_snapshot) for log in logs]
    truncated = total > len(logs)
    exported_at = datetime.now(UTC)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.export",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_export_snapshot(
            export_format="csv",
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
            include_snapshot=include_snapshot,
            limit=limit,
            total=total,
            exported_count=len(logs),
            truncated=truncated,
            exported_at=exported_at,
        ),
    )
    db.commit()
    return Response(
        content=_audit_log_csv(items),
        media_type="text/csv; charset=utf-8",
        headers=_audit_log_csv_headers(
            total=total,
            limit=limit,
            truncated=truncated,
            include_snapshot=include_snapshot,
            exported_at=exported_at,
        ),
    )


@router.get("/audit-logs/report", response_model=AuditLogReport)
def report_audit_logs(
    request: Request,
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
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogReport:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    generated_at = datetime.now(UTC)
    report = _audit_log_report(
        db,
        statement=statement,
        filters=_audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.report",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_report_snapshot(report, report_format="json"),
    )
    db.commit()
    return report


@router.get("/audit-logs/report.csv")
def report_audit_logs_csv(
    request: Request,
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
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    generated_at = datetime.now(UTC)
    report = _audit_log_report(
        db,
        statement=statement,
        filters=_audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.report",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_report_snapshot(report, report_format="csv"),
    )
    db.commit()
    return Response(
        content=_audit_log_report_csv(report),
        media_type="text/csv; charset=utf-8",
        headers=_audit_log_report_csv_headers(report),
    )


@router.get("/audit-logs/retention-plan", response_model=AuditLogRetentionPlan)
def plan_audit_log_retention(
    request: Request,
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
    before_at: datetime | None = Query(default=None, alias="before"),
    retention_days: int | None = Query(default=None, ge=1, le=3650),
    warning_days: int = Query(default=30, ge=0, le=3650),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogRetentionPlan:
    _require_admin(current_user)
    if before_at is not None and retention_days is not None:
        raise HTTPException(status_code=422, detail="before and retention_days cannot be used together")
    settings = get_settings()
    generated_at = datetime.now(UTC)
    policy_retention_days = retention_days or settings.audit_log_retention_days
    if before_at is not None:
        cutoff_at = before_at
        policy_source: Literal["config", "query", "before"] = "before"
        policy_days: int | None = None
    else:
        cutoff_at = generated_at - timedelta(days=policy_retention_days)
        policy_source = "query" if retention_days is not None else "config"
        policy_days = policy_retention_days
    expiring_soon_cutoff_at = cutoff_at + timedelta(days=warning_days)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    filters = _audit_log_filters(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    plan = _audit_log_retention_plan(
        db,
        statement=statement,
        filters=filters,
        policy=AuditLogRetentionPolicy(
            retention_days=policy_days,
            warning_days=warning_days,
            cutoff_at=cutoff_at,
            expiring_soon_cutoff_at=expiring_soon_cutoff_at,
            source=policy_source,
        ),
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.retention_plan",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_retention_snapshot(plan),
    )
    db.commit()
    return plan


@router.get("/audit-logs/chain-integrity", response_model=AuditLogChainVerification)
def verify_audit_log_chain_integrity(
    request: Request,
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=5000, ge=1, le=20000),
    issue_limit: int = Query(default=50, ge=0, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogChainVerification:
    _require_admin(current_user)
    statement = _audit_log_statement(
        actor_user_id=None,
        action=None,
        resource_type=None,
        resource_id=None,
        school_id=None,
        class_id=None,
        event_result=None,
        failure_reason=None,
        request_id=None,
        from_at=from_at,
        to_at=to_at,
    ).order_by(None)
    statement = statement.order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    total = _statement_count(db, statement)
    logs = list(db.scalars(statement.limit(limit)).all())
    generated_at = datetime.now(UTC)
    report = _audit_log_chain_verification(
        logs=logs,
        total=total,
        filters=_audit_log_filters(
            actor_user_id=None,
            action=None,
            resource_type=None,
            resource_id=None,
            school_id=None,
            class_id=None,
            event_result=None,
            failure_reason=None,
            request_id=None,
            from_at=from_at,
            to_at=to_at,
        ),
        limit=limit,
        issue_limit=issue_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.chain_integrity",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_chain_verification_snapshot(report),
    )
    db.commit()
    return report


@router.get("/audit-logs/high-frequency", response_model=AuditLogFrequencyReport)
def report_audit_log_high_frequency(
    request: Request,
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
    window_hours: int = Query(default=24, ge=1, le=24 * 31),
    min_count: int = Query(default=10, ge=1, le=10000),
    min_failure_count: int = Query(default=3, ge=0, le=10000),
    min_failure_ratio: float = Query(default=0.5, ge=0, le=1),
    bucket_limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditLogFrequencyReport:
    _require_admin(current_user)
    generated_at = datetime.now(UTC)
    effective_to = to_at or generated_at
    effective_from = from_at or effective_to - timedelta(hours=window_hours)
    statement = _audit_log_statement(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=effective_from,
        to_at=effective_to,
    )
    filters = _audit_log_filters(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=from_at,
        to_at=to_at,
    )
    report = _audit_log_frequency_report(
        db,
        statement=statement,
        filters=filters,
        effective_from=effective_from,
        effective_to=effective_to,
        window_hours=window_hours,
        min_count=min_count,
        min_failure_count=min_failure_count,
        min_failure_ratio=min_failure_ratio,
        bucket_limit=bucket_limit,
        generated_at=generated_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.audit.high_frequency",
        resource_type="audit_log",
        event_result="success",
        request=request,
        snapshot=_audit_log_frequency_snapshot(report),
    )
    db.commit()
    return report


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


def _knowledge_snapshot_run_statement(
    *,
    granularity: str | None,
    trigger_source: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
    statement = select(KnowledgeSnapshotRun)
    if granularity is not None:
        statement = statement.where(KnowledgeSnapshotRun.granularity == granularity.strip().lower())
    if trigger_source is not None:
        statement = statement.where(KnowledgeSnapshotRun.trigger_source == trigger_source.strip().lower())
    if from_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at >= from_at)
    if to_at is not None:
        statement = statement.where(KnowledgeSnapshotRun.started_at <= to_at)
    return statement


def _knowledge_snapshot_run_filters(
    *,
    granularity: str | None,
    trigger_source: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    return {
        "granularity": granularity.strip().lower() if granularity is not None else None,
        "trigger_source": trigger_source.strip().lower() if trigger_source is not None else None,
        "from": from_at.isoformat() if from_at is not None else None,
        "to": to_at.isoformat() if to_at is not None else None,
    }


def _knowledge_snapshot_run_health_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    retry_attempts: int,
    lease_seconds: int,
    lease_expiring_seconds: int,
    problem_limit: int,
    generated_at: datetime,
) -> AdminKnowledgeSnapshotRunHealthReport:
    runs = list(db.scalars(statement).all())
    generated_at_naive = _naive_utc(generated_at)
    lease_expiring_cutoff = generated_at_naive + timedelta(seconds=lease_expiring_seconds)
    status_counts: dict[str | None, int] = {}
    running_count = 0
    active_running_count = 0
    stale_running_count = 0
    lease_expiring_count = 0
    legacy_running_without_lease_count = 0
    partial_running_lease_count = 0
    pending_count = 0
    success_count = 0
    failed_count = 0
    retryable_failed_count = 0
    exhausted_failed_count = 0
    cancelled_count = 0
    claimable_count = 0
    problem_runs: list[AdminKnowledgeSnapshotRunHealthItem] = []
    latest_success_by_granularity: dict[str, datetime | None] = {}
    oldest_running_started_at: datetime | None = None
    next_lease_expires_at: datetime | None = None
    newest_finished_at: datetime | None = None

    for run in runs:
        status_counts[run.status] = status_counts.get(run.status, 0) + 1
        if run.finished_at is not None and (
            newest_finished_at is None or _naive_utc(run.finished_at) > _naive_utc(newest_finished_at)
        ):
            newest_finished_at = run.finished_at
        health_flags: list[str] = []
        retryable = False
        claimable = False
        lease_seconds_remaining: int | None = None
        if run.status == "running":
            running_count += 1
            if oldest_running_started_at is None or _naive_utc(run.started_at) < _naive_utc(oldest_running_started_at):
                oldest_running_started_at = run.started_at
            has_any_lease = knowledge_snapshot_lease_has_any_field(run)
            has_complete_lease = knowledge_snapshot_lease_is_complete(run)
            if not has_any_lease:
                legacy_running_without_lease_count += 1
                health_flags.append("legacy_running_without_lease")
            elif not has_complete_lease:
                partial_running_lease_count += 1
                health_flags.append("partial_scheduler_lease")
                health_flags.extend(_knowledge_snapshot_missing_lease_flags(knowledge_snapshot_lease_missing_fields(run)))
            lease_expires_at = _naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > generated_at_naive:
                lease_seconds_remaining = int((lease_expires_at - generated_at_naive).total_seconds())
                if next_lease_expires_at is None or lease_expires_at < _naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
                if lease_expires_at <= lease_expiring_cutoff:
                    lease_expiring_count += 1
                    health_flags.append("lease_expiring")
            if _knowledge_snapshot_run_lease_expired(run, generated_at_naive, lease_seconds):
                stale_running_count += 1
                claimable = True
                claimable_count += 1
                health_flags.append("stale_running")
            elif has_complete_lease:
                active_running_count += 1
        elif run.status == "pending":
            pending_count += 1
            claimable = True
            claimable_count += 1
            health_flags.append("pending")
        elif run.status == "success":
            success_count += 1
            latest_success_at = run.finished_at or run.started_at
            current_latest = latest_success_by_granularity.get(run.granularity)
            if current_latest is None or _naive_utc(latest_success_at) > _naive_utc(current_latest):
                latest_success_by_granularity[run.granularity] = latest_success_at
        elif run.status == "failed":
            failed_count += 1
            if run.attempt_count < retry_attempts:
                retryable_failed_count += 1
                retryable = True
                claimable = True
                claimable_count += 1
                health_flags.append("retryable_failed")
            else:
                exhausted_failed_count += 1
                health_flags.append("exhausted_failed")
        elif run.status == "cancelled":
            cancelled_count += 1
        if health_flags:
            problem_runs.append(
                AdminKnowledgeSnapshotRunHealthItem(
                    id=run.id,
                    run_key=run.run_key,
                    granularity=run.granularity,
                    period_start=run.period_start,
                    period_end=run.period_end,
                    trigger_source=run.trigger_source,
                    status=run.status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    scheduler_lease_owner=run.scheduler_lease_owner,
                    scheduler_lease_expires_at=run.scheduler_lease_expires_at,
                    scheduler_heartbeat_at=run.scheduler_heartbeat_at,
                    attempt_count=run.attempt_count,
                    user_snapshot_count=run.user_snapshot_count,
                    class_snapshot_count=run.class_snapshot_count,
                    error_message=run.error_message,
                    health_flags=health_flags,
                    retryable=retryable,
                    claimable=claimable,
                    cancellable=run.status == "pending"
                    or (run.status == "running" and run.scheduler_lease_token is not None),
                    lease_seconds_remaining=lease_seconds_remaining,
                )
            )

    needs_attention_count = stale_running_count + pending_count + failed_count + partial_running_lease_count
    if needs_attention_count > 0:
        health_status: Literal["ok", "warning", "attention"] = "attention"
    elif lease_expiring_count > 0:
        health_status = "warning"
    else:
        health_status = "ok"
    return AdminKnowledgeSnapshotRunHealthReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": retry_attempts,
            "lease_seconds": lease_seconds,
            "lease_expiring_seconds": lease_expiring_seconds,
            "problem_limit": problem_limit,
        },
        health_status=health_status,
        total=len(runs),
        by_status=[
            AdminKnowledgeSnapshotRunStatusBucket(status=status, total=total)
            for status, total in sorted(status_counts.items(), key=lambda item: str(item[0] or ""))
        ],
        running_count=running_count,
        active_running_count=active_running_count,
        stale_running_count=stale_running_count,
        lease_expiring_count=lease_expiring_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        partial_running_lease_count=partial_running_lease_count,
        claimable_count=claimable_count,
        pending_count=pending_count,
        success_count=success_count,
        failed_count=failed_count,
        retryable_failed_count=retryable_failed_count,
        exhausted_failed_count=exhausted_failed_count,
        cancelled_count=cancelled_count,
        needs_attention_count=needs_attention_count,
        problem_count=len(problem_runs),
        problem_runs=_sort_knowledge_snapshot_problem_runs(problem_runs)[:problem_limit],
        latest_success_by_granularity=latest_success_by_granularity,
        oldest_running_started_at=oldest_running_started_at,
        next_lease_expires_at=next_lease_expires_at,
        newest_finished_at=newest_finished_at,
    )


def _knowledge_snapshot_run_health_snapshot(report: AdminKnowledgeSnapshotRunHealthReport) -> dict[str, Any]:
    return {
        "format": "health",
        "filters": report.filters,
        "policy": report.policy,
        "health_status": report.health_status,
        "total": report.total,
        "by_status": [bucket.model_dump() for bucket in report.by_status],
        "running_count": report.running_count,
        "stale_running_count": report.stale_running_count,
        "lease_expiring_count": report.lease_expiring_count,
        "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        "partial_running_lease_count": report.partial_running_lease_count,
        "claimable_count": report.claimable_count,
        "pending_count": report.pending_count,
        "failed_count": report.failed_count,
        "retryable_failed_count": report.retryable_failed_count,
        "exhausted_failed_count": report.exhausted_failed_count,
        "needs_attention_count": report.needs_attention_count,
        "problem_count": report.problem_count,
    }


def _knowledge_snapshot_run_queue_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    schedule_config: SnapshotScheduleConfig,
    retry_attempts: int,
    lease_seconds: int,
    item_limit: int,
    generated_at: datetime,
) -> AdminKnowledgeSnapshotRunQueueReport:
    runs = list(db.scalars(statement).all())
    generated_at_naive = _naive_utc(generated_at)
    due_jobs = due_snapshot_jobs(generated_at_naive, schedule_config)
    if filters["granularity"] is not None:
        due_jobs = [job for job in due_jobs if job.granularity == filters["granularity"]]

    ready_jobs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    manual_requeue_runs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    blocked_runs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    next_due_jobs: list[AdminKnowledgeSnapshotRunQueueItem] = []
    ready_keys: set[tuple[str, date]] = set()
    next_lease_expires_at: datetime | None = None

    for job in due_jobs:
        item = _knowledge_snapshot_due_queue_item(db, job, retry_attempts, lease_seconds, generated_at_naive)
        if item is None:
            continue
        if _knowledge_snapshot_queue_item_matches_filters(item, filters):
            next_due_jobs.append(item)
            if item.ready:
                ready_jobs.append(item)
                ready_keys.add((item.granularity, item.reference_date))

    retryable_failed_count = 0
    exhausted_failed_count = 0
    cancelled_count = 0
    stale_running_count = 0
    active_running_count = 0
    legacy_running_without_lease_count = 0
    pending_count = 0
    claimable_by_lease_rule_count = 0

    for run in runs:
        key = (run.granularity, run.period_start.date())
        if run.status == "pending":
            pending_count += 1
            claimable_by_lease_rule_count += 1
            if key not in ready_keys:
                item = _knowledge_snapshot_run_queue_item(
                    run,
                    source="pending",
                    reason="pending_run_waiting_for_scheduler",
                    ready=True,
                    claimable=True,
                )
                ready_jobs.append(item)
                ready_keys.add(key)
        elif run.status == "failed":
            retryable = run.attempt_count < retry_attempts
            if retryable:
                retryable_failed_count += 1
                claimable_by_lease_rule_count += 1
                source = "retryable_failed"
                reason = "manual_requeue_available_retryable_failed"
            else:
                exhausted_failed_count += 1
                source = "exhausted_failed"
                reason = "manual_requeue_available_exhausted_failed"
            manual_requeue_runs.append(
                _knowledge_snapshot_run_queue_item(
                    run,
                    source=source,
                    reason=reason,
                    ready=False,
                    claimable=retryable,
                )
            )
        elif run.status == "cancelled":
            cancelled_count += 1
            manual_requeue_runs.append(
                _knowledge_snapshot_run_queue_item(
                    run,
                    source="cancelled",
                    reason="manual_requeue_available_cancelled",
                    ready=False,
                    claimable=False,
                )
            )
        elif run.status == "running":
            lease_expired = _knowledge_snapshot_run_lease_expired(run, generated_at_naive, lease_seconds)
            if run.scheduler_lease_token is None:
                legacy_running_without_lease_count += 1
            lease_expires_at = _naive_utc(run.scheduler_lease_expires_at) if run.scheduler_lease_expires_at else None
            if lease_expires_at is not None and lease_expires_at > generated_at_naive:
                if next_lease_expires_at is None or lease_expires_at < _naive_utc(next_lease_expires_at):
                    next_lease_expires_at = run.scheduler_lease_expires_at
            if lease_expired and run.scheduler_lease_token is not None:
                stale_running_count += 1
                claimable_by_lease_rule_count += 1
                if key not in ready_keys:
                    manual_requeue_runs.append(
                        _knowledge_snapshot_run_queue_item(
                            run,
                            source="stale_running",
                            reason="manual_requeue_available_stale_running",
                            ready=False,
                            claimable=True,
                        )
                    )
            elif lease_expired:
                stale_running_count += 1
                claimable_by_lease_rule_count += 1
                blocked_runs.append(
                    _knowledge_snapshot_run_queue_item(
                        run,
                        source="legacy_running",
                        reason="legacy_running_without_scheduler_lease",
                        ready=False,
                        claimable=False,
                    )
                )
            else:
                active_running_count += 1
                blocked_runs.append(
                    _knowledge_snapshot_run_queue_item(
                        run,
                        source="active_running" if run.scheduler_lease_token is not None else "legacy_running",
                        reason="active_running_lease_not_expired"
                        if run.scheduler_lease_token is not None
                        else "legacy_running_without_scheduler_lease",
                        ready=False,
                        claimable=False,
                    )
                )

    ready_jobs = _sort_knowledge_snapshot_queue_items(ready_jobs)
    manual_requeue_runs = _sort_knowledge_snapshot_queue_items(manual_requeue_runs)
    blocked_runs = _sort_knowledge_snapshot_queue_items(blocked_runs)
    next_due_jobs = _sort_knowledge_snapshot_queue_items(next_due_jobs)
    ready_count = len(ready_jobs)
    manual_requeue_count = len(manual_requeue_runs)
    blocked_count = len(blocked_runs)
    backlog_count = ready_count + manual_requeue_count + blocked_count
    if ready_count > 0:
        queue_status: Literal["empty", "ready", "backlog"] = "ready"
    elif backlog_count > 0:
        queue_status = "backlog"
    else:
        queue_status = "empty"

    by_granularity: dict[str, int] = {}
    for item in ready_jobs + manual_requeue_runs + blocked_runs:
        by_granularity[item.granularity] = by_granularity.get(item.granularity, 0) + 1

    return AdminKnowledgeSnapshotRunQueueReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": retry_attempts,
            "lease_seconds": lease_seconds,
            "item_limit": item_limit,
            "daily_enabled": schedule_config.daily_enabled,
            "daily_hour": schedule_config.daily_hour,
            "weekly_enabled": schedule_config.weekly_enabled,
            "weekly_weekday": schedule_config.weekly_weekday,
            "weekly_hour": schedule_config.weekly_hour,
        },
        queue_status=queue_status,
        backlog_count=backlog_count,
        ready_count=ready_count,
        dispatchable_now_count=ready_count,
        claimable_by_lease_rule_count=claimable_by_lease_rule_count,
        due_count=sum(1 for item in ready_jobs if item.source == "due"),
        pending_count=pending_count,
        manual_requeue_count=manual_requeue_count,
        blocked_count=blocked_count,
        retryable_failed_count=retryable_failed_count,
        exhausted_failed_count=exhausted_failed_count,
        cancelled_count=cancelled_count,
        stale_running_count=stale_running_count,
        active_running_count=active_running_count,
        legacy_running_without_lease_count=legacy_running_without_lease_count,
        by_granularity=by_granularity,
        ready_jobs=ready_jobs[:item_limit],
        manual_requeue_runs=manual_requeue_runs[:item_limit],
        blocked_runs=blocked_runs[:item_limit],
        next_due_jobs=next_due_jobs[:item_limit],
        oldest_ready_at=_oldest_queue_item_started_at(ready_jobs),
        oldest_manual_requeue_at=_oldest_queue_item_started_at(manual_requeue_runs),
        next_lease_expires_at=next_lease_expires_at,
    )


def _knowledge_snapshot_due_queue_item(
    db: Session,
    job: SnapshotScheduleJob,
    retry_attempts: int,
    lease_seconds: int,
    now: datetime,
) -> AdminKnowledgeSnapshotRunQueueItem | None:
    period_start, period_end = snapshot_window(job.granularity, job.reference_date)
    run_key = snapshot_run_key(job.granularity, period_start, period_end)
    should_run = should_run_snapshot_job(
        db,
        job,
        retry_attempts=retry_attempts,
        lease_seconds=lease_seconds,
        now=now,
    )
    run = db.scalar(select(KnowledgeSnapshotRun).where(KnowledgeSnapshotRun.run_key == run_key))
    if not should_run and run is None:
        return None
    if run is None:
        return AdminKnowledgeSnapshotRunQueueItem(
            source="due",
            reason="due_window_missing_run",
            ready=True,
            claimable=True,
            run_key=run_key,
            granularity=job.granularity,
            reference_date=job.reference_date,
            period_start=period_start,
            period_end=period_end,
            status="missing",
        )
    if not should_run:
        return _knowledge_snapshot_run_queue_item(
            run,
            source="due",
            reason=f"due_window_{run.status}_not_ready",
            ready=False,
            claimable=False,
        )
    if run.status == "pending":
        reason = "due_window_pending"
    elif run.status == "failed":
        reason = "due_window_retryable_failed" if run.attempt_count < retry_attempts else "due_window_failed"
    elif run.status == "running":
        reason = "due_window_stale_running"
    else:
        reason = "due_window_ready"
    return _knowledge_snapshot_run_queue_item(
        run,
        source="due",
        reason=reason,
        ready=True,
        claimable=True,
    )


def _knowledge_snapshot_run_queue_item(
    run: KnowledgeSnapshotRun,
    *,
    source: Literal[
        "due",
        "pending",
        "retryable_failed",
        "exhausted_failed",
        "cancelled",
        "stale_running",
        "active_running",
        "legacy_running",
    ],
    reason: str,
    ready: bool,
    claimable: bool,
) -> AdminKnowledgeSnapshotRunQueueItem:
    return AdminKnowledgeSnapshotRunQueueItem(
        source=source,
        reason=reason,
        ready=ready,
        claimable=claimable,
        run_id=run.id,
        run_key=run.run_key,
        granularity=run.granularity,
        reference_date=run.period_start.date(),
        period_start=run.period_start,
        period_end=run.period_end,
        status=run.status,
        trigger_source=run.trigger_source,
        started_at=run.started_at,
        finished_at=run.finished_at,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        attempt_count=run.attempt_count,
    )


def _knowledge_snapshot_queue_item_matches_filters(
    item: AdminKnowledgeSnapshotRunQueueItem,
    filters: dict[str, Any],
) -> bool:
    if filters["granularity"] is not None and item.granularity != filters["granularity"]:
        return False
    if filters["trigger_source"] is not None and item.trigger_source != filters["trigger_source"]:
        return False
    if filters["from"] is not None:
        if item.started_at is None or _naive_utc(item.started_at) < _naive_utc(datetime.fromisoformat(filters["from"])):
            return False
    if filters["to"] is not None:
        if item.started_at is None or _naive_utc(item.started_at) > _naive_utc(datetime.fromisoformat(filters["to"])):
            return False
    return True


def _sort_knowledge_snapshot_queue_items(
    items: list[AdminKnowledgeSnapshotRunQueueItem],
) -> list[AdminKnowledgeSnapshotRunQueueItem]:
    source_order = {
        "due": 0,
        "pending": 1,
        "stale_running": 2,
        "retryable_failed": 3,
        "exhausted_failed": 4,
        "cancelled": 5,
        "active_running": 6,
        "legacy_running": 7,
    }

    def sort_key(item: AdminKnowledgeSnapshotRunQueueItem) -> tuple[int, datetime, str, int]:
        base_time = item.started_at or item.period_start
        return (source_order.get(item.source, 99), _naive_utc(base_time), item.run_key, item.run_id or 0)

    return sorted(items, key=sort_key)


def _oldest_queue_item_started_at(items: list[AdminKnowledgeSnapshotRunQueueItem]) -> datetime | None:
    started_values = [item.started_at for item in items if item.started_at is not None]
    if not started_values:
        return None
    return min(started_values, key=_naive_utc)


def _knowledge_snapshot_run_queue_snapshot(report: AdminKnowledgeSnapshotRunQueueReport) -> dict[str, Any]:
    return {
        "format": "queue",
        "filters": report.filters,
        "policy": report.policy,
        "queue_status": report.queue_status,
        "backlog_count": report.backlog_count,
        "ready_count": report.ready_count,
        "dispatchable_now_count": report.dispatchable_now_count,
        "claimable_by_lease_rule_count": report.claimable_by_lease_rule_count,
        "due_count": report.due_count,
        "pending_count": report.pending_count,
        "manual_requeue_count": report.manual_requeue_count,
        "blocked_count": report.blocked_count,
        "retryable_failed_count": report.retryable_failed_count,
        "exhausted_failed_count": report.exhausted_failed_count,
        "cancelled_count": report.cancelled_count,
        "stale_running_count": report.stale_running_count,
        "active_running_count": report.active_running_count,
        "legacy_running_without_lease_count": report.legacy_running_without_lease_count,
        "by_granularity": report.by_granularity,
    }


def _knowledge_snapshot_run_alert_report(
    *,
    health_report: AdminKnowledgeSnapshotRunHealthReport,
    queue_report: AdminKnowledgeSnapshotRunQueueReport,
    candidate_limit: int,
    generated_at: datetime,
    filters: dict[str, Any],
    lease_expiring_seconds: int,
) -> AdminKnowledgeSnapshotRunAlertReport:
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate] = []
    for item in health_report.problem_runs:
        candidates.extend(_knowledge_snapshot_health_alert_candidates(item))
    for item in queue_report.ready_jobs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"queue_{item.source}",
                severity="warning",
                action_hint="dispatch",
            )
        )
    for item in queue_report.manual_requeue_runs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"manual_{item.source}",
                severity="critical" if item.source in {"stale_running", "exhausted_failed"} else "warning",
                action_hint="requeue" if item.claimable else "investigate",
            )
        )
    for item in queue_report.blocked_runs:
        candidates.append(
            _knowledge_snapshot_queue_alert_candidate(
                item,
                code=f"blocked_{item.source}",
                severity="critical" if item.source == "legacy_running" else "info",
                action_hint="investigate" if item.source == "legacy_running" else "monitor",
            )
        )

    sorted_candidates = _sort_knowledge_snapshot_alert_candidates(candidates)
    critical_count = sum(1 for item in sorted_candidates if item.severity == "critical")
    warning_count = sum(1 for item in sorted_candidates if item.severity == "warning")
    info_count = sum(1 for item in sorted_candidates if item.severity == "info")
    if critical_count > 0:
        alert_status: Literal["ok", "warning", "critical"] = "critical"
    elif warning_count > 0:
        alert_status = "warning"
    else:
        alert_status = "ok"
    return AdminKnowledgeSnapshotRunAlertReport(
        generated_at=generated_at,
        filters=filters,
        policy={
            "retry_attempts": health_report.policy.get("retry_attempts"),
            "lease_seconds": health_report.policy.get("lease_seconds"),
            "lease_expiring_seconds": lease_expiring_seconds,
            "candidate_limit": candidate_limit,
            "source": "health_queue_derived",
        },
        alert_status=alert_status,
        health_status=health_report.health_status,
        queue_status=queue_report.queue_status,
        candidate_count=len(sorted_candidates),
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        needs_attention_count=health_report.needs_attention_count,
        lease_expiring_count=health_report.lease_expiring_count,
        dispatchable_now_count=queue_report.dispatchable_now_count,
        manual_requeue_count=queue_report.manual_requeue_count,
        blocked_count=queue_report.blocked_count,
        candidates=sorted_candidates[:candidate_limit],
    )


def _knowledge_snapshot_health_alert_candidates(
    item: AdminKnowledgeSnapshotRunHealthItem,
) -> list[AdminKnowledgeSnapshotRunAlertCandidate]:
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate] = []
    for flag in item.health_flags:
        if flag == "stale_running":
            severity: Literal["critical", "warning", "info"] = "critical"
            action_hint: Literal["requeue", "dispatch", "investigate", "monitor"] = (
                "requeue" if item.claimable else "investigate"
            )
        elif flag in {
            "partial_scheduler_lease",
            "running_missing_lease_owner",
            "running_missing_lease_token",
            "running_missing_lease_expiry",
            "running_missing_heartbeat",
        }:
            severity = "critical"
            action_hint = "investigate"
        elif flag in {"retryable_failed", "pending"}:
            severity = "warning"
            action_hint = "requeue" if flag == "retryable_failed" else "dispatch"
        elif flag in {"exhausted_failed", "legacy_running_without_lease"}:
            severity = "critical"
            action_hint = "investigate"
        elif flag == "lease_expiring":
            severity = "warning"
            action_hint = "monitor"
        else:
            severity = "info"
            action_hint = "monitor"
        candidates.append(
            AdminKnowledgeSnapshotRunAlertCandidate(
                severity=severity,
                code=flag,
                source="health",
                action_hint=action_hint,
                run_id=item.id,
                run_key=item.run_key,
                granularity=item.granularity,
                status=item.status,
                trigger_source=item.trigger_source,
                started_at=item.started_at,
                finished_at=item.finished_at,
                scheduler_lease_owner=item.scheduler_lease_owner,
                scheduler_lease_expires_at=item.scheduler_lease_expires_at,
                scheduler_heartbeat_at=item.scheduler_heartbeat_at,
                attempt_count=item.attempt_count,
                health_flags=[flag],
                retryable=item.retryable,
                claimable=item.claimable,
                cancellable=item.cancellable,
            )
        )
    return candidates


def _knowledge_snapshot_queue_alert_candidate(
    item: AdminKnowledgeSnapshotRunQueueItem,
    *,
    code: str,
    severity: Literal["critical", "warning", "info"],
    action_hint: Literal["requeue", "dispatch", "investigate", "monitor"],
) -> AdminKnowledgeSnapshotRunAlertCandidate:
    return AdminKnowledgeSnapshotRunAlertCandidate(
        severity=severity,
        code=code,
        source="queue",
        action_hint=action_hint,
        run_id=item.run_id,
        run_key=item.run_key,
        granularity=item.granularity,
        status=item.status,
        trigger_source=item.trigger_source,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
        queue_reason=item.reason,
        claimable=item.claimable,
        ready=item.ready,
    )


def _sort_knowledge_snapshot_alert_candidates(
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate],
) -> list[AdminKnowledgeSnapshotRunAlertCandidate]:
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    action_order = {"requeue": 0, "dispatch": 1, "investigate": 2, "monitor": 3}

    def sort_key(item: AdminKnowledgeSnapshotRunAlertCandidate) -> tuple[int, int, datetime, str, int]:
        base_time = item.started_at or item.finished_at or datetime.max
        return (
            severity_order.get(item.severity, 99),
            action_order.get(item.action_hint, 99),
            _naive_utc(base_time),
            item.run_key,
            item.run_id or 0,
        )

    return sorted(candidates, key=sort_key)


def _knowledge_snapshot_run_alert_snapshot(report: AdminKnowledgeSnapshotRunAlertReport) -> dict[str, Any]:
    by_code: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for item in report.candidates:
        by_code[item.code] = by_code.get(item.code, 0) + 1
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
    return {
        "format": "alert_candidates",
        "filters": report.filters,
        "policy": report.policy,
        "alert_status": report.alert_status,
        "health_status": report.health_status,
        "queue_status": report.queue_status,
        "candidate_count": report.candidate_count,
        "critical_count": report.critical_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "needs_attention_count": report.needs_attention_count,
        "lease_expiring_count": report.lease_expiring_count,
        "dispatchable_now_count": report.dispatchable_now_count,
        "manual_requeue_count": report.manual_requeue_count,
        "blocked_count": report.blocked_count,
        "candidate_codes": by_code,
        "candidate_severities": by_severity,
    }


def _knowledge_snapshot_schedule_config(settings: Any) -> SnapshotScheduleConfig:
    return SnapshotScheduleConfig(
        daily_enabled=settings.knowledge_snapshot_daily_enabled,
        daily_hour=settings.knowledge_snapshot_daily_hour,
        weekly_enabled=settings.knowledge_snapshot_weekly_enabled,
        weekly_weekday=settings.knowledge_snapshot_weekly_weekday,
        weekly_hour=settings.knowledge_snapshot_weekly_hour,
    )


def _sort_knowledge_snapshot_problem_runs(
    runs: list[AdminKnowledgeSnapshotRunHealthItem],
) -> list[AdminKnowledgeSnapshotRunHealthItem]:
    severity_order = {
        "stale_running": 0,
        "partial_scheduler_lease": 1,
        "running_missing_lease_owner": 2,
        "running_missing_lease_token": 3,
        "running_missing_lease_expiry": 4,
        "running_missing_heartbeat": 5,
        "retryable_failed": 6,
        "exhausted_failed": 7,
        "pending": 8,
        "lease_expiring": 9,
        "legacy_running_without_lease": 10,
    }

    def sort_key(run: AdminKnowledgeSnapshotRunHealthItem) -> tuple[int, datetime, int]:
        severity = min((severity_order.get(flag, 99) for flag in run.health_flags), default=99)
        return (severity, _naive_utc(run.started_at), run.id)

    return sorted(runs, key=sort_key)


def _knowledge_snapshot_run_lease_expired(run: KnowledgeSnapshotRun, now: datetime, lease_seconds: int) -> bool:
    return knowledge_snapshot_lease_is_expired(run, now, lease_seconds)


def _knowledge_snapshot_run_metadata_summary(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    if not metadata:
        return {}, False
    summary: dict[str, Any] = {}
    directly_allowed = {
        "trigger_source",
        "previous_status",
        "previous_attempt_count",
        "cleared_lease",
        "cancelled_at",
        "requeued_at",
    }
    for key in directly_allowed:
        if key in metadata:
            summary[key] = metadata[key]
    if "requeue_reason" in metadata:
        summary["requeue_reason_present"] = bool(str(metadata.get("requeue_reason") or "").strip())
    if "cancelled_by_user_id" in metadata or "requeued_by_user_id" in metadata:
        summary["admin_actor_present"] = True
    redacted_keys = set(metadata) - directly_allowed
    return summary, bool(redacted_keys)


def _knowledge_snapshot_missing_lease_flags(missing_fields: list[str]) -> list[str]:
    flag_by_field = {
        "scheduler_lease_owner": "running_missing_lease_owner",
        "scheduler_lease_token": "running_missing_lease_token",
        "scheduler_lease_expires_at": "running_missing_lease_expiry",
        "scheduler_heartbeat_at": "running_missing_heartbeat",
    }
    return [flag_by_field[field] for field in missing_fields if field in flag_by_field]


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _admin_knowledge_snapshot_run_read(run: KnowledgeSnapshotRun) -> AdminKnowledgeSnapshotRunRead:
    metadata_summary, metadata_redacted = _knowledge_snapshot_run_metadata_summary(run.metadata_json)
    return AdminKnowledgeSnapshotRunRead(
        id=run.id,
        run_key=run.run_key,
        granularity=run.granularity,
        period_start=run.period_start,
        period_end=run.period_end,
        trigger_source=run.trigger_source,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        attempt_count=run.attempt_count,
        user_snapshot_count=run.user_snapshot_count,
        class_snapshot_count=run.class_snapshot_count,
        error_message=run.error_message,
        metadata_summary=metadata_summary,
        metadata_redacted=metadata_redacted,
        created_at=run.created_at,
        updated_at=run.updated_at,
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
        schema_hash=draft.schema_hash,
        base_version_id=draft.base_version_id,
        base_schema_hash=draft.base_schema_hash,
        script_risk_level=draft.script_risk_level,
        script_analysis=draft.script_analysis_json,
        script_review_status=draft.script_review_status,
        script_reviewed_by_user_id=draft.script_reviewed_by_user_id,
        script_reviewed_at=draft.script_reviewed_at,
        script_review_note=draft.script_review_note,
        submitted_at=draft.submitted_at,
        withdrawn_at=draft.withdrawn_at,
        change_requested_by_user_id=draft.change_requested_by_user_id,
        change_requested_at=draft.change_requested_at,
        change_request_note=draft.change_request_note,
        published_page_id=draft.published_page_id,
        published_version_id=draft.published_version_id,
        published_by_user_id=draft.published_by_user_id,
        published_at=draft.published_at,
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
        previous_version_id=version.previous_version_id,
        source_draft_id=version.source_draft_id,
        restored_from_version_id=version.restored_from_version_id,
        published_by_user_id=version.published_by_user_id,
        published_at=version.published_at,
        note=version.note,
        created_at=version.created_at,
    )


def _admin_content_script_asset_read(asset: ContentScriptAsset) -> AdminContentScriptAssetRead:
    return AdminContentScriptAssetRead(
        id=asset.id,
        page_id=asset.page_id,
        page_version_id=asset.page_version_id,
        slug=asset.slug,
        sandbox_id=asset.sandbox_id,
        reference_key=asset.reference_key,
        reference_value_sha256=asset.reference_value_sha256,
        source_host=asset.source_host,
        source_url_sha256=sha256(asset.source_url.encode("utf-8")).hexdigest(),
        matched_algorithm=asset.matched_algorithm,
        asset_sha256=asset.asset_sha256,
        asset_size_bytes=asset.asset_size_bytes,
        policy_version=asset.policy_version,
        policy_context_hash=asset.policy_context_hash,
        published_by_user_id=asset.published_by_user_id,
        published_at=asset.published_at,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _admin_content_script_host_policy_read(row: ContentScriptHostPolicyRow) -> AdminContentScriptHostPolicyRead:
    return AdminContentScriptHostPolicyRead(
        id=row.policy_id,
        source_host=row.source_host,
        status=row.status,
        reason=row.reason,
        configured_allowed=row.configured_allowed,
        observed_asset_count=row.observed_asset_count,
        observed_page_count=row.observed_page_count,
        last_observed_at=row.last_observed_at,
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _admin_content_script_asset_audit_issue_read(
    issue: ContentScriptAssetMirrorAuditIssue,
) -> AdminContentScriptAssetAuditIssueRead:
    return AdminContentScriptAssetAuditIssueRead(
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        page_id=issue.page_id,
        page_version_id=issue.page_version_id,
        slug=issue.slug,
        sandbox_id=issue.sandbox_id,
        reference_key=issue.reference_key,
        reference_value_sha256=issue.reference_value_sha256,
        source_host=issue.source_host,
        source_url_sha256=issue.source_url_sha256,
        asset_id=issue.asset_id,
        asset_sha256=issue.asset_sha256,
        published_at=issue.published_at,
    )


def _admin_content_script_asset_remote_drift_issue_read(
    issue: ContentScriptAssetRemoteDriftIssue,
) -> AdminContentScriptAssetRemoteDriftIssueRead:
    return AdminContentScriptAssetRemoteDriftIssueRead(
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        page_id=issue.page_id,
        page_version_id=issue.page_version_id,
        slug=issue.slug,
        sandbox_id=issue.sandbox_id,
        reference_key=issue.reference_key,
        reference_value_sha256=issue.reference_value_sha256,
        source_host=issue.source_host,
        source_url_sha256=issue.source_url_sha256,
        asset_id=issue.asset_id,
        asset_sha256=issue.asset_sha256,
        remote_asset_sha256=issue.remote_asset_sha256,
        remote_asset_size_bytes=issue.remote_asset_size_bytes,
        published_at=issue.published_at,
    )


def _admin_content_script_asset_scan_run_read(run: ContentScriptAssetScanRun) -> AdminContentScriptAssetScanRunRead:
    return AdminContentScriptAssetScanRunRead(
        id=run.id,
        run_key=run.run_key,
        scan_type=run.scan_type,
        trigger_source=run.trigger_source,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_by_user_id=run.created_by_user_id,
        attempt_count=run.attempt_count,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        filters_json=run.filters_json,
        totals_json=run.totals_json,
        issue_counts_json=run.issue_counts_json,
        alert_status=run.alert_status,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _admin_content_script_asset_scan_health_report(
    report: ContentScriptAssetScanHealthReportRow,
) -> AdminContentScriptAssetScanHealthReport:
    return AdminContentScriptAssetScanHealthReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        health_status=report.health_status,
        total=report.total,
        by_status=[
            AdminContentScriptAssetScanRunStatusBucket(status=item.status, total=item.total) for item in report.by_status
        ],
        running_count=report.running_count,
        active_running_count=report.active_running_count,
        stale_running_count=report.stale_running_count,
        lease_expiring_count=report.lease_expiring_count,
        legacy_running_without_lease_count=report.legacy_running_without_lease_count,
        claimable_count=report.claimable_count,
        success_count=report.success_count,
        failed_count=report.failed_count,
        warning_run_count=report.warning_run_count,
        critical_run_count=report.critical_run_count,
        issue_run_count=report.issue_run_count,
        needs_attention_count=report.needs_attention_count,
        problem_count=report.problem_count,
        problem_runs=[_admin_content_script_asset_scan_health_item(item) for item in report.problem_runs],
        newest_finished_at=report.newest_finished_at,
        oldest_running_started_at=report.oldest_running_started_at,
        next_lease_expires_at=report.next_lease_expires_at,
    )


def _admin_content_script_asset_scan_health_item(
    item: ContentScriptAssetScanHealthItemRow,
) -> AdminContentScriptAssetScanHealthItem:
    return AdminContentScriptAssetScanHealthItem(
        id=item.id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        trigger_source=item.trigger_source,
        status=item.status,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
        error_message=item.error_message,
        health_flags=item.health_flags,
        retryable=item.retryable,
        claimable=item.claimable,
        lease_seconds_remaining=item.lease_seconds_remaining,
    )


def _admin_content_script_asset_scan_queue_report(
    report: ContentScriptAssetScanQueueReportRow,
) -> AdminContentScriptAssetScanQueueReport:
    return AdminContentScriptAssetScanQueueReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        queue_status=report.queue_status,
        backlog_count=report.backlog_count,
        ready_count=report.ready_count,
        dispatchable_now_count=report.dispatchable_now_count,
        claimable_by_lease_rule_count=report.claimable_by_lease_rule_count,
        manual_review_count=report.manual_review_count,
        blocked_count=report.blocked_count,
        failed_count=report.failed_count,
        stale_running_count=report.stale_running_count,
        active_running_count=report.active_running_count,
        legacy_running_without_lease_count=report.legacy_running_without_lease_count,
        by_trigger_source=report.by_trigger_source,
        ready_jobs=[_admin_content_script_asset_scan_queue_item(item) for item in report.ready_jobs],
        manual_review_runs=[_admin_content_script_asset_scan_queue_item(item) for item in report.manual_review_runs],
        blocked_runs=[_admin_content_script_asset_scan_queue_item(item) for item in report.blocked_runs],
        current_window=[_admin_content_script_asset_scan_queue_item(item) for item in report.current_window],
        oldest_ready_at=report.oldest_ready_at,
        oldest_manual_review_at=report.oldest_manual_review_at,
        next_lease_expires_at=report.next_lease_expires_at,
    )


def _admin_content_script_asset_scan_queue_item(
    item: ContentScriptAssetScanQueueItemRow,
) -> AdminContentScriptAssetScanQueueItem:
    return AdminContentScriptAssetScanQueueItem(
        source=item.source,
        reason=item.reason,
        ready=item.ready,
        claimable=item.claimable,
        run_id=item.run_id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        status=item.status,
        trigger_source=item.trigger_source,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
    )


def _admin_content_script_asset_scan_alert_report(
    report: ContentScriptAssetScanAlertReportRow,
) -> AdminContentScriptAssetScanAlertReport:
    return AdminContentScriptAssetScanAlertReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        alert_status=report.alert_status,
        candidate_count=report.candidate_count,
        critical_count=report.critical_count,
        warning_count=report.warning_count,
        info_count=report.info_count,
        recent_run_count=report.recent_run_count,
        issue_run_count=report.issue_run_count,
        candidates=[_admin_content_script_asset_scan_alert_candidate(item) for item in report.candidates],
    )


def _admin_content_script_asset_scan_alert_candidate(
    item: ContentScriptAssetScanAlertCandidateRow,
) -> AdminContentScriptAssetScanAlertCandidate:
    return AdminContentScriptAssetScanAlertCandidate(
        severity=item.severity,
        code=item.code,
        source=item.source,
        action_hint=item.action_hint,
        run_id=item.run_id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        trigger_source=item.trigger_source,
        status=item.status,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        slug=item.slug,
        page_id=item.page_id,
        page_version_id=item.page_version_id,
        sandbox_id=item.sandbox_id,
        reference_key=item.reference_key,
        reference_value_sha256=item.reference_value_sha256,
        source_host=item.source_host,
        source_url_sha256=item.source_url_sha256,
        asset_id=item.asset_id,
        asset_sha256=item.asset_sha256,
        remote_asset_sha256=item.remote_asset_sha256,
        remote_asset_size_bytes=item.remote_asset_size_bytes,
        published_at=item.published_at,
    )


def _admin_alert_outbox_write_response(write_result: Any) -> AdminAlertOutboxWriteResponse:
    return AdminAlertOutboxWriteResponse(
        generated_at=write_result.generated_at,
        source_type=write_result.source_type,
        status=write_result.status,
        dispatch_mode=write_result.dispatch_mode,
        delivery_target=write_result.delivery_target,
        external_delivery=write_result.external_delivery,
        candidate_count=write_result.candidate_count,
        created_count=write_result.created_count,
        refreshed_count=write_result.refreshed_count,
        skipped_count=write_result.skipped_count,
        items=[_admin_alert_outbox_entry_read(entry) for entry in write_result.entries],
    )


def _admin_background_task_read(task: BackgroundTask) -> AdminBackgroundTaskRead:
    now_at = datetime.now(UTC)
    lease_active = (
        task.status == "leased"
        and task.lease_expires_at is not None
        and _naive_utc(task.lease_expires_at) > _naive_utc(now_at)
    )
    return AdminBackgroundTaskRead(
        id=task.id,
        task_type=task.task_type,
        source_type=task.source_type,
        source_id=task.source_id,
        status=task.status,
        priority=task.priority,
        idempotency_key_prefix=task.idempotency_key[:12],
        payload_redacted=True,
        result_summary=dict(task.result_summary_json or {}),
        available_at=task.available_at,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        last_error_code=task.last_error_code,
        lease_owner=task.lease_owner,
        lease_active=lease_active,
        lease_expires_at=task.lease_expires_at,
        heartbeat_at=task.heartbeat_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_by_user_id=task.created_by_user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _admin_background_task_attempt_read(
    attempt: BackgroundTaskAttempt,
) -> AdminBackgroundTaskAttemptRead:
    return AdminBackgroundTaskAttemptRead(
        id=attempt.id,
        task_id=attempt.task_id,
        attempt_number=attempt.attempt_number,
        worker_id=attempt.worker_id,
        status=attempt.status,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_code=attempt.error_code,
        retryable=attempt.retryable,
        result_summary=dict(attempt.result_summary_json or {}),
    )


def _admin_alert_outbox_entry_read(entry: AdminAlertOutboxEntry) -> AdminAlertOutboxEntryRead:
    return AdminAlertOutboxEntryRead(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,
        dispatch_mode=entry.dispatch_mode,
        delivery_target=entry.delivery_target,
        external_delivery=entry.external_delivery,
        payload_hash_prefix=entry.payload_hash[:12],
        payload_redacted=True,
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        expires_at=entry.expires_at,
        seen_count=entry.seen_count,
        attempt_count=entry.attempt_count,
        last_error_code=entry.last_error_code,
        created_by_user_id=entry.created_by_user_id,
        reviewed_by_user_id=entry.reviewed_by_user_id,
        reviewed_at=entry.reviewed_at,
        review_note_present=bool(entry.review_note),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _admin_alert_outbox_queue_report(
    entries: list[AdminAlertOutboxEntry],
    *,
    generated_at: datetime,
    filters: dict[str, Any],
    stale_after_hours: int,
    item_limit: int,
) -> AdminAlertOutboxQueueReport:
    stale_before = generated_at - timedelta(hours=stale_after_hours)
    pending_review = [entry for entry in entries if entry.status == "pending_review"]
    planned = [entry for entry in entries if entry.status == "planned"]
    queued = [entry for entry in entries if entry.status == "queued"]
    dispatching = [entry for entry in entries if entry.status == "dispatching"]
    delivered = [entry for entry in entries if entry.status == "delivered"]
    failed = [entry for entry in entries if entry.status == "failed"]
    suppressed = [entry for entry in entries if entry.status == "suppressed"]
    cancelled = [entry for entry in entries if entry.status == "cancelled"]
    stale_pending_review = [
        entry for entry in pending_review if _naive_utc(entry.last_seen_at) <= _naive_utc(stale_before)
    ]
    due_planned = [entry for entry in planned if _admin_alert_outbox_entry_due(entry, generated_at)]
    due_queued = [entry for entry in queued if _admin_alert_outbox_entry_due(entry, generated_at)]
    ready_entries = _sort_admin_alert_outbox_queue_items(due_queued + due_planned)
    active_count = len(pending_review) + len(planned) + len(queued) + len(dispatching) + len(failed)
    terminal_count = len(delivered) + len(suppressed) + len(cancelled)
    if ready_entries or dispatching:
        queue_status: Literal["empty", "review_required", "ready", "cleared"] = "ready"
    elif pending_review or failed:
        queue_status = "review_required"
    elif entries:
        queue_status = "cleared"
    else:
        queue_status = "empty"
    status_order = [
        "pending_review",
        "planned",
        "queued",
        "dispatching",
        "failed",
        "delivered",
        "suppressed",
        "cancelled",
    ]
    buckets = [
        _admin_alert_outbox_status_bucket(status, [entry for entry in entries if entry.status == status])
        for status in status_order
    ]
    filtered_snapshot_filters = {key: value for key, value in filters.items() if value is not None}
    return AdminAlertOutboxQueueReport(
        generated_at=generated_at,
        filters=filtered_snapshot_filters,
        policy={
            "external_delivery": bool(
                alert_delivery_posture(get_settings())["enabled"]
                and alert_delivery_posture(get_settings())["configured"]
            ),
            "delivery_posture": alert_delivery_posture(get_settings()),
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
            "stale_after_hours": stale_after_hours,
        },
        queue_status=queue_status,
        total_count=len(entries),
        active_count=active_count,
        pending_review_count=len(pending_review),
        planned_count=len(planned),
        queued_count=len(queued),
        dispatching_count=len(dispatching),
        delivered_count=len(delivered),
        failed_count=len(failed),
        suppressed_count=len(suppressed),
        cancelled_count=len(cancelled),
        terminal_count=terminal_count,
        stale_pending_review_count=len(stale_pending_review),
        due_planned_count=len(due_planned),
        due_queued_count=len(due_queued),
        external_delivery_count=sum(1 for entry in entries if entry.external_delivery),
        oldest_pending_review_at=_oldest_datetime(entry.last_seen_at for entry in pending_review),
        oldest_due_at=_oldest_datetime(
            (entry.available_at or entry.last_seen_at) for entry in due_planned + due_queued
        ),
        status_buckets=buckets,
        pending_review_items=[
            _admin_alert_outbox_queue_item(entry)
            for entry in _sort_admin_alert_outbox_queue_items(pending_review + failed)[:item_limit]
        ],
        ready_items=[_admin_alert_outbox_queue_item(entry) for entry in ready_entries[:item_limit]],
        terminal_items=[
            _admin_alert_outbox_queue_item(entry)
            for entry in _sort_admin_alert_outbox_queue_items(delivered + suppressed + cancelled)[:item_limit]
        ],
    )


def _admin_alert_outbox_queue_snapshot(report: AdminAlertOutboxQueueReport) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_queue",
        "queue_status": report.queue_status,
        "filters": {key: _admin_alert_outbox_snapshot_value(value) for key, value in report.filters.items()},
        "policy": report.policy,
        "total_count": report.total_count,
        "active_count": report.active_count,
        "pending_review_count": report.pending_review_count,
        "planned_count": report.planned_count,
        "queued_count": report.queued_count,
        "dispatching_count": report.dispatching_count,
        "delivered_count": report.delivered_count,
        "failed_count": report.failed_count,
        "suppressed_count": report.suppressed_count,
        "cancelled_count": report.cancelled_count,
        "terminal_count": report.terminal_count,
        "stale_pending_review_count": report.stale_pending_review_count,
        "due_planned_count": report.due_planned_count,
        "due_queued_count": report.due_queued_count,
        "external_delivery_count": report.external_delivery_count,
        "oldest_pending_review_at": report.oldest_pending_review_at.isoformat()
        if report.oldest_pending_review_at is not None
        else None,
        "oldest_due_at": report.oldest_due_at.isoformat() if report.oldest_due_at is not None else None,
        "status_buckets": {bucket.status: bucket.total for bucket in report.status_buckets},
        "automatic_actions": False,
        "external_delivery": report.policy["external_delivery"],
    }


def _admin_alert_outbox_dispatch_dry_run_report(
    entries: list[AdminAlertOutboxEntry],
    *,
    generated_at: datetime,
    filters: dict[str, Any],
    item_limit: int,
) -> AdminAlertOutboxDispatchDryRunReport:
    active_entries = [
        entry
        for entry in entries
        if entry.status in {"pending_review", "planned", "queued", "dispatching", "failed"}
    ]
    terminal_entries = [entry for entry in entries if entry.status in {"delivered", "suppressed", "cancelled"}]
    expired_entries = [
        entry for entry in active_entries if _admin_alert_outbox_entry_expired(entry, generated_at)
    ]
    ready_entries = [
        entry
        for entry in active_entries
        if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at)
    ]
    ready_entry_ids = {entry.id for entry in ready_entries}
    not_due_entries = [
        entry
        for entry in active_entries
        if _admin_alert_outbox_entry_dispatch_not_due(entry, generated_at)
    ]
    not_due_entry_ids = {entry.id for entry in not_due_entries}
    expired_entry_ids = {entry.id for entry in expired_entries}
    blocked_entries = [
        entry
        for entry in active_entries
        if entry.id not in ready_entry_ids
        and entry.id not in not_due_entry_ids
        and entry.id not in expired_entry_ids
    ]
    if ready_entries:
        dry_run_status: Literal["empty", "blocked", "expired", "ready", "cleared"] = "ready"
    elif blocked_entries or not_due_entries:
        dry_run_status = "blocked"
    elif expired_entries:
        dry_run_status = "expired"
    elif entries:
        dry_run_status = "cleared"
    else:
        dry_run_status = "empty"
    filtered_snapshot_filters = {key: value for key, value in filters.items() if value is not None}
    return AdminAlertOutboxDispatchDryRunReport(
        generated_at=generated_at,
        filters=filtered_snapshot_filters,
        policy={
            "dry_run": True,
            "writes_outbox_state": False,
            "increments_attempts": False,
            "external_delivery": False,
            "broker_delivery": False,
            "automatic_actions": False,
            "dispatch_mode": "manual_review",
            "delivery_target": "admin_outbox",
        },
        dry_run_status=dry_run_status,
        total_count=len(entries),
        active_count=len(active_entries),
        pending_review_count=sum(1 for entry in active_entries if entry.status == "pending_review"),
        planned_count=sum(1 for entry in active_entries if entry.status == "planned"),
        queued_count=sum(1 for entry in active_entries if entry.status == "queued"),
        ready_count=len(ready_entries),
        blocked_count=len(blocked_entries),
        expired_count=len(expired_entries),
        not_due_count=len(not_due_entries),
        terminal_count=len(terminal_entries),
        external_delivery_count=sum(1 for entry in entries if entry.external_delivery),
        blocked_reason_counts=_admin_alert_outbox_dispatch_entry_reason_counts(blocked_entries, generated_at),
        ready_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(ready_entries)[:item_limit]
        ],
        blocked_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(blocked_entries)[:item_limit]
        ],
        expired_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(expired_entries)[:item_limit]
        ],
        not_due_items=[
            _admin_alert_outbox_dispatch_dry_run_item(entry, generated_at)
            for entry in _sort_admin_alert_outbox_queue_items(not_due_entries)[:item_limit]
        ],
    )


def _admin_alert_outbox_dispatch_dry_run_snapshot(report: AdminAlertOutboxDispatchDryRunReport) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_dry_run",
        "dry_run_status": report.dry_run_status,
        "filters": {key: _admin_alert_outbox_snapshot_value(value) for key, value in report.filters.items()},
        "policy": report.policy,
        "total_count": report.total_count,
        "active_count": report.active_count,
        "pending_review_count": report.pending_review_count,
        "planned_count": report.planned_count,
        "queued_count": report.queued_count,
        "ready_count": report.ready_count,
        "blocked_count": report.blocked_count,
        "expired_count": report.expired_count,
        "not_due_count": report.not_due_count,
        "terminal_count": report.terminal_count,
        "external_delivery_count": report.external_delivery_count,
        "ready_entry_ids": [item.id for item in report.ready_items],
        "blocked_reason_counts": report.blocked_reason_counts,
        "expired_entry_ids": [item.id for item in report.expired_items],
        "not_due_entry_ids": [item.id for item in report.not_due_items],
    }


def _admin_alert_outbox_dispatch_entries_for_request(
    db: Session,
    *,
    entry_ids: list[int] | None,
    source_type: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    now_at: datetime | None,
    entry_limit: int,
) -> tuple[list[AdminAlertOutboxEntry], dict[str, Any], datetime]:
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from_at must be earlier than to_at")
    unique_entry_ids: list[int] | None = None
    if entry_ids is not None:
        unique_entry_ids = list(dict.fromkeys(entry_ids))
        if len(unique_entry_ids) != len(entry_ids):
            raise HTTPException(status_code=422, detail="entry_ids must be unique")
    generated_at = now_at or datetime.now(UTC)
    filters = {
        "entry_ids": unique_entry_ids,
        "source_type": source_type.strip() if source_type is not None and source_type.strip() else None,
        "from_at": from_at,
        "to_at": to_at,
        "now_at": generated_at,
        "entry_limit": entry_limit,
    }
    statement = select(AdminAlertOutboxEntry)
    if unique_entry_ids is not None:
        statement = statement.where(AdminAlertOutboxEntry.id.in_(unique_entry_ids))
    if filters["source_type"] is not None:
        statement = statement.where(AdminAlertOutboxEntry.source_type == filters["source_type"])
    if from_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at >= from_at)
    if to_at is not None:
        statement = statement.where(AdminAlertOutboxEntry.last_seen_at <= to_at)
    entries = list(
        db.scalars(statement.order_by(AdminAlertOutboxEntry.last_seen_at.desc(), AdminAlertOutboxEntry.id.desc())).all()
    )
    if unique_entry_ids is not None:
        found_ids = {entry.id for entry in entries}
        missing_ids = [entry_id for entry_id in unique_entry_ids if entry_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail={"message": "Alert outbox entries not found", "missing_ids": missing_ids},
            )
    return entries, filters, generated_at


def _admin_alert_outbox_dispatch_plan_key(generated_at: datetime) -> str:
    return sha256(f"{uuid4().hex}:{generated_at.isoformat()}".encode("utf-8")).hexdigest()


def _admin_alert_outbox_dispatch_plan_read(
    plan: AdminAlertOutboxDispatchPlan,
) -> AdminAlertOutboxDispatchPlanRead:
    ready_entry_ids = [int(entry_id) for entry_id in list(plan.ready_entry_ids_json or [])]
    return AdminAlertOutboxDispatchPlanRead(
        id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        generated_at=plan.generated_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        created_by_user_id=plan.created_by_user_id,
        source_type=plan.source_type,
        filters=plan.filters_json or {},
        policy=plan.policy_json or {},
        dry_run_status=plan.dry_run_status,  # type: ignore[arg-type]
        total_count=plan.total_count,
        active_count=plan.active_count,
        ready_count=plan.ready_count,
        blocked_count=plan.blocked_count,
        expired_count=plan.expired_count,
        not_due_count=plan.not_due_count,
        terminal_count=plan.terminal_count,
        external_delivery_count=plan.external_delivery_count,
        ready_entry_ids=ready_entry_ids,
        ready_entry_count=len(ready_entry_ids),
        truncated_ready_entry_ids=plan.ready_count > len(ready_entry_ids),
        blocked_reason_counts=plan.blocked_reason_counts_json or {},
    )


def _admin_alert_outbox_dispatch_plan_snapshot(plan: AdminAlertOutboxDispatchPlanRead) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_plan",
        "plan_id": plan.id,
        "plan_key": plan.plan_key,
        "plan_status": plan.plan_status,
        "dry_run_status": plan.dry_run_status,
        "filters": plan.filters,
        "policy": plan.policy,
        "total_count": plan.total_count,
        "active_count": plan.active_count,
        "ready_count": plan.ready_count,
        "blocked_count": plan.blocked_count,
        "expired_count": plan.expired_count,
        "not_due_count": plan.not_due_count,
        "terminal_count": plan.terminal_count,
        "external_delivery_count": plan.external_delivery_count,
        "ready_entry_ids": plan.ready_entry_ids,
        "ready_entry_count": plan.ready_entry_count,
        "truncated_ready_entry_ids": plan.truncated_ready_entry_ids,
        "blocked_reason_counts": plan.blocked_reason_counts,
    }


def _admin_alert_outbox_dispatch_plan_validation_report(
    plan: AdminAlertOutboxDispatchPlan,
    db: Session,
    generated_at: datetime,
) -> AdminAlertOutboxDispatchPlanValidationReport:
    planned_entry_ids = [int(entry_id) for entry_id in list(plan.ready_entry_ids_json or [])]
    planned_hashes = {str(key): str(value) for key, value in (plan.ready_entry_payload_hashes_json or {}).items()}
    if not planned_entry_ids:
        return AdminAlertOutboxDispatchPlanValidationReport(
            generated_at=generated_at,
            plan_id=plan.id,
            plan_key=plan.plan_key,
            plan_status=plan.plan_status,  # type: ignore[arg-type]
            validation_status="empty",
            policy=_admin_alert_outbox_dispatch_plan_validation_policy(plan),
            planned_ready_count=0,
            current_ready_count=0,
            missing_count=0,
            payload_hash_mismatch_count=0,
            payload_hash_snapshot_missing_count=0,
            blocked_count=0,
            expired_count=0,
            not_due_count=0,
            payload_hash_snapshot_available=True,
            ready_entry_ids=[],
            missing_entry_ids=[],
            payload_hash_mismatch_entry_ids=[],
            payload_hash_snapshot_missing_entry_ids=[],
            blocked_entry_ids=[],
            expired_entry_ids=[],
            not_due_entry_ids=[],
            blocked_reason_counts={},
        )
    entries = list(
        db.scalars(select(AdminAlertOutboxEntry).where(AdminAlertOutboxEntry.id.in_(planned_entry_ids))).all()
    )
    entry_by_id = {entry.id: entry for entry in entries}
    ready_entry_ids: list[int] = []
    missing_entry_ids: list[int] = []
    mismatch_entry_ids: list[int] = []
    snapshot_missing_entry_ids: list[int] = []
    blocked_entry_ids: list[int] = []
    expired_entry_ids: list[int] = []
    not_due_entry_ids: list[int] = []
    blocked_reason_counts: dict[str, int] = {}
    for entry_id in planned_entry_ids:
        entry = entry_by_id.get(entry_id)
        if entry is None:
            missing_entry_ids.append(entry_id)
            blocked_reason_counts["missing_entry"] = blocked_reason_counts.get("missing_entry", 0) + 1
            continue
        planned_hash = planned_hashes.get(str(entry_id))
        if planned_hash is None:
            snapshot_missing_entry_ids.append(entry_id)
            blocked_entry_ids.append(entry_id)
            reason = "payload_hash_snapshot_missing"
            blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
            continue
        if entry.payload_hash != planned_hash:
            mismatch_entry_ids.append(entry_id)
            blocked_entry_ids.append(entry_id)
            blocked_reason_counts["payload_hash_mismatch"] = blocked_reason_counts.get("payload_hash_mismatch", 0) + 1
            continue
        if _admin_alert_outbox_entry_dispatch_ready(entry, generated_at):
            ready_entry_ids.append(entry_id)
            continue
        if _admin_alert_outbox_entry_expired(entry, generated_at):
            expired_entry_ids.append(entry_id)
            blocked_reason_counts["expired"] = blocked_reason_counts.get("expired", 0) + 1
            continue
        if _admin_alert_outbox_entry_dispatch_not_due(entry, generated_at):
            not_due_entry_ids.append(entry_id)
            blocked_reason_counts["queued_not_due"] = blocked_reason_counts.get("queued_not_due", 0) + 1
            continue
        reason = _admin_alert_outbox_dispatch_reason(entry, generated_at)
        blocked_entry_ids.append(entry_id)
        blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
    validation_status: Literal["valid", "changed", "empty"] = (
        "valid"
        if len(ready_entry_ids) == len(planned_entry_ids)
        and not missing_entry_ids
        and not mismatch_entry_ids
        and not snapshot_missing_entry_ids
        and not blocked_entry_ids
        and not expired_entry_ids
        and not not_due_entry_ids
        else "changed"
    )
    return AdminAlertOutboxDispatchPlanValidationReport(
        generated_at=generated_at,
        plan_id=plan.id,
        plan_key=plan.plan_key,
        plan_status=plan.plan_status,  # type: ignore[arg-type]
        validation_status=validation_status,
        policy=_admin_alert_outbox_dispatch_plan_validation_policy(plan),
        planned_ready_count=len(planned_entry_ids),
        current_ready_count=len(ready_entry_ids),
        missing_count=len(missing_entry_ids),
        payload_hash_mismatch_count=len(mismatch_entry_ids),
        payload_hash_snapshot_missing_count=len(snapshot_missing_entry_ids),
        blocked_count=len(blocked_entry_ids),
        expired_count=len(expired_entry_ids),
        not_due_count=len(not_due_entry_ids),
        payload_hash_snapshot_available=not snapshot_missing_entry_ids,
        ready_entry_ids=ready_entry_ids,
        missing_entry_ids=missing_entry_ids,
        payload_hash_mismatch_entry_ids=mismatch_entry_ids,
        payload_hash_snapshot_missing_entry_ids=snapshot_missing_entry_ids,
        blocked_entry_ids=blocked_entry_ids,
        expired_entry_ids=expired_entry_ids,
        not_due_entry_ids=not_due_entry_ids,
        blocked_reason_counts=blocked_reason_counts,
    )


def _admin_alert_outbox_dispatch_plan_validation_policy(plan: AdminAlertOutboxDispatchPlan) -> dict[str, Any]:
    return {
        "dry_run": True,
        "validates_plan": True,
        "validates_payload_hashes": True,
        "writes_outbox_state": False,
        "increments_attempts": False,
        "external_delivery": False,
        "broker_delivery": False,
        "automatic_actions": False,
        "dispatch_mode": "manual_review",
        "delivery_target": "admin_outbox",
        "plan_id": plan.id,
        "plan_key": plan.plan_key,
    }


def _admin_alert_outbox_dispatch_plan_validation_snapshot(
    report: AdminAlertOutboxDispatchPlanValidationReport,
) -> dict[str, Any]:
    return {
        "format": "admin_alert_outbox_dispatch_plan_validation",
        "plan_id": report.plan_id,
        "plan_key": report.plan_key,
        "plan_status": report.plan_status,
        "validation_status": report.validation_status,
        "policy": report.policy,
        "planned_ready_count": report.planned_ready_count,
        "current_ready_count": report.current_ready_count,
        "missing_count": report.missing_count,
        "payload_hash_mismatch_count": report.payload_hash_mismatch_count,
        "payload_hash_snapshot_missing_count": report.payload_hash_snapshot_missing_count,
        "blocked_count": report.blocked_count,
        "expired_count": report.expired_count,
        "not_due_count": report.not_due_count,
        "payload_hash_snapshot_available": report.payload_hash_snapshot_available,
        "ready_entry_ids": report.ready_entry_ids,
        "missing_entry_ids": report.missing_entry_ids,
        "payload_hash_mismatch_entry_ids": report.payload_hash_mismatch_entry_ids,
        "payload_hash_snapshot_missing_entry_ids": report.payload_hash_snapshot_missing_entry_ids,
        "blocked_entry_ids": report.blocked_entry_ids,
        "expired_entry_ids": report.expired_entry_ids,
        "not_due_entry_ids": report.not_due_entry_ids,
        "blocked_reason_counts": report.blocked_reason_counts,
    }


def _admin_alert_outbox_snapshot_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _admin_alert_outbox_snapshot_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_admin_alert_outbox_snapshot_value(item) for item in value]
    return value


def _admin_alert_outbox_entry_due(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return entry.available_at is None or _naive_utc(entry.available_at) <= _naive_utc(now_at)


def _admin_alert_outbox_entry_expired(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return entry.expires_at is not None and _naive_utc(entry.expires_at) <= _naive_utc(now_at)


def _admin_alert_outbox_entry_dispatch_ready(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return (
        entry.status == "queued"
        and _admin_alert_outbox_entry_due(entry, now_at)
        and not _admin_alert_outbox_entry_expired(entry, now_at)
        and not entry.external_delivery
        and entry.dispatch_mode == "manual_review"
        and entry.delivery_target == "admin_outbox"
    )


def _admin_alert_outbox_entry_dispatch_not_due(entry: AdminAlertOutboxEntry, now_at: datetime) -> bool:
    return (
        entry.status == "queued"
        and not _admin_alert_outbox_entry_due(entry, now_at)
        and not _admin_alert_outbox_entry_expired(entry, now_at)
        and not entry.external_delivery
        and entry.dispatch_mode == "manual_review"
        and entry.delivery_target == "admin_outbox"
    )


def _admin_alert_outbox_status_bucket(
    status: str,
    entries: list[AdminAlertOutboxEntry],
) -> AdminAlertOutboxStatusBucket:
    return AdminAlertOutboxStatusBucket(
        status=status,  # type: ignore[arg-type]
        total=len(entries),
        critical_count=sum(1 for entry in entries if entry.severity == "critical"),
        warning_count=sum(1 for entry in entries if entry.severity == "warning"),
        info_count=sum(1 for entry in entries if entry.severity == "info"),
        oldest_last_seen_at=_oldest_datetime(entry.last_seen_at for entry in entries),
        latest_last_seen_at=_latest_datetime(entry.last_seen_at for entry in entries),
        oldest_available_at=_oldest_datetime(entry.available_at for entry in entries if entry.available_at is not None),
        latest_reviewed_at=_latest_datetime(entry.reviewed_at for entry in entries if entry.reviewed_at is not None),
    )


def _admin_alert_outbox_dispatch_dry_run_item(
    entry: AdminAlertOutboxEntry,
    now_at: datetime,
) -> AdminAlertOutboxDispatchDryRunItem:
    return AdminAlertOutboxDispatchDryRunItem(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,  # type: ignore[arg-type]
        reason=_admin_alert_outbox_dispatch_reason(entry, now_at),
        dispatch_mode=entry.dispatch_mode,
        delivery_target=entry.delivery_target,
        external_delivery=entry.external_delivery,
        payload_hash_prefix=entry.payload_hash[:12],
        delivery_key=_admin_alert_outbox_delivery_key(entry),
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        expires_at=entry.expires_at,
        reviewed_at=entry.reviewed_at,
        attempt_count=entry.attempt_count,
    )


def _admin_alert_outbox_dispatch_reason(entry: AdminAlertOutboxEntry, now_at: datetime) -> str:
    if _admin_alert_outbox_entry_expired(entry, now_at):
        return "expired"
    if entry.status == "dispatching":
        return "dispatch_in_progress"
    if entry.status == "failed":
        return "failed_requires_manual_requeue"
    if entry.external_delivery:
        return "external_delivery_disabled"
    if entry.dispatch_mode != "manual_review":
        return "unsupported_dispatch_mode"
    if entry.delivery_target != "admin_outbox":
        return "unsupported_delivery_target"
    if entry.status == "pending_review":
        return "pending_review"
    if entry.status == "planned":
        return "planned_not_queued"
    if entry.status == "queued" and not _admin_alert_outbox_entry_due(entry, now_at):
        return "queued_not_due"
    if entry.status == "queued":
        return "queued_due"
    return "terminal"


def _admin_alert_outbox_delivery_key(entry: AdminAlertOutboxEntry) -> str:
    return sha256(f"{entry.id}:{entry.source_type}:{entry.event_code}:{entry.payload_hash}".encode("utf-8")).hexdigest()[
        :16
    ]


def _admin_alert_outbox_dispatch_entry_reason_counts(
    entries: list[AdminAlertOutboxEntry],
    now_at: datetime,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        reason = _admin_alert_outbox_dispatch_reason(entry, now_at)
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _admin_alert_outbox_queue_item(entry: AdminAlertOutboxEntry) -> AdminAlertOutboxQueueItem:
    return AdminAlertOutboxQueueItem(
        id=entry.id,
        source_type=entry.source_type,
        source_id=entry.source_id,
        source_key=entry.source_key,
        event_code=entry.event_code,
        severity=entry.severity,
        action_hint=entry.action_hint,
        status=entry.status,  # type: ignore[arg-type]
        external_delivery=entry.external_delivery,
        last_seen_at=entry.last_seen_at,
        available_at=entry.available_at,
        reviewed_at=entry.reviewed_at,
        seen_count=entry.seen_count,
    )


def _sort_admin_alert_outbox_queue_items(entries: list[AdminAlertOutboxEntry]) -> list[AdminAlertOutboxEntry]:
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    status_order = {
        "queued": 0,
        "planned": 1,
        "dispatching": 2,
        "failed": 3,
        "pending_review": 4,
        "delivered": 5,
        "suppressed": 6,
        "cancelled": 7,
    }
    return sorted(
        entries,
        key=lambda entry: (
            status_order.get(entry.status, 99),
            severity_order.get(entry.severity, 99),
            _naive_utc(entry.available_at or entry.last_seen_at),
            _naive_utc(entry.last_seen_at),
            entry.id,
        ),
    )


def _oldest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return min(items, key=_naive_utc) if items else None


def _latest_datetime(values: Any) -> datetime | None:
    items = [value for value in values if value is not None]
    return max(items, key=_naive_utc) if items else None


def _content_script_asset_filters(
    *,
    slug: str | None,
    source_host: str | None,
    sandbox_id: str | None,
    page_id: int | None,
    page_version_id: int | None,
    published_by_user_id: int | None,
    policy_version: str | None,
    policy_context_hash: str | None,
    asset_sha256: str | None,
    reference_value_sha256: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    q: str | None,
) -> dict[str, Any]:
    return {
        "slug": slug.strip("/") if slug is not None and slug.strip("/") else None,
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "sandbox_id": sandbox_id.strip() if sandbox_id is not None and sandbox_id.strip() else None,
        "page_id": page_id,
        "page_version_id": page_version_id,
        "published_by_user_id": published_by_user_id,
        "policy_version": policy_version.strip() if policy_version is not None and policy_version.strip() else None,
        "policy_context_hash": policy_context_hash.strip().lower()
        if policy_context_hash is not None and policy_context_hash.strip()
        else None,
        "asset_sha256": asset_sha256.strip().lower() if asset_sha256 is not None and asset_sha256.strip() else None,
        "reference_value_sha256": reference_value_sha256.strip().lower()
        if reference_value_sha256 is not None and reference_value_sha256.strip()
        else None,
        "from": from_at,
        "to": to_at,
        "q": q.strip() if q is not None and q.strip() else None,
    }


def _content_script_host_policy_filters(
    *,
    source_host: str | None,
    policy_status: str | None,
    q: str | None,
) -> dict[str, Any]:
    filters = {
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "status": policy_status.strip().lower() if policy_status is not None and policy_status.strip() else None,
        "q": q.strip() if q is not None and q.strip() else None,
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_scan_run_filters(
    *,
    status_filter: str | None,
    trigger_source: str | None,
    alert_status: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters = {
        "scan_type": "remote_drift",
        "status": status_filter.strip().lower() if status_filter is not None and status_filter.strip() else None,
        "trigger_source": trigger_source.strip().lower()
        if trigger_source is not None and trigger_source.strip()
        else None,
        "alert_status": alert_status.strip().lower() if alert_status is not None and alert_status.strip() else None,
        "from": from_at.isoformat() if from_at is not None else None,
        "to": to_at.isoformat() if to_at is not None else None,
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_remote_drift_scan_request_filters(
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
) -> dict[str, Any]:
    filters = {
        "slug": request_body.slug.strip("/") if request_body.slug is not None and request_body.slug.strip("/") else None,
        "source_host": (
            request_body.source_host.strip().lower()
            if request_body.source_host is not None and request_body.source_host.strip()
            else None
        ),
        "issue_code": (
            request_body.issue_code.strip().lower()
            if request_body.issue_code is not None and request_body.issue_code.strip()
            else None
        ),
        "severity": request_body.severity,
        "limit": request_body.limit,
        "offset": request_body.offset,
        "confirm_external_network": bool(request_body.confirm_external_network),
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_mirror_audit_snapshot(
    report: ContentScriptAssetMirrorAuditReport,
    *,
    slug: str | None,
    source_host: str | None,
    issue_code: str | None,
    severity: str | None,
    limit: int,
    offset: int,
    item_count: int,
) -> dict[str, Any]:
    filters = {
        "slug": slug.strip("/") if slug is not None and slug.strip("/") else None,
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "issue_code": issue_code.strip().lower() if issue_code is not None and issue_code.strip() else None,
        "severity": severity,
    }
    return {
        "filters": {key: value for key, value in filters.items() if value is not None},
        "generated_at": report.generated_at.isoformat(),
        "total_pages_scanned": report.total_pages_scanned,
        "total_external_references": report.total_external_references,
        "total_issues": report.total_issues,
        "issue_counts_by_code": report.issue_counts_by_code,
        "issue_counts_by_severity": report.issue_counts_by_severity,
        "limit": limit,
        "offset": offset,
        "item_count": item_count,
        "capabilities": {
            "external_network": False,
            "cdn_scan": False,
            "external_alerts": False,
            "repair": False,
        },
    }


def _content_script_asset_remote_drift_scan_snapshot(
    report: ContentScriptAssetRemoteDriftReport,
    *,
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
    item_count: int,
) -> dict[str, Any]:
    filters = _content_script_asset_remote_drift_scan_request_filters(request_body)
    filters.pop("limit", None)
    filters.pop("offset", None)
    filters.pop("confirm_external_network", None)
    return {
        "filters": filters,
        "generated_at": report.generated_at.isoformat(),
        "total_pages_scanned": report.total_pages_scanned,
        "total_external_references": report.total_external_references,
        "total_scanned_references": report.total_scanned_references,
        "total_remote_fetches": report.total_remote_fetches,
        "total_skipped_references": report.total_skipped_references,
        "total_issues": report.total_issues,
        "issue_counts_by_code": report.issue_counts_by_code,
        "issue_counts_by_severity": report.issue_counts_by_severity,
        "limit": request_body.limit,
        "offset": request_body.offset,
        "item_count": item_count,
        "capabilities": {
            "external_network": True,
            "cdn_scan": True,
            "external_alerts": False,
            "repair": False,
            "mutation": False,
        },
    }


def _apply_content_script_asset_filters(statement: Any, filters: dict[str, Any]) -> Any:
    if filters["slug"] is not None:
        statement = statement.where(ContentScriptAsset.slug == filters["slug"])
    if filters["source_host"] is not None:
        statement = statement.where(ContentScriptAsset.source_host == filters["source_host"])
    if filters["sandbox_id"] is not None:
        statement = statement.where(ContentScriptAsset.sandbox_id == filters["sandbox_id"])
    if filters["page_id"] is not None:
        statement = statement.where(ContentScriptAsset.page_id == filters["page_id"])
    if filters["page_version_id"] is not None:
        statement = statement.where(ContentScriptAsset.page_version_id == filters["page_version_id"])
    if filters["published_by_user_id"] is not None:
        statement = statement.where(ContentScriptAsset.published_by_user_id == filters["published_by_user_id"])
    if filters["policy_version"] is not None:
        statement = statement.where(ContentScriptAsset.policy_version == filters["policy_version"])
    if filters["policy_context_hash"] is not None:
        statement = statement.where(ContentScriptAsset.policy_context_hash == filters["policy_context_hash"])
    if filters["asset_sha256"] is not None:
        statement = statement.where(ContentScriptAsset.asset_sha256 == filters["asset_sha256"])
    if filters["reference_value_sha256"] is not None:
        statement = statement.where(ContentScriptAsset.reference_value_sha256 == filters["reference_value_sha256"])
    if filters["from"] is not None:
        statement = statement.where(ContentScriptAsset.published_at >= filters["from"])
    if filters["to"] is not None:
        statement = statement.where(ContentScriptAsset.published_at <= filters["to"])
    if filters["q"] is not None:
        pattern = _contains_pattern(filters["q"])
        statement = statement.where(
            or_(
                ContentScriptAsset.slug.ilike(pattern, escape="~"),
                ContentScriptAsset.source_host.ilike(pattern, escape="~"),
                ContentScriptAsset.sandbox_id.ilike(pattern, escape="~"),
                ContentScriptAsset.reference_key.ilike(pattern, escape="~"),
                ContentScriptAsset.reference_value_sha256.ilike(pattern, escape="~"),
                ContentScriptAsset.asset_sha256.ilike(pattern, escape="~"),
                ContentScriptAsset.policy_version.ilike(pattern, escape="~"),
                ContentScriptAsset.policy_context_hash.ilike(pattern, escape="~"),
            )
        )
    return statement


def _content_script_asset_inventory_snapshot(
    assets: list[ContentScriptAsset],
    *,
    filters: dict[str, Any],
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    host_counts: dict[str, int] = {}
    policy_version_counts: dict[str, int] = {}
    for asset in assets:
        host_counts[asset.source_host] = host_counts.get(asset.source_host, 0) + 1
        policy_version_counts[asset.policy_version] = policy_version_counts.get(asset.policy_version, 0) + 1
    audit_filters = {
        key: (value.isoformat() if isinstance(value, datetime) else value)
        for key, value in filters.items()
        if value is not None and key != "q"
    }
    audit_filters["has_q"] = filters["q"] is not None
    return {
        "filters": audit_filters,
        "total": total,
        "item_count": len(assets),
        "limit": limit,
        "offset": offset,
        "host_counts": host_counts,
        "policy_version_counts": policy_version_counts,
    }


def _previous_content_page_version(db: Session, version: ContentPageVersion) -> ContentPageVersion | None:
    return db.scalar(
        select(ContentPageVersion)
        .where(
            ContentPageVersion.slug == version.slug,
            ContentPageVersion.id < version.id,
        )
        .order_by(ContentPageVersion.id.desc())
    )


def _linked_previous_content_page_version(db: Session, version: ContentPageVersion) -> ContentPageVersion | None:
    if version.previous_version_id is not None:
        linked_version = db.get(ContentPageVersion, version.previous_version_id)
        if linked_version is not None:
            return linked_version
    return _previous_content_page_version(db, version)


def _content_schema_diff(before: Any, after: Any, path: str = "$") -> list[AdminContentPageVersionDiffItem]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[AdminContentPageVersionDiffItem] = []
        for key in sorted(set(before) | set(after)):
            before_value = before.get(key, _DIFF_MISSING)
            after_value = after.get(key, _DIFF_MISSING)
            changes.extend(_content_schema_diff(before_value, after_value, f"{path}.{key}"))
        return changes

    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            before_value = before[index] if index < len(before) else _DIFF_MISSING
            after_value = after[index] if index < len(after) else _DIFF_MISSING
            changes.extend(_content_schema_diff(before_value, after_value, f"{path}[{index}]"))
        return changes

    if before != after:
        return [
            AdminContentPageVersionDiffItem(
                path=path,
                before=_diff_value(before, path),
                after=_diff_value(after, path),
            )
        ]
    return []


def _content_schema_semantic_diff(before: Any, after: Any) -> AdminContentPageVersionSemanticDiff:
    before_schema = before if isinstance(before, dict) else {}
    after_schema = after if isinstance(after, dict) else {}
    metadata_changes = _semantic_field_changes(before_schema, after_schema, _CONTENT_METADATA_FIELDS)
    course_unit_changes = _semantic_course_unit_changes(
        before_schema.get("courseUnit"),
        after_schema.get("courseUnit"),
    )
    section_changes = _semantic_section_changes(
        before_schema.get("sections"),
        after_schema.get("sections"),
    )
    source_changes = _semantic_source_changes(
        before_schema.get("sources"),
        after_schema.get("sources"),
    )
    summary = {
        "metadata": len(metadata_changes),
        "course_unit": len(course_unit_changes),
        "sections_added": _semantic_action_count(section_changes, "added"),
        "sections_removed": _semantic_action_count(section_changes, "removed"),
        "sections_modified": _semantic_action_count(section_changes, "modified"),
        "sections_moved": sum(1 for change in section_changes if change.moved),
        "sources_added": _semantic_action_count(source_changes, "added"),
        "sources_removed": _semantic_action_count(source_changes, "removed"),
        "sources_modified": _semantic_action_count(source_changes, "modified"),
        "sources_moved": sum(1 for change in source_changes if change.moved),
    }
    summary["semantic_changes"] = (
        len(metadata_changes)
        + len(course_unit_changes)
        + len(section_changes)
        + len(source_changes)
    )
    return AdminContentPageVersionSemanticDiff(
        metadata_changes=metadata_changes,
        course_unit_changes=course_unit_changes,
        section_changes=section_changes,
        source_changes=source_changes,
        summary=summary,
    )


def _semantic_section_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticSectionChange]:
    before_entries = _semantic_indexed_entries(before, _section_identity)
    after_entries = _semantic_indexed_entries(after, _section_identity)
    changes: list[AdminContentPageVersionSemanticSectionChange] = []
    for key in sorted(set(before_entries) | set(after_entries)):
        before_entry = before_entries.get(key)
        after_entry = after_entries.get(key)
        before_item = before_entry["item"] if before_entry is not None else None
        after_item = after_entry["item"] if after_entry is not None else None
        if before_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="added",
                    key=key,
                    index_after=after_entry["index"] if after_entry is not None else None,
                    section_id_after=_semantic_stable_id(after_item, "sectionId"),
                    type_after=_semantic_text(after_item, "type"),
                    title_after=_semantic_text(after_item, "title"),
                )
            )
            continue
        if after_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="removed",
                    key=key,
                    index_before=before_entry["index"],
                    section_id_before=_semantic_stable_id(before_item, "sectionId"),
                    type_before=_semantic_text(before_item, "type"),
                    title_before=_semantic_text(before_item, "title"),
                )
            )
            continue

        field_changes = _semantic_field_changes(before_item, after_item, _CONTENT_SECTION_FIELDS)
        prop_changes = _semantic_map_changes(
            _semantic_mapping(before_item.get("props") if isinstance(before_item, dict) else None),
            _semantic_mapping(after_item.get("props") if isinstance(after_item, dict) else None),
            prefix="props.",
        )
        moved = before_entry["index"] != after_entry["index"]
        if field_changes or prop_changes or moved:
            changes.append(
                AdminContentPageVersionSemanticSectionChange(
                    action="modified" if field_changes or prop_changes else "moved",
                    key=key,
                    index_before=before_entry["index"],
                    index_after=after_entry["index"],
                    section_id_before=_semantic_stable_id(before_item, "sectionId"),
                    section_id_after=_semantic_stable_id(after_item, "sectionId"),
                    type_before=_semantic_text(before_item, "type"),
                    type_after=_semantic_text(after_item, "type"),
                    title_before=_semantic_text(before_item, "title"),
                    title_after=_semantic_text(after_item, "title"),
                    moved=moved,
                    field_changes=field_changes,
                    prop_changes=prop_changes,
                )
            )
    return changes


def _semantic_source_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticSourceChange]:
    before_entries = _semantic_indexed_entries(before, _source_identity)
    after_entries = _semantic_indexed_entries(after, _source_identity)
    changes: list[AdminContentPageVersionSemanticSourceChange] = []
    for key in sorted(set(before_entries) | set(after_entries)):
        before_entry = before_entries.get(key)
        after_entry = after_entries.get(key)
        before_item = before_entry["item"] if before_entry is not None else None
        after_item = after_entry["item"] if after_entry is not None else None
        if before_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="added",
                    key=key,
                    index_after=after_entry["index"] if after_entry is not None else None,
                    source_id_after=_semantic_stable_id(after_item, "sourceId"),
                    label_after=_semantic_text(after_item, "label"),
                    url_after=_semantic_text(after_item, "url"),
                )
            )
            continue
        if after_entry is None:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="removed",
                    key=key,
                    index_before=before_entry["index"],
                    source_id_before=_semantic_stable_id(before_item, "sourceId"),
                    label_before=_semantic_text(before_item, "label"),
                    url_before=_semantic_text(before_item, "url"),
                )
            )
            continue

        field_changes = _semantic_field_changes(before_item, after_item, _CONTENT_SOURCE_FIELDS)
        moved = before_entry["index"] != after_entry["index"]
        if field_changes or moved:
            changes.append(
                AdminContentPageVersionSemanticSourceChange(
                    action="modified" if field_changes else "moved",
                    key=key,
                    index_before=before_entry["index"],
                    index_after=after_entry["index"],
                    source_id_before=_semantic_stable_id(before_item, "sourceId"),
                    source_id_after=_semantic_stable_id(after_item, "sourceId"),
                    label_before=_semantic_text(before_item, "label"),
                    label_after=_semantic_text(after_item, "label"),
                    url_before=_semantic_text(before_item, "url"),
                    url_after=_semantic_text(after_item, "url"),
                    moved=moved,
                    field_changes=field_changes,
                )
            )
    return changes


def _semantic_course_unit_changes(before: Any, after: Any) -> list[AdminContentPageVersionSemanticFieldChange]:
    before_map = _semantic_mapping(before)
    after_map = _semantic_mapping(after)
    return _semantic_field_changes(before_map, after_map, _CONTENT_COURSE_UNIT_FIELDS)


def _semantic_field_changes(
    before: Any,
    after: Any,
    fields: tuple[str, ...],
) -> list[AdminContentPageVersionSemanticFieldChange]:
    before_map = _semantic_mapping(before)
    after_map = _semantic_mapping(after)
    changes: list[AdminContentPageVersionSemanticFieldChange] = []
    for field in fields:
        before_value = before_map.get(field)
        after_value = after_map.get(field)
        if before_value != after_value:
            changes.append(
                AdminContentPageVersionSemanticFieldChange(
                    field=field,
                    before=_diff_value(before_value, field),
                    after=_diff_value(after_value, field),
                )
            )
    return changes


def _semantic_map_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    prefix: str = "",
) -> list[AdminContentPageVersionSemanticFieldChange]:
    changes: list[AdminContentPageVersionSemanticFieldChange] = []
    for field in sorted(set(before) | set(after)):
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            changes.append(
                AdminContentPageVersionSemanticFieldChange(
                    field=f"{prefix}{field}",
                    before=_diff_value(before_value, f"{prefix}{field}"),
                    after=_diff_value(after_value, f"{prefix}{field}"),
                )
            )
    return changes


def _semantic_indexed_entries(values: Any, identity_fn) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        return {}
    occurrences: dict[str, int] = {}
    entries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(values):
        identity = identity_fn(item, index)
        occurrences[identity] = occurrences.get(identity, 0) + 1
        key = identity if occurrences[identity] == 1 else f"{identity}#{occurrences[identity]}"
        entries[key] = {"item": item, "index": index}
    return entries


def _section_identity(item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"section:index:{index}"
    props = _semantic_mapping(item.get("props"))
    explicit_id = item.get("sectionId") or item.get("id") or props.get("sectionId") or props.get("id")
    if explicit_id:
        return f"section:id:{_identity_token(explicit_id)}"
    if item.get("experimentId"):
        return f"section:experiment:{_identity_token(item['experimentId'])}"
    if item.get("questionSetId"):
        return f"section:question-set:{_identity_token(item['questionSetId'])}"
    section_type = item.get("type")
    title = item.get("title")
    if section_type and title:
        return f"section:{_identity_token(section_type)}:{_identity_token(title)}"
    if section_type:
        return f"section:type:{_identity_token(section_type)}"
    return f"section:index:{index}"


def _source_identity(item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"source:index:{index}"
    if item.get("sourceId"):
        return f"source:id:{_identity_token(item['sourceId'])}"
    if item.get("label"):
        return f"source:label:{_identity_token(item['label'])}"
    if item.get("url"):
        return f"source:url:{_identity_token(item['url'])}"
    return f"source:index:{index}"


def _identity_token(value: Any) -> str:
    return str(value).strip().lower()


def _semantic_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _semantic_text(value: Any, field: str) -> str | None:
    if not isinstance(value, dict):
        return None
    field_value = value.get(field)
    return str(field_value) if field_value is not None else None


def _semantic_stable_id(value: Any, field: str) -> str | None:
    return _semantic_text(value, field)


def _semantic_action_count(changes: list[Any], action: str) -> int:
    return sum(1 for change in changes if change.action == action)


def _diff_value(value: Any, path: str = "$") -> Any:
    if value is _DIFF_MISSING:
        return None
    return _sanitize_diff_value(value, path)


def _sanitize_diff_value(value: Any, path: str) -> Any:
    if value is None:
        return None
    if _is_sensitive_diff_path(path):
        return _redacted_diff_value(value)
    if isinstance(value, dict):
        return {key: _sanitize_diff_value(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_diff_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _is_sensitive_diff_path(path: str) -> bool:
    return any(_is_sensitive_diff_segment(segment) for segment in _diff_path_segments(path))


def _diff_path_segments(path: str) -> list[str]:
    return [
        segment
        for segment in path.replace("[", ".").replace("]", "").replace("$", "").split(".")
        if segment and not segment.isdigit()
    ]


def _is_sensitive_diff_segment(segment: str) -> bool:
    normalized = segment.replace("_", "").replace("-", "").lower()
    words = _diff_segment_words(segment)
    if normalized in {"authorization", "cookie", "credential", "credentials", "crossorigin", "integrity", "password"}:
        return True
    if normalized == "sandbox" or normalized.endswith("sandbox"):
        return True
    if normalized.startswith("script") or "script" in words:
        return True
    return any(
        token.replace("_", "") in normalized
        for token in _CONTENT_DIFF_SENSITIVE_FIELD_TOKENS
        if token not in {"script", "sandbox", "integrity", "crossorigin"}
    )


def _diff_segment_words(segment: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", segment.replace("_", " ").replace("-", " "))
    return {word.lower() for word in spaced.split() if word}


def _redacted_diff_value(value: Any) -> dict[str, Any]:
    preview: dict[str, Any] = {
        "redacted": True,
        "reason": "content_diff_sensitive_field",
        "value_type": type(value).__name__,
    }
    if isinstance(value, (str, bytes, list, dict, tuple, set)):
        preview["length"] = len(value)
    return preview


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
        .outerjoin(
            AssignmentClassPolicy,
            and_(
                AssignmentClassPolicy.assignment_id == Assignment.id,
                AssignmentClassPolicy.class_id == CourseClass.class_id,
            ),
        )
        .where(
            CourseClass.class_id == class_id,
            CourseClass.status == "active",
            assignment_class_is_assigned_expression(),
        )
    )
    if active_only:
        statement = statement.where(
            assignment_class_effective_status_expression() == "active",
            Course.status == "published",
            CourseUnit.status == "published",
        )
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


def _audit_log_statement(
    *,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
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
    return statement


def _audit_log_export_item(log: AuditLog, *, include_snapshot: bool) -> AuditLogExportItem:
    data = AuditLogRead.model_validate(log).model_dump()
    if not include_snapshot:
        data["snapshot_json"] = None
    return AuditLogExportItem(**data)


def _audit_log_csv(items: list[AuditLogExportItem]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_AUDIT_LOG_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        data = item.model_dump(mode="json")
        writer.writerow({field: _audit_log_csv_value(data.get(field)) for field in _AUDIT_LOG_CSV_FIELDS})
    return buffer.getvalue()


def _audit_log_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{text}"
    return text


def _audit_log_csv_headers(
    *,
    total: int,
    limit: int,
    truncated: bool,
    include_snapshot: bool,
    exported_at: datetime,
) -> dict[str, str]:
    exported_at_text = exported_at.isoformat()
    filename_stamp = exported_at.strftime("%Y%m%dT%H%M%SZ")
    return {
        "Content-Disposition": f'attachment; filename="audit-logs-{filename_stamp}.csv"',
        "X-Audit-Export-Total": str(total),
        "X-Audit-Export-Limit": str(limit),
        "X-Audit-Export-Truncated": str(truncated).lower(),
        "X-Audit-Export-Include-Snapshot": str(include_snapshot).lower(),
        "X-Audit-Exported-At": exported_at_text,
    }


def _audit_log_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogReport:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    return AuditLogReport(
        total=total,
        bucket_limit=bucket_limit,
        generated_at=generated_at,
        filters=filters,
        by_action=_audit_log_action_report(db, source, bucket_limit),
        by_resource_type=_audit_log_report_buckets(db, source, "resource_type", bucket_limit),
        by_actor_role=_audit_log_report_buckets(db, source, "actor_role", bucket_limit),
        by_event_result=_audit_log_report_buckets(db, source, "event_result", bucket_limit),
        by_failure_reason=_audit_log_report_buckets(db, source, "failure_reason", bucket_limit),
    )


def _audit_log_action_report(db: Session, source: Any, bucket_limit: int) -> list[AuditLogActionReport]:
    rows = db.execute(
        select(
            source.c.action,
            source.c.event_result,
            func.count().label("total"),
            func.max(source.c.created_at).label("latest_at"),
        ).group_by(source.c.action, source.c.event_result)
    ).all()
    buckets: dict[str, dict[str, Any]] = {}
    for action, event_result, total, latest_at in rows:
        action_key = str(action)
        bucket = buckets.setdefault(
            action_key,
            {"total": 0, "success": 0, "failure": 0, "other": 0, "latest_at": None},
        )
        count = int(total)
        bucket["total"] += count
        if event_result == "success":
            bucket["success"] += count
        elif event_result == "failure":
            bucket["failure"] += count
        else:
            bucket["other"] += count
        if latest_at is not None and (bucket["latest_at"] is None or latest_at > bucket["latest_at"]):
            bucket["latest_at"] = latest_at

    ordered = sorted(buckets.items(), key=lambda item: (-int(item[1]["total"]), item[0]))[:bucket_limit]
    return [
        AuditLogActionReport(
            action=action,
            total=int(values["total"]),
            success=int(values["success"]),
            failure=int(values["failure"]),
            other=int(values["other"]),
            latest_at=values["latest_at"],
        )
        for action, values in ordered
    ]


def _audit_log_report_buckets(db: Session, source: Any, column_name: str, bucket_limit: int) -> list[AuditLogReportBucket]:
    column = getattr(source.c, column_name)
    count_expr = func.count().label("total")
    rows = db.execute(
        select(column, count_expr).group_by(column).order_by(count_expr.desc(), column).limit(bucket_limit)
    ).all()
    return [AuditLogReportBucket(key=str(key) if key is not None else None, total=int(total)) for key, total in rows]


def _audit_log_report_csv(report: AuditLogReport) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_AUDIT_LOG_REPORT_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in report.by_action:
        writer.writerow(
            {
                "section": "action",
                "key": _audit_log_csv_value(item.action),
                "total": item.total,
                "success": item.success,
                "failure": item.failure,
                "other": item.other,
                "latest_at": item.latest_at.isoformat() if item.latest_at is not None else "",
            }
        )
    for section, buckets in {
        "resource_type": report.by_resource_type,
        "actor_role": report.by_actor_role,
        "event_result": report.by_event_result,
        "failure_reason": report.by_failure_reason,
    }.items():
        for bucket in buckets:
            writer.writerow(
                {
                    "section": section,
                    "key": _audit_log_csv_value(bucket.key),
                    "total": bucket.total,
                    "success": "",
                    "failure": "",
                    "other": "",
                    "latest_at": "",
                }
            )
    return buffer.getvalue()


def _audit_log_report_csv_headers(report: AuditLogReport) -> dict[str, str]:
    filename_stamp = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    return {
        "Content-Disposition": f'attachment; filename="audit-log-report-{filename_stamp}.csv"',
        "X-Audit-Report-Total": str(report.total),
        "X-Audit-Report-Bucket-Limit": str(report.bucket_limit),
        "X-Audit-Report-Generated-At": report.generated_at.isoformat(),
    }


def _audit_log_report_snapshot(report: AuditLogReport, *, report_format: Literal["json", "csv"]) -> dict[str, Any]:
    return {
        "format": report_format,
        "filters": report.filters,
        "total": report.total,
        "bucket_limit": report.bucket_limit,
        "action_bucket_count": len(report.by_action),
        "resource_type_bucket_count": len(report.by_resource_type),
        "actor_role_bucket_count": len(report.by_actor_role),
        "event_result_bucket_count": len(report.by_event_result),
        "failure_reason_bucket_count": len(report.by_failure_reason),
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_retention_plan(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    policy: AuditLogRetentionPolicy,
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogRetentionPlan:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    archive_candidates = int(
        db.scalar(select(func.count()).select_from(source).where(source.c.created_at <= policy.cutoff_at)) or 0
    )
    expiring_soon = int(
        db.scalar(
            select(func.count())
            .select_from(source)
            .where(source.c.created_at > policy.cutoff_at, source.c.created_at <= policy.expiring_soon_cutoff_at)
        )
        or 0
    )
    oldest_at, newest_at = db.execute(
        select(func.min(source.c.created_at), func.max(source.c.created_at)).select_from(source)
    ).one()
    first_candidate = db.execute(
        select(source.c.id, source.c.prev_hash, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= policy.cutoff_at)
        .order_by(source.c.created_at.asc(), source.c.id.asc())
        .limit(1)
    ).first()
    last_candidate = db.execute(
        select(source.c.id, source.c.current_hash)
        .select_from(source)
        .where(source.c.created_at <= policy.cutoff_at)
        .order_by(source.c.created_at.desc(), source.c.id.desc())
        .limit(1)
    ).first()
    return AuditLogRetentionPlan(
        generated_at=generated_at,
        filters=filters,
        capabilities={
            "archive_export": False,
            "delete": False,
            "worm": False,
            "external_anchor": False,
        },
        policy=policy,
        summary=AuditLogRetentionSummary(
            total=total,
            retained=max(total - archive_candidates, 0),
            archive_candidates=archive_candidates,
            expiring_soon=expiring_soon,
            oldest_at=oldest_at,
            newest_at=newest_at,
            first_candidate_id=int(first_candidate.id) if first_candidate is not None else None,
            last_candidate_id=int(last_candidate.id) if last_candidate is not None else None,
            chain_start_prev_hash=first_candidate.prev_hash if first_candidate is not None else None,
            chain_start_current_hash=first_candidate.current_hash if first_candidate is not None else None,
            chain_end_current_hash=last_candidate.current_hash if last_candidate is not None else None,
        ),
        bucket_limit=bucket_limit,
        by_action=_audit_log_retention_buckets(db, source, policy.cutoff_at, "action", bucket_limit),
        by_resource_type=_audit_log_retention_buckets(db, source, policy.cutoff_at, "resource_type", bucket_limit),
        by_event_result=_audit_log_retention_buckets(db, source, policy.cutoff_at, "event_result", bucket_limit),
    )


def _audit_log_retention_buckets(
    db: Session,
    source: Any,
    cutoff_at: datetime,
    column_name: str,
    bucket_limit: int,
) -> list[AuditLogReportBucket]:
    column = getattr(source.c, column_name)
    count_expr = func.count().label("total")
    rows = db.execute(
        select(column, count_expr)
        .select_from(source)
        .where(source.c.created_at <= cutoff_at)
        .group_by(column)
        .order_by(count_expr.desc(), column)
        .limit(bucket_limit)
    ).all()
    return [AuditLogReportBucket(key=str(key) if key is not None else None, total=int(total)) for key, total in rows]


def _audit_log_retention_snapshot(plan: AuditLogRetentionPlan) -> dict[str, Any]:
    return {
        "format": "retention_plan",
        "filters": plan.filters,
        "capabilities": plan.capabilities,
        "policy": plan.policy.model_dump(mode="json"),
        "total": plan.summary.total,
        "archive_candidates": plan.summary.archive_candidates,
        "expiring_soon": plan.summary.expiring_soon,
        "bucket_limit": plan.bucket_limit,
        "action_bucket_count": len(plan.by_action),
        "resource_type_bucket_count": len(plan.by_resource_type),
        "event_result_bucket_count": len(plan.by_event_result),
        "first_candidate_id": plan.summary.first_candidate_id,
        "last_candidate_id": plan.summary.last_candidate_id,
        "chain_start_prev_hash": plan.summary.chain_start_prev_hash,
        "chain_start_current_hash": plan.summary.chain_start_current_hash,
        "chain_end_current_hash": plan.summary.chain_end_current_hash,
        "generated_at": plan.generated_at.isoformat(),
    }


def _audit_log_chain_verification(
    *,
    logs: list[AuditLog],
    total: int,
    filters: dict[str, Any],
    limit: int,
    issue_limit: int,
    generated_at: datetime,
) -> AuditLogChainVerification:
    chain_report = verify_audit_log_chain(logs, issue_limit=issue_limit)
    first = logs[0] if logs else None
    last = logs[-1] if logs else None
    truncated = total > chain_report["scanned_count"]
    status = chain_report["status"]
    if truncated and status == "valid":
        status = "partial"
    return AuditLogChainVerification(
        generated_at=generated_at,
        filters=filters,
        capabilities={
            "repair": False,
            "delete": False,
            "worm": False,
            "external_anchor": False,
        },
        algorithm=chain_report["algorithm"],
        chain_version=chain_report["chain_version"],
        status=status,
        valid=status == "valid",
        total=total,
        scanned_count=chain_report["scanned_count"],
        limit=limit,
        truncated=truncated,
        issue_limit=issue_limit,
        issue_count=chain_report["issue_count"],
        issues_truncated=chain_report["issues_truncated"],
        null_current_hash_count=chain_report["null_current_hash_count"],
        current_hash_mismatch_count=chain_report["current_hash_mismatch_count"],
        prev_hash_mismatch_count=chain_report["prev_hash_mismatch_count"],
        first_id=first.id if first is not None else None,
        last_id=last.id if last is not None else None,
        chain_start_prev_hash=first.prev_hash if first is not None else None,
        chain_start_current_hash=first.current_hash if first is not None else None,
        chain_end_current_hash=last.current_hash if last is not None else None,
        issues=chain_report["issues"],
    )


def _audit_log_chain_verification_snapshot(report: AuditLogChainVerification) -> dict[str, Any]:
    return {
        "format": "chain_integrity",
        "filters": report.filters,
        "capabilities": report.capabilities,
        "status": report.status,
        "valid": report.valid,
        "total": report.total,
        "scanned_count": report.scanned_count,
        "limit": report.limit,
        "truncated": report.truncated,
        "issue_count": report.issue_count,
        "issues_truncated": report.issues_truncated,
        "null_current_hash_count": report.null_current_hash_count,
        "current_hash_mismatch_count": report.current_hash_mismatch_count,
        "prev_hash_mismatch_count": report.prev_hash_mismatch_count,
        "first_id": report.first_id,
        "last_id": report.last_id,
        "chain_start_prev_hash": report.chain_start_prev_hash,
        "chain_start_current_hash": report.chain_start_current_hash,
        "chain_end_current_hash": report.chain_end_current_hash,
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_frequency_report(
    db: Session,
    *,
    statement: Any,
    filters: dict[str, Any],
    effective_from: datetime,
    effective_to: datetime,
    window_hours: int,
    min_count: int,
    min_failure_count: int,
    min_failure_ratio: float,
    bucket_limit: int,
    generated_at: datetime,
) -> AuditLogFrequencyReport:
    source = statement.order_by(None).subquery()
    total = int(db.scalar(select(func.count()).select_from(source)) or 0)
    minimum_activity = max(1, min(min_count, min_failure_count or min_count))
    candidates: list[AuditLogFrequencyCandidate] = []
    for dimension, columns in _audit_log_frequency_dimensions(source):
        candidates.extend(
            _audit_log_frequency_candidates(
                db,
                source=source,
                dimension=dimension,
                columns=columns,
                minimum_activity=minimum_activity,
                min_count=min_count,
                min_failure_count=min_failure_count,
                min_failure_ratio=min_failure_ratio,
            )
        )
    candidates.sort(
        key=lambda candidate: (
            -candidate.total,
            -candidate.failure,
            candidate.dimension,
            candidate.key or "",
            candidate.action or "",
        )
    )
    candidates = candidates[:bucket_limit]
    return AuditLogFrequencyReport(
        total=total,
        generated_at=generated_at,
        filters=filters,
        window={
            "from": effective_from.isoformat(),
            "to": effective_to.isoformat(),
            "window_hours": window_hours,
        },
        thresholds={
            "min_count": min_count,
            "min_failure_count": min_failure_count,
            "min_failure_ratio": min_failure_ratio,
            "bucket_limit": bucket_limit,
        },
        candidates=candidates,
    )


def _audit_log_frequency_dimensions(source: Any) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("action", {"key": source.c.action, "action": source.c.action}),
        (
            "actor_action",
            {
                "key": source.c.actor_user_id,
                "actor_user_id": source.c.actor_user_id,
                "actor_role": source.c.actor_role,
                "action": source.c.action,
            },
        ),
        (
            "ip_action",
            {
                "key": source.c.client_ip_hash,
                "action": source.c.action,
            },
        ),
        (
            "resource_action",
            {
                "key": source.c.resource,
                "resource_type": source.c.resource_type,
                "resource_id": source.c.resource_id,
                "school_id": source.c.school_id,
                "class_id": source.c.class_id,
                "action": source.c.action,
            },
        ),
        (
            "failure_reason",
            {
                "key": source.c.failure_reason,
                "failure_reason": source.c.failure_reason,
            },
        ),
    ]


def _audit_log_frequency_candidates(
    db: Session,
    *,
    source: Any,
    dimension: str,
    columns: dict[str, Any],
    minimum_activity: int,
    min_count: int,
    min_failure_count: int,
    min_failure_ratio: float,
) -> list[AuditLogFrequencyCandidate]:
    count_expr = func.count().label("total")
    success_expr = func.coalesce(func.sum(case((source.c.event_result == "success", 1), else_=0)), 0).label("success")
    failure_expr = func.coalesce(func.sum(case((source.c.event_result == "failure", 1), else_=0)), 0).label("failure")
    group_columns = list(dict.fromkeys(columns.values()))
    rows = db.execute(
        select(
            *[column.label(name) for name, column in columns.items()],
            count_expr,
            success_expr,
            failure_expr,
            func.count(func.distinct(source.c.actor_user_id)).label("distinct_actors"),
            func.count(func.distinct(source.c.client_ip_hash)).label("distinct_ip_hashes"),
            func.count(func.distinct(source.c.request_id)).label("distinct_request_ids"),
            func.min(source.c.created_at).label("first_at"),
            func.max(source.c.created_at).label("latest_at"),
        )
        .group_by(*group_columns)
        .having(count_expr >= minimum_activity)
    ).mappings()
    candidates: list[AuditLogFrequencyCandidate] = []
    for row in rows:
        total = int(row["total"])
        success = int(row["success"] or 0)
        failure = int(row["failure"] or 0)
        failure_ratio = _divide(failure, total)
        reasons: list[str] = []
        if total >= min_count:
            reasons.append("count_threshold")
        if min_failure_count > 0 and failure >= min_failure_count:
            reasons.append("failure_count_threshold")
        if min_failure_count > 0 and failure >= min_failure_count and failure_ratio >= min_failure_ratio:
            reasons.append("failure_ratio_threshold")
        if not reasons:
            continue
        candidates.append(
            AuditLogFrequencyCandidate(
                dimension=dimension,
                key=str(row["key"]) if row["key"] is not None else None,
                action=str(row["action"]) if row.get("action") is not None else None,
                actor_user_id=row.get("actor_user_id"),
                actor_role=row.get("actor_role"),
                resource_type=row.get("resource_type"),
                resource_id=row.get("resource_id"),
                school_id=row.get("school_id"),
                class_id=row.get("class_id"),
                failure_reason=row.get("failure_reason"),
                total=total,
                success=success,
                failure=failure,
                other=max(total - success - failure, 0),
                failure_ratio=failure_ratio,
                distinct_actors=int(row["distinct_actors"] or 0),
                distinct_ip_hashes=int(row["distinct_ip_hashes"] or 0),
                distinct_request_ids=int(row["distinct_request_ids"] or 0),
                first_at=row["first_at"],
                latest_at=row["latest_at"],
                reasons=reasons,
            )
        )
    return candidates


def _audit_log_frequency_snapshot(report: AuditLogFrequencyReport) -> dict[str, Any]:
    dimension_counts: dict[str, int] = {}
    for candidate in report.candidates:
        dimension_counts[candidate.dimension] = dimension_counts.get(candidate.dimension, 0) + 1
    return {
        "format": "high_frequency",
        "filters": report.filters,
        "window": report.window,
        "thresholds": report.thresholds,
        "total": report.total,
        "candidate_count": len(report.candidates),
        "dimension_counts": dimension_counts,
        "generated_at": report.generated_at.isoformat(),
    }


def _audit_log_filters(
    *,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in {
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "school_id": school_id,
        "class_id": class_id,
        "event_result": event_result,
        "failure_reason": failure_reason,
        "request_id": request_id,
    }.items():
        if value is not None:
            filters[key] = value.strip() if isinstance(value, str) else value
    if from_at is not None:
        filters["from"] = from_at.isoformat()
    if to_at is not None:
        filters["to"] = to_at.isoformat()
    return filters


def _audit_log_export_snapshot(
    *,
    export_format: Literal["json", "csv"],
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    include_snapshot: bool,
    limit: int,
    total: int,
    exported_count: int,
    truncated: bool,
    exported_at: datetime,
) -> dict[str, Any]:
    return {
        "format": export_format,
        "filters": _audit_log_filters(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=from_at,
            to_at=to_at,
        ),
        "include_snapshot": include_snapshot,
        "limit": limit,
        "total": total,
        "exported_count": exported_count,
        "truncated": truncated,
        "exported_at": exported_at.isoformat(),
    }


def _next_offset(total: int, offset: int, item_count: int) -> int | None:
    next_offset = offset + item_count
    return next_offset if next_offset < total else None


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _normalize_issue_provider(value: str | None) -> str | None:
    normalized = _strip_optional(value)
    if normalized is None:
        return None
    return normalized.lower()


def _contains_pattern(value: str) -> str:
    escaped = value.strip().replace("~", "~~").replace("%", "~%").replace("_", "~_")
    return f"%{escaped}%"


def _content_page_schema_text(field: str) -> Any:
    return func.coalesce(ContentPageRecord.schema_json[field].as_string(), "")


def _user_snapshot(user: User) -> dict[str, str]:
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
    }


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


def _change_snapshot(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = {
        key: {"from": before.get(key), "to": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
    return {"before": before, "after": after, "changes": changes}


def _revoke_user_sessions(db: Session, user: User) -> int:
    now = datetime.now(UTC)
    sessions = db.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    ).all()
    for auth_session in sessions:
        auth_session.revoked_at = now
    return len(sessions)


def _clear_user_login_attempt(db: Session, user: User) -> bool:
    attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.normalized_username == user.normalized_username))
    if attempt is None:
        return False
    db.delete(attempt)
    return True
