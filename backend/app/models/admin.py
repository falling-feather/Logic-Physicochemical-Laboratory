from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BugRecord(TimestampMixin, Base):
    __tablename__ = "bug_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="general", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="P2", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    external_issue_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    external_issue_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_issue_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

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
