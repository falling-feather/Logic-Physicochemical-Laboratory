"""add admin alert outbox entries

Revision ID: 20260708_0034
Revises: 20260708_0033
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0034"
down_revision = "20260708_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_alert_outbox_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("event_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("action_hint", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dispatch_mode", sa.String(length=40), nullable=False),
        sa.Column("delivery_target", sa.String(length=80), nullable=False),
        sa.Column("external_delivery", sa.Boolean(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_admin_alert_outbox_entries_dedupe_key"),
    )
    op.create_index(op.f("ix_admin_alert_outbox_entries_id"), "admin_alert_outbox_entries", ["id"], unique=False)
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_source_type"),
        "admin_alert_outbox_entries",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_source_id"),
        "admin_alert_outbox_entries",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_source_key"),
        "admin_alert_outbox_entries",
        ["source_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_event_code"),
        "admin_alert_outbox_entries",
        ["event_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_severity"),
        "admin_alert_outbox_entries",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_action_hint"),
        "admin_alert_outbox_entries",
        ["action_hint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_status"),
        "admin_alert_outbox_entries",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_last_seen_at"),
        "admin_alert_outbox_entries",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_available_at"),
        "admin_alert_outbox_entries",
        ["available_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_expires_at"),
        "admin_alert_outbox_entries",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_entries_created_by_user_id"),
        "admin_alert_outbox_entries",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_alert_outbox_entries_created_by_user_id"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_expires_at"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_available_at"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_last_seen_at"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_status"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_action_hint"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_severity"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_event_code"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_source_key"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_source_id"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_source_type"), table_name="admin_alert_outbox_entries")
    op.drop_index(op.f("ix_admin_alert_outbox_entries_id"), table_name="admin_alert_outbox_entries")
    op.drop_table("admin_alert_outbox_entries")
