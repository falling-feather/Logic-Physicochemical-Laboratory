"""add content script asset scan scheduler metadata

Revision ID: 20260708_0033
Revises: 20260708_0032
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0033"
down_revision = "20260708_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_script_asset_scan_runs") as batch_op:
        batch_op.alter_column("finished_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch_op.alter_column("created_by_user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("scheduler_lease_owner", sa.String(length=96), nullable=True))
        batch_op.add_column(sa.Column("scheduler_lease_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("scheduler_lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("scheduler_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_unique_constraint("uq_content_script_asset_scan_runs_run_key", ["run_key"])
        batch_op.create_index(
            op.f("ix_content_script_asset_scan_runs_scheduler_lease_expires_at"),
            ["scheduler_lease_expires_at"],
            unique=False,
        )
    with op.batch_alter_table("content_script_asset_scan_runs") as batch_op:
        batch_op.alter_column("attempt_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("content_script_asset_scan_runs") as batch_op:
        batch_op.drop_index(op.f("ix_content_script_asset_scan_runs_scheduler_lease_expires_at"))
        batch_op.drop_constraint("uq_content_script_asset_scan_runs_run_key", type_="unique")
        batch_op.drop_column("scheduler_heartbeat_at")
        batch_op.drop_column("scheduler_lease_expires_at")
        batch_op.drop_column("scheduler_lease_token")
        batch_op.drop_column("scheduler_lease_owner")
        batch_op.drop_column("attempt_count")
        batch_op.alter_column("created_by_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("finished_at", existing_type=sa.DateTime(timezone=True), nullable=False)
