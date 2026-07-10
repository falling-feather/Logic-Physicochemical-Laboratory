"""add targeted performance indexes

Revision ID: 20260710_0043
Revises: 20260710_0042
Create Date: 2026-07-10
"""

from alembic import op


revision = "20260710_0043"
down_revision = "20260710_0042"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_bug_records_status_id", "bug_records", ("status", "id")),
    ("ix_bug_external_sync_bug_id_id", "bug_external_sync_operations", ("bug_record_id", "id")),
    ("ix_audit_logs_created_id", "audit_logs", ("created_at", "id")),
    (
        "ix_audit_logs_resource_created",
        "audit_logs",
        ("resource_type", "resource_id", "created_at", "id"),
    ),
    (
        "ix_submissions_status_submitted_id",
        "submissions",
        ("status", "submitted_at", "id"),
    ),
    (
        "ix_submissions_class_status_submitted",
        "submissions",
        ("class_id", "status", "submitted_at", "id"),
    ),
    (
        "ix_knowledge_runs_started_id",
        "knowledge_snapshot_runs",
        ("started_at", "id"),
    ),
    (
        "ix_knowledge_runs_status_started",
        "knowledge_snapshot_runs",
        ("status", "started_at", "id"),
    ),
    (
        "ix_script_scan_type_started",
        "content_script_asset_scan_runs",
        ("scan_type", "started_at", "id"),
    ),
    (
        "ix_script_scan_status_started",
        "content_script_asset_scan_runs",
        ("status", "started_at", "id"),
    ),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
