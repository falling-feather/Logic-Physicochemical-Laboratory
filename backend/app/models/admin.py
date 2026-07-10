from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BugRecord(TimestampMixin, Base):
    __tablename__ = "bug_records"
    __table_args__ = (Index("ix_bug_records_status_id", "status", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="general", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="P2", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    external_issue_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    external_issue_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_issue_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_issue_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_issue_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_sync_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BugExternalSyncOperation(TimestampMixin, Base):
    __tablename__ = "bug_external_sync_operations"
    __table_args__ = (
        UniqueConstraint("operation_key", name="uq_bug_external_sync_operations_key"),
        Index("ix_bug_external_sync_bug_id_id", "bug_record_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bug_record_id: Mapped[int] = mapped_column(ForeignKey("bug_records.id"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    desired_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_issue_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_issue_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_comment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_id", "created_at", "id"),
        Index("ix_audit_logs_resource_created", "resource_type", "resource_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True, nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=True)
    event_result: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(240), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(240), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AuditChainHead(TimestampMixin, Base):
    __tablename__ = "audit_chain_heads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_audit_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuditArchiveAnchor(TimestampMixin, Base):
    __tablename__ = "audit_archive_anchors"
    __table_args__ = (UniqueConstraint("manifest_sha256", name="uq_audit_archive_anchors_manifest_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    manifest_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_path_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(32), nullable=False)
    exported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oldest_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    newest_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chain_start_prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chain_end_current_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    anchored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    external_receipt_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_anchored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class AdminAlertOutboxDispatchPlan(TimestampMixin, Base):
    __tablename__ = "admin_alert_outbox_dispatch_plans"
    __table_args__ = (UniqueConstraint("plan_key", name="uq_admin_alert_outbox_dispatch_plans_plan_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_key: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_status: Mapped[str] = mapped_column(String(32), default="created", index=True, nullable=False)
    dry_run_status: Mapped[str] = mapped_column(String(32), default="ready", index=True, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    policy_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ready_entry_ids_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ready_entry_payload_hashes_json: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    blocked_reason_counts_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ready_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expired_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_due_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    terminal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    external_delivery_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class AdminAlertOutboxEntry(TimestampMixin, Base):
    __tablename__ = "admin_alert_outbox_entries"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_admin_alert_outbox_entries_dedupe_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    source_key: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    event_code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    action_hint: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True, nullable=False)
    dispatch_mode: Mapped[str] = mapped_column(String(40), default="manual_review", nullable=False)
    delivery_target: Mapped[str] = mapped_column(String(80), default="admin_outbox", nullable=False)
    external_delivery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    seen_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BackgroundTask(TimestampMixin, Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_background_tasks_idempotency_key"),
        Index("ix_background_tasks_claim", "status", "available_at", "priority", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class BackgroundTaskAttempt(TimestampMixin, Base):
    __tablename__ = "background_task_attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number", name="uq_background_task_attempts_task_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("background_tasks.id"), index=True, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
