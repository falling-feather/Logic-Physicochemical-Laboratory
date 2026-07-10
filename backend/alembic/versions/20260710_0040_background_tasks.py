"""add unified background task queue

Revision ID: 20260710_0040
Revises: 20260710_0039
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0040"
down_revision = "20260710_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_summary_json", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_background_tasks_idempotency_key"),
    )
    for column in (
        "id",
        "task_type",
        "source_type",
        "source_id",
        "status",
        "available_at",
        "lease_expires_at",
        "finished_at",
        "created_by_user_id",
    ):
        op.create_index(op.f(f"ix_background_tasks_{column}"), "background_tasks", [column], unique=False)
    op.create_index(
        "ix_background_tasks_claim",
        "background_tasks",
        ["status", "available_at", "priority", "id"],
        unique=False,
    )

    op.create_table(
        "background_task_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("result_summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["background_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "attempt_number", name="uq_background_task_attempts_task_number"),
    )
    for column in ("id", "task_id", "worker_id", "status"):
        op.create_index(
            op.f(f"ix_background_task_attempts_{column}"),
            "background_task_attempts",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("status", "worker_id", "task_id", "id"):
        op.drop_index(op.f(f"ix_background_task_attempts_{column}"), table_name="background_task_attempts")
    op.drop_table("background_task_attempts")
    op.drop_index("ix_background_tasks_claim", table_name="background_tasks")
    for column in (
        "created_by_user_id",
        "finished_at",
        "lease_expires_at",
        "available_at",
        "status",
        "source_id",
        "source_type",
        "task_type",
        "id",
    ):
        op.drop_index(op.f(f"ix_background_tasks_{column}"), table_name="background_tasks")
    op.drop_table("background_tasks")
