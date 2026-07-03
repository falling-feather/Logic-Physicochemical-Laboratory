"""add user knowledge snapshots

Revision ID: 20260703_0010
Revises: 20260703_0009
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0010"
down_revision = "20260703_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_knowledge_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("class_scope_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("course_scope_id", sa.Integer(), nullable=False),
        sa.Column("granularity", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("assignment_count", sa.Integer(), nullable=False),
        sa.Column("submitted_assignments", sa.Integer(), nullable=False),
        sa.Column("graded_assignments", sa.Integer(), nullable=False),
        sa.Column("total_events", sa.Integer(), nullable=False),
        sa.Column("visit_events", sa.Integer(), nullable=False),
        sa.Column("start_events", sa.Integer(), nullable=False),
        sa.Column("submit_events", sa.Integer(), nullable=False),
        sa.Column("complete_events", sa.Integer(), nullable=False),
        sa.Column("score_total", sa.Integer(), nullable=False),
        sa.Column("max_score_total", sa.Integer(), nullable=False),
        sa.Column("accuracy_percent", sa.Float(), nullable=False),
        sa.Column("completion_percent", sa.Float(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("knowledge_stats_json", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "class_scope_id",
            "course_scope_id",
            "granularity",
            "period_start",
            "period_end",
            "rule_version",
            name="uq_user_knowledge_snapshot_window",
        ),
    )
    op.create_index(op.f("ix_user_knowledge_snapshots_class_id"), "user_knowledge_snapshots", ["class_id"], unique=False)
    op.create_index(
        op.f("ix_user_knowledge_snapshots_course_id"),
        "user_knowledge_snapshots",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_knowledge_snapshots_created_by_user_id"),
        "user_knowledge_snapshots",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_knowledge_snapshots_granularity"),
        "user_knowledge_snapshots",
        ["granularity"],
        unique=False,
    )
    op.create_index(op.f("ix_user_knowledge_snapshots_id"), "user_knowledge_snapshots", ["id"], unique=False)
    op.create_index(
        op.f("ix_user_knowledge_snapshots_period_end"),
        "user_knowledge_snapshots",
        ["period_end"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_knowledge_snapshots_period_start"),
        "user_knowledge_snapshots",
        ["period_start"],
        unique=False,
    )
    op.create_index(op.f("ix_user_knowledge_snapshots_school_id"), "user_knowledge_snapshots", ["school_id"], unique=False)
    op.create_index(op.f("ix_user_knowledge_snapshots_user_id"), "user_knowledge_snapshots", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_knowledge_snapshots_user_id"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_school_id"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_period_start"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_period_end"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_id"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_granularity"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_created_by_user_id"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_course_id"), table_name="user_knowledge_snapshots")
    op.drop_index(op.f("ix_user_knowledge_snapshots_class_id"), table_name="user_knowledge_snapshots")
    op.drop_table("user_knowledge_snapshots")
