"""add content script asset scan runs

Revision ID: 20260708_0032
Revises: 20260708_0031
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0032"
down_revision = "20260708_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_script_asset_scan_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_key", sa.String(length=160), nullable=False),
        sa.Column("scan_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("totals_json", sa.JSON(), nullable=False),
        sa.Column("issue_counts_json", sa.JSON(), nullable=False),
        sa.Column("issue_summary_json", sa.JSON(), nullable=False),
        sa.Column("alert_status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_script_asset_scan_runs_id"), "content_script_asset_scan_runs", ["id"], unique=False)
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_run_key"),
        "content_script_asset_scan_runs",
        ["run_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_scan_type"),
        "content_script_asset_scan_runs",
        ["scan_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_trigger_source"),
        "content_script_asset_scan_runs",
        ["trigger_source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_status"),
        "content_script_asset_scan_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_started_at"),
        "content_script_asset_scan_runs",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_finished_at"),
        "content_script_asset_scan_runs",
        ["finished_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_created_by_user_id"),
        "content_script_asset_scan_runs",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_asset_scan_runs_alert_status"),
        "content_script_asset_scan_runs",
        ["alert_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_content_script_asset_scan_runs_alert_status"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_created_by_user_id"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_finished_at"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_started_at"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_status"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_trigger_source"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_scan_type"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_run_key"), table_name="content_script_asset_scan_runs")
    op.drop_index(op.f("ix_content_script_asset_scan_runs_id"), table_name="content_script_asset_scan_runs")
    op.drop_table("content_script_asset_scan_runs")
