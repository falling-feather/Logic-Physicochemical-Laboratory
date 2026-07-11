"""add admin alert outbox dispatch plans

Revision ID: 20260708_0036
Revises: 20260708_0035
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0036"
down_revision = "20260708_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_alert_outbox_dispatch_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_key", sa.String(length=64), nullable=False),
        sa.Column("plan_status", sa.String(length=32), nullable=False),
        sa.Column("dry_run_status", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("ready_entry_ids_json", sa.JSON(), nullable=False),
        sa.Column("blocked_reason_counts_json", sa.JSON(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("ready_count", sa.Integer(), nullable=False),
        sa.Column("blocked_count", sa.Integer(), nullable=False),
        sa.Column("expired_count", sa.Integer(), nullable=False),
        sa.Column("not_due_count", sa.Integer(), nullable=False),
        sa.Column("terminal_count", sa.Integer(), nullable=False),
        sa.Column("external_delivery_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_key", name="uq_admin_alert_outbox_dispatch_plans_plan_key"),
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_id"),
        "admin_alert_outbox_dispatch_plans",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_plan_status"),
        "admin_alert_outbox_dispatch_plans",
        ["plan_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_dry_run_status"),
        "admin_alert_outbox_dispatch_plans",
        ["dry_run_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_source_type"),
        "admin_alert_outbox_dispatch_plans",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_generated_at"),
        "admin_alert_outbox_dispatch_plans",
        ["generated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_created_by_user_id"),
        "admin_alert_outbox_dispatch_plans",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_created_by_user_id"),
        table_name="admin_alert_outbox_dispatch_plans",
    )
    op.drop_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_generated_at"),
        table_name="admin_alert_outbox_dispatch_plans",
    )
    op.drop_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_source_type"),
        table_name="admin_alert_outbox_dispatch_plans",
    )
    op.drop_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_dry_run_status"),
        table_name="admin_alert_outbox_dispatch_plans",
    )
    op.drop_index(
        op.f("ix_admin_alert_outbox_dispatch_plans_plan_status"),
        table_name="admin_alert_outbox_dispatch_plans",
    )
    op.drop_index(op.f("ix_admin_alert_outbox_dispatch_plans_id"), table_name="admin_alert_outbox_dispatch_plans")
    op.drop_table("admin_alert_outbox_dispatch_plans")
