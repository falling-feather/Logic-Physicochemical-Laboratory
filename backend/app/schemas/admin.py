from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.content import ScriptAnalysisRead
from app.schemas.school import ClassRead, SchoolRead


AdminUserRole = Literal["admin", "teacher", "student"]
AdminUserStatus = Literal["active", "disabled"]
BugSeverity = Literal["P0", "P1", "P2", "P3"]
BugStatus = Literal["open", "triaged", "in_progress", "closed"]


class AdminBootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    bootstrap_token: str | None = Field(default=None, max_length=240)


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUserRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: AdminUserRole | None = None
    status: AdminUserStatus | None = None


class AdminUserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AdminUserPasswordResetResponse(BaseModel):
    status: str = "ok"
    user_id: int
    revoked_sessions: int
    cleared_login_attempt: bool


class AdminContentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    galaxy: str
    subject: str
    layout: str
    status: str
    version: str
    schema_hash: str | None = None
    current_version_id: int | None = None
    published_by_user_id: int | None = None
    published_at: datetime | None = None
    updated_at: datetime


class AdminContentPagePage(BaseModel):
    items: list[AdminContentPageRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentDraftRead(BaseModel):
    id: int
    author_user_id: int
    author_username: str
    author_display_name: str
    target_slug: str
    title: str
    status: str
    allow_script: bool
    schema_hash: str | None = None
    base_version_id: int | None = None
    base_schema_hash: str | None = None
    script_risk_level: str | None = None
    script_analysis: ScriptAnalysisRead | None = None
    script_review_status: str
    script_reviewed_by_user_id: int | None = None
    script_reviewed_at: datetime | None = None
    script_review_note: str | None = None
    submitted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    change_requested_by_user_id: int | None = None
    change_requested_at: datetime | None = None
    change_request_note: str | None = None
    published_page_id: int | None = None
    published_version_id: int | None = None
    published_by_user_id: int | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminContentDraftPage(BaseModel):
    items: list[AdminContentDraftRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentPageVersionRead(BaseModel):
    id: int
    page_id: int
    slug: str
    title: str
    status: str
    version: str
    schema_hash: str
    previous_version_id: int | None = None
    source_draft_id: int | None = None
    restored_from_version_id: int | None = None
    published_by_user_id: int
    published_at: datetime
    note: str | None = None
    created_at: datetime


class AdminContentPageVersionPage(BaseModel):
    items: list[AdminContentPageVersionRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentScriptAssetRead(BaseModel):
    id: int
    page_id: int
    page_version_id: int
    slug: str
    sandbox_id: str
    reference_key: str
    reference_value_sha256: str
    source_host: str
    source_url_sha256: str
    matched_algorithm: str
    asset_sha256: str
    asset_size_bytes: int
    policy_version: str
    policy_context_hash: str
    published_by_user_id: int
    published_at: datetime
    created_at: datetime
    updated_at: datetime


class AdminContentScriptAssetPage(BaseModel):
    items: list[AdminContentScriptAssetRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


ContentScriptHostPolicyStatus = Literal["trusted", "watch", "blocked"]


class AdminContentScriptHostPolicyRead(BaseModel):
    id: int | None = None
    source_host: str
    status: str
    reason: str | None = None
    configured_allowed: bool
    observed_asset_count: int
    observed_page_count: int
    last_observed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminContentScriptHostPolicyPage(BaseModel):
    items: list[AdminContentScriptHostPolicyRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentScriptHostPolicyUpdate(BaseModel):
    status: ContentScriptHostPolicyStatus
    reason: str | None = Field(default=None, max_length=500)


class AdminContentScriptAssetAuditIssueRead(BaseModel):
    code: str
    severity: str
    message: str
    page_id: int | None = None
    page_version_id: int | None = None
    slug: str
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    published_at: datetime | None = None


class AdminContentScriptAssetAuditReport(BaseModel):
    generated_at: datetime
    total_pages_scanned: int
    total_external_references: int
    total_issues: int
    issue_counts_by_code: dict[str, int]
    issue_counts_by_severity: dict[str, int]
    items: list[AdminContentScriptAssetAuditIssueRead]
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentScriptAssetRemoteDriftScanRequest(BaseModel):
    slug: str | None = Field(default=None, max_length=180)
    source_host: str | None = Field(default=None, max_length=255)
    issue_code: str | None = Field(default=None, max_length=80)
    severity: Literal["critical", "warning", "info"] | None = None
    limit: int = Field(default=25, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    confirm_external_network: bool = False


class AdminContentScriptAssetRemoteDriftIssueRead(BaseModel):
    code: str
    severity: str
    message: str
    page_id: int | None = None
    page_version_id: int | None = None
    slug: str
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    remote_asset_sha256: str | None = None
    remote_asset_size_bytes: int | None = None
    published_at: datetime | None = None


class AdminContentScriptAssetRemoteDriftReport(BaseModel):
    scan_run_id: int | None = None
    scan_run_key: str | None = None
    generated_at: datetime
    total_pages_scanned: int
    total_external_references: int
    total_scanned_references: int
    total_remote_fetches: int
    total_skipped_references: int
    total_issues: int
    issue_counts_by_code: dict[str, int]
    issue_counts_by_severity: dict[str, int]
    items: list[AdminContentScriptAssetRemoteDriftIssueRead]
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentScriptAssetScanRunRead(BaseModel):
    id: int
    run_key: str
    scan_type: str
    trigger_source: str
    status: str
    started_at: datetime
    finished_at: datetime
    created_by_user_id: int
    filters_json: dict[str, Any]
    totals_json: dict[str, Any]
    issue_counts_json: dict[str, Any]
    alert_status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminContentScriptAssetScanRunPage(BaseModel):
    items: list[AdminContentScriptAssetScanRunRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminContentScriptAssetScanAlertCandidate(BaseModel):
    severity: str
    code: str
    source: str
    action_hint: str
    run_id: int
    run_key: str
    scan_type: str
    trigger_source: str
    status: str
    alert_status: str
    started_at: datetime
    finished_at: datetime
    slug: str | None = None
    page_id: int | None = None
    page_version_id: int | None = None
    sandbox_id: str | None = None
    reference_key: str | None = None
    reference_value_sha256: str | None = None
    source_host: str | None = None
    source_url_sha256: str | None = None
    asset_id: int | None = None
    asset_sha256: str | None = None
    remote_asset_sha256: str | None = None
    remote_asset_size_bytes: int | None = None
    published_at: datetime | None = None


class AdminContentScriptAssetScanAlertReport(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    alert_status: str
    candidate_count: int
    critical_count: int
    warning_count: int
    info_count: int
    recent_run_count: int
    issue_run_count: int
    candidates: list[AdminContentScriptAssetScanAlertCandidate]


class AdminContentPageVersionDiffItem(BaseModel):
    path: str
    before: Any = None
    after: Any = None


class AdminContentPageVersionSemanticFieldChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class AdminContentPageVersionSemanticSectionChange(BaseModel):
    action: Literal["added", "removed", "modified", "moved"]
    key: str
    index_before: int | None = None
    index_after: int | None = None
    section_id_before: str | None = None
    section_id_after: str | None = None
    type_before: str | None = None
    type_after: str | None = None
    title_before: str | None = None
    title_after: str | None = None
    moved: bool = False
    field_changes: list[AdminContentPageVersionSemanticFieldChange] = Field(default_factory=list)
    prop_changes: list[AdminContentPageVersionSemanticFieldChange] = Field(default_factory=list)


class AdminContentPageVersionSemanticSourceChange(BaseModel):
    action: Literal["added", "removed", "modified", "moved"]
    key: str
    index_before: int | None = None
    index_after: int | None = None
    source_id_before: str | None = None
    source_id_after: str | None = None
    label_before: str | None = None
    label_after: str | None = None
    url_before: str | None = None
    url_after: str | None = None
    moved: bool = False
    field_changes: list[AdminContentPageVersionSemanticFieldChange] = Field(default_factory=list)


class AdminContentPageVersionSemanticDiff(BaseModel):
    metadata_changes: list[AdminContentPageVersionSemanticFieldChange] = Field(default_factory=list)
    course_unit_changes: list[AdminContentPageVersionSemanticFieldChange] = Field(default_factory=list)
    section_changes: list[AdminContentPageVersionSemanticSectionChange] = Field(default_factory=list)
    source_changes: list[AdminContentPageVersionSemanticSourceChange] = Field(default_factory=list)
    summary: dict[str, int]


class AdminContentPageVersionDiff(BaseModel):
    slug: str
    base_version_id: int
    base_version: str
    base_schema_hash: str
    target_version_id: int
    target_version: str
    target_schema_hash: str
    change_count: int
    changes: list[AdminContentPageVersionDiffItem]
    semantic: AdminContentPageVersionSemanticDiff


class AdminSchoolPage(BaseModel):
    items: list[SchoolRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminClassPage(BaseModel):
    items: list[ClassRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminClassJoinRequestRead(BaseModel):
    id: int
    school_id: int
    school_name: str
    class_id: int
    class_name: str
    user_id: int
    user_username: str
    user_display_name: str
    role: str
    status: str
    message: str | None = None
    requested_by_user_id: int
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminClassJoinRequestPage(BaseModel):
    items: list[AdminClassJoinRequestRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminClassJoinRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    users_by_role: dict[str, int]
    total_schools: int
    total_classes: int
    pending_class_join_requests: int
    total_content_pages: int
    total_content_drafts: int
    total_content_page_versions: int
    pending_script_reviews: int
    total_courses: int
    total_assignments: int
    total_learning_events: int
    total_submissions: int
    total_point_ledger_entries: int
    total_bug_records: int
    open_bug_records: int
    total_audit_logs: int


class AdminSchoolStats(BaseModel):
    school_id: int
    school_name: str
    region: str | None = None
    status: str
    total_classes: int
    active_classes: int
    active_students: int
    active_teachers: int
    total_courses: int
    active_courses: int
    total_assignments: int
    active_assignments: int
    total_learning_events: int
    complete_learning_events: int
    total_submissions: int
    graded_submissions: int
    returned_submissions: int
    pending_submissions: int
    total_points: int


class AdminClassStats(BaseModel):
    class_id: int
    class_name: str
    school_id: int
    grade: str | None = None
    term: str | None = None
    status: str
    active_students: int
    active_teachers: int
    active_courses: int
    active_assignments: int
    expected_submissions: int
    total_learning_events: int
    complete_learning_events: int
    total_submissions: int
    graded_submissions: int
    returned_submissions: int
    pending_submissions: int
    pending_submission_ratio: float
    total_points: int
    average_points_per_student: float
    average_score_percent: float


class AdminPendingSubmissionRead(BaseModel):
    id: int
    assignment_id: int
    assignment_title: str
    student_id: int
    student_username: str
    student_display_name: str
    class_id: int | None = None
    class_name: str | None = None
    school_id: int
    course_id: int
    course_title: str
    status: str
    score: int | None = None
    submitted_at: datetime
    graded_at: datetime | None = None
    due_at: datetime | None = None


class AdminPendingSubmissionQueue(BaseModel):
    items: list[AdminPendingSubmissionRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminKnowledgeSnapshotRunRead(BaseModel):
    id: int
    run_key: str
    granularity: str
    period_start: datetime
    period_end: datetime
    trigger_source: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    scheduler_lease_owner: str | None = None
    scheduler_lease_expires_at: datetime | None = None
    scheduler_heartbeat_at: datetime | None = None
    attempt_count: int
    user_snapshot_count: int
    class_snapshot_count: int
    error_message: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AdminKnowledgeSnapshotRunPage(BaseModel):
    items: list[AdminKnowledgeSnapshotRunRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AdminKnowledgeSnapshotRunRequeueRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminKnowledgeSnapshotRunStatusBucket(BaseModel):
    status: str | None = None
    total: int


class AdminKnowledgeSnapshotRunHealthItem(BaseModel):
    id: int
    run_key: str
    granularity: str
    period_start: datetime
    period_end: datetime
    trigger_source: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    scheduler_lease_owner: str | None = None
    scheduler_lease_expires_at: datetime | None = None
    scheduler_heartbeat_at: datetime | None = None
    attempt_count: int
    user_snapshot_count: int
    class_snapshot_count: int
    error_message: str | None = None
    health_flags: list[str]
    retryable: bool
    claimable: bool
    cancellable: bool
    lease_seconds_remaining: int | None = None


class AdminKnowledgeSnapshotRunHealthReport(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    health_status: Literal["ok", "warning", "attention"]
    total: int
    by_status: list[AdminKnowledgeSnapshotRunStatusBucket]
    running_count: int
    active_running_count: int
    stale_running_count: int
    lease_expiring_count: int
    legacy_running_without_lease_count: int
    claimable_count: int
    pending_count: int
    success_count: int
    failed_count: int
    retryable_failed_count: int
    exhausted_failed_count: int
    cancelled_count: int
    needs_attention_count: int
    problem_count: int
    problem_runs: list[AdminKnowledgeSnapshotRunHealthItem]
    latest_success_by_granularity: dict[str, datetime | None]
    oldest_running_started_at: datetime | None = None
    next_lease_expires_at: datetime | None = None
    newest_finished_at: datetime | None = None


class AdminKnowledgeSnapshotRunQueueItem(BaseModel):
    source: Literal[
        "due",
        "pending",
        "retryable_failed",
        "exhausted_failed",
        "cancelled",
        "stale_running",
        "active_running",
        "legacy_running",
    ]
    reason: str
    ready: bool
    claimable: bool
    run_id: int | None = None
    run_key: str
    granularity: str
    reference_date: date
    period_start: datetime
    period_end: datetime
    status: str
    trigger_source: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    scheduler_lease_owner: str | None = None
    scheduler_lease_expires_at: datetime | None = None
    scheduler_heartbeat_at: datetime | None = None
    attempt_count: int | None = None


class AdminKnowledgeSnapshotRunQueueReport(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    queue_status: Literal["empty", "ready", "backlog"]
    backlog_count: int
    ready_count: int
    dispatchable_now_count: int
    claimable_by_lease_rule_count: int
    due_count: int
    pending_count: int
    manual_requeue_count: int
    blocked_count: int
    retryable_failed_count: int
    exhausted_failed_count: int
    cancelled_count: int
    stale_running_count: int
    active_running_count: int
    legacy_running_without_lease_count: int
    by_granularity: dict[str, int]
    ready_jobs: list[AdminKnowledgeSnapshotRunQueueItem]
    manual_requeue_runs: list[AdminKnowledgeSnapshotRunQueueItem]
    blocked_runs: list[AdminKnowledgeSnapshotRunQueueItem]
    next_due_jobs: list[AdminKnowledgeSnapshotRunQueueItem]
    oldest_ready_at: datetime | None = None
    oldest_manual_requeue_at: datetime | None = None
    next_lease_expires_at: datetime | None = None


class AdminKnowledgeSnapshotRunAlertCandidate(BaseModel):
    severity: Literal["critical", "warning", "info"]
    code: str
    source: Literal["health", "queue"]
    action_hint: Literal["requeue", "dispatch", "investigate", "monitor"]
    run_id: int | None = None
    run_key: str
    granularity: str
    status: str
    trigger_source: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    scheduler_lease_owner: str | None = None
    scheduler_lease_expires_at: datetime | None = None
    scheduler_heartbeat_at: datetime | None = None
    attempt_count: int | None = None
    health_flags: list[str] = Field(default_factory=list)
    queue_reason: str | None = None
    retryable: bool = False
    claimable: bool = False
    cancellable: bool = False
    ready: bool = False


class AdminKnowledgeSnapshotRunAlertReport(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    policy: dict[str, Any]
    alert_status: Literal["ok", "warning", "critical"]
    health_status: Literal["ok", "warning", "attention"]
    queue_status: Literal["empty", "ready", "backlog"]
    candidate_count: int
    critical_count: int
    warning_count: int
    info_count: int
    needs_attention_count: int
    lease_expiring_count: int
    dispatchable_now_count: int
    manual_requeue_count: int
    blocked_count: int
    candidates: list[AdminKnowledgeSnapshotRunAlertCandidate]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    actor_role: str | None = None
    action: str
    resource: str
    resource_type: str
    resource_id: str | None = None
    school_id: int | None = None
    class_id: int | None = None
    event_result: str | None = None
    failure_reason: str | None = None
    request_id: str | None = None
    client_ip_hash: str | None = None
    user_agent: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    prev_hash: str | None = None
    current_hash: str | None = None
    snapshot_json: dict
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None


class AuditLogExportItem(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_role: str | None = None
    action: str
    resource: str
    resource_type: str
    resource_id: str | None = None
    school_id: int | None = None
    class_id: int | None = None
    event_result: str | None = None
    failure_reason: str | None = None
    request_id: str | None = None
    client_ip_hash: str | None = None
    user_agent: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    prev_hash: str | None = None
    current_hash: str | None = None
    snapshot_json: dict | None = None
    created_at: datetime


class AuditLogExport(BaseModel):
    items: list[AuditLogExportItem]
    total: int
    limit: int
    truncated: bool
    include_snapshot: bool
    exported_at: datetime


class AuditLogReportBucket(BaseModel):
    key: str | None = None
    total: int


class AuditLogActionReport(BaseModel):
    action: str
    total: int
    success: int
    failure: int
    other: int
    latest_at: datetime | None = None


class AuditLogReport(BaseModel):
    total: int
    bucket_limit: int
    generated_at: datetime
    filters: dict[str, Any]
    by_action: list[AuditLogActionReport]
    by_resource_type: list[AuditLogReportBucket]
    by_actor_role: list[AuditLogReportBucket]
    by_event_result: list[AuditLogReportBucket]
    by_failure_reason: list[AuditLogReportBucket]


class AuditLogFrequencyCandidate(BaseModel):
    dimension: str
    key: str | None = None
    action: str | None = None
    actor_user_id: int | None = None
    actor_role: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    school_id: int | None = None
    class_id: int | None = None
    failure_reason: str | None = None
    total: int
    success: int
    failure: int
    other: int
    failure_ratio: float
    distinct_actors: int
    distinct_ip_hashes: int
    distinct_request_ids: int
    first_at: datetime | None = None
    latest_at: datetime | None = None
    reasons: list[str]


class AuditLogFrequencyReport(BaseModel):
    total: int
    generated_at: datetime
    filters: dict[str, Any]
    window: dict[str, Any]
    thresholds: dict[str, Any]
    candidates: list[AuditLogFrequencyCandidate]


class AuditLogRetentionPolicy(BaseModel):
    retention_days: int | None = None
    warning_days: int
    cutoff_at: datetime
    expiring_soon_cutoff_at: datetime
    source: Literal["config", "query", "before"]


class AuditLogRetentionSummary(BaseModel):
    total: int
    retained: int
    archive_candidates: int
    expiring_soon: int
    oldest_at: datetime | None = None
    newest_at: datetime | None = None
    first_candidate_id: int | None = None
    last_candidate_id: int | None = None
    chain_start_prev_hash: str | None = None
    chain_start_current_hash: str | None = None
    chain_end_current_hash: str | None = None


class AuditLogRetentionPlan(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    capabilities: dict[str, bool]
    policy: AuditLogRetentionPolicy
    summary: AuditLogRetentionSummary
    bucket_limit: int
    by_action: list[AuditLogReportBucket]
    by_resource_type: list[AuditLogReportBucket]
    by_event_result: list[AuditLogReportBucket]


class AuditLogChainIssue(BaseModel):
    type: Literal["null_current_hash", "current_hash_mismatch", "prev_hash_mismatch"]
    log_id: int
    previous_log_id: int | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None


class AuditLogChainVerification(BaseModel):
    generated_at: datetime
    filters: dict[str, Any]
    capabilities: dict[str, bool]
    algorithm: str
    chain_version: int
    status: Literal["valid", "partial", "invalid"]
    valid: bool
    total: int
    scanned_count: int
    limit: int
    truncated: bool
    issue_limit: int
    issue_count: int
    issues_truncated: bool
    null_current_hash_count: int
    current_hash_mismatch_count: int
    prev_hash_mismatch_count: int
    first_id: int | None = None
    last_id: int | None = None
    chain_start_prev_hash: str | None = None
    chain_start_current_hash: str | None = None
    chain_end_current_hash: str | None = None
    issues: list[AuditLogChainIssue]


class BugRecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(default="general", min_length=1, max_length=80)
    severity: BugSeverity = "P2"
    status: BugStatus = "open"
    source: str | None = Field(default=None, max_length=240)
    external_issue_provider: str | None = Field(default=None, max_length=80)
    external_issue_id: str | None = Field(default=None, max_length=120)
    external_issue_url: str | None = Field(default=None, max_length=500)
    evidence: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class BugRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    severity: BugSeverity | None = None
    status: BugStatus | None = None
    source: str | None = Field(default=None, max_length=240)
    external_issue_provider: str | None = Field(default=None, max_length=80)
    external_issue_id: str | None = Field(default=None, max_length=120)
    external_issue_url: str | None = Field(default=None, max_length=500)
    evidence: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class BugRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    severity: str
    status: str
    source: str | None = None
    external_issue_provider: str | None = None
    external_issue_id: str | None = None
    external_issue_url: str | None = None
    evidence: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class BugRecordPage(BaseModel):
    items: list[BugRecordRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
