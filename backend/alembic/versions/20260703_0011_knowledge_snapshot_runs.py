"""add knowledge snapshot runs

Revision ID: 20260703_0011
Revises: 20260703_0010
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0011"
down_revision = "20260703_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_snapshot_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_key", sa.String(length=160), nullable=False),
        sa.Column("granularity", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_snapshot_count", sa.Integer(), nullable=False),
        sa.Column("class_snapshot_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_key", name="uq_knowledge_snapshot_runs_run_key"),
    )
    op.create_index(op.f("ix_knowledge_snapshot_runs_granularity"), "knowledge_snapshot_runs", ["granularity"], unique=False)
    op.create_index(op.f("ix_knowledge_snapshot_runs_id"), "knowledge_snapshot_runs", ["id"], unique=False)
    op.create_index(op.f("ix_knowledge_snapshot_runs_period_end"), "knowledge_snapshot_runs", ["period_end"], unique=False)
    op.create_index(op.f("ix_knowledge_snapshot_runs_period_start"), "knowledge_snapshot_runs", ["period_start"], unique=False)
    op.create_index(op.f("ix_knowledge_snapshot_runs_status"), "knowledge_snapshot_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_snapshot_runs_status"), table_name="knowledge_snapshot_runs")
    op.drop_index(op.f("ix_knowledge_snapshot_runs_period_start"), table_name="knowledge_snapshot_runs")
    op.drop_index(op.f("ix_knowledge_snapshot_runs_period_end"), table_name="knowledge_snapshot_runs")
    op.drop_index(op.f("ix_knowledge_snapshot_runs_id"), table_name="knowledge_snapshot_runs")
    op.drop_index(op.f("ix_knowledge_snapshot_runs_granularity"), table_name="knowledge_snapshot_runs")
    op.drop_table("knowledge_snapshot_runs")
