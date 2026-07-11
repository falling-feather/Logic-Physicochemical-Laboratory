"""add knowledge snapshot scheduler leases

Revision ID: 20260707_0026
Revises: 20260707_0025
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0026"
down_revision = "20260707_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_snapshot_runs", sa.Column("scheduler_lease_owner", sa.String(length=96), nullable=True))
    op.add_column("knowledge_snapshot_runs", sa.Column("scheduler_lease_token", sa.String(length=64), nullable=True))
    op.add_column(
        "knowledge_snapshot_runs",
        sa.Column("scheduler_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("knowledge_snapshot_runs", sa.Column("scheduler_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_knowledge_snapshot_runs_scheduler_lease_expires_at"),
        "knowledge_snapshot_runs",
        ["scheduler_lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_snapshot_runs_scheduler_lease_expires_at"), table_name="knowledge_snapshot_runs")
    op.drop_column("knowledge_snapshot_runs", "scheduler_heartbeat_at")
    op.drop_column("knowledge_snapshot_runs", "scheduler_lease_expires_at")
    op.drop_column("knowledge_snapshot_runs", "scheduler_lease_token")
    op.drop_column("knowledge_snapshot_runs", "scheduler_lease_owner")
