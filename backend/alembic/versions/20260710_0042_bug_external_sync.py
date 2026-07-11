"""add external issue synchronization ledger

Revision ID: 20260710_0042
Revises: 20260710_0041
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0042"
down_revision = "20260710_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bug_records", sa.Column("external_issue_state", sa.String(length=32), nullable=True))
    op.add_column("bug_records", sa.Column("external_issue_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "bug_records",
        sa.Column("external_sync_revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "bug_external_sync_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bug_record_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("operation_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("desired_state", sa.String(length=32), nullable=True),
        sa.Column("comment_sha256", sa.String(length=64), nullable=True),
        sa.Column("comment_length", sa.Integer(), nullable=True),
        sa.Column("external_issue_id", sa.String(length=120), nullable=True),
        sa.Column("external_issue_url", sa.String(length=500), nullable=True),
        sa.Column("external_state", sa.String(length=32), nullable=True),
        sa.Column("external_comment_id", sa.String(length=120), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bug_record_id"], ["bug_records.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_key", name="uq_bug_external_sync_operations_key"),
    )
    for column in ("id", "bug_record_id", "provider", "operation", "status", "finished_at", "created_by_user_id"):
        op.create_index(
            op.f(f"ix_bug_external_sync_operations_{column}"),
            "bug_external_sync_operations",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("created_by_user_id", "finished_at", "status", "operation", "provider", "bug_record_id", "id"):
        op.drop_index(op.f(f"ix_bug_external_sync_operations_{column}"), table_name="bug_external_sync_operations")
    op.drop_table("bug_external_sync_operations")
    op.drop_column("bug_records", "external_sync_revision")
    op.drop_column("bug_records", "external_issue_synced_at")
    op.drop_column("bug_records", "external_issue_state")
