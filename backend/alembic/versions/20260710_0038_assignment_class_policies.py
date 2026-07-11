"""add assignment class policies

Revision ID: 20260710_0038
Revises: 20260708_0037
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0038"
down_revision = "20260708_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column(
            "audience_mode",
            sa.String(length=32),
            nullable=False,
            server_default="all_attached_classes",
        ),
    )
    op.create_table(
        "assignment_class_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("assigned", sa.Boolean(), nullable=False),
        sa.Column("status_override", sa.String(length=32), nullable=True),
        sa.Column("due_at_overridden", sa.Boolean(), nullable=False),
        sa.Column("due_at_override", sa.DateTime(timezone=True), nullable=True),
        sa.Column("point_rule_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            "class_id",
            name="uq_assignment_class_policies_assignment_class",
        ),
    )
    op.create_index(
        op.f("ix_assignment_class_policies_id"),
        "assignment_class_policies",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignment_class_policies_assignment_id"),
        "assignment_class_policies",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assignment_class_policies_class_id"),
        "assignment_class_policies",
        ["class_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assignment_class_policies_class_id"),
        table_name="assignment_class_policies",
    )
    op.drop_index(
        op.f("ix_assignment_class_policies_assignment_id"),
        table_name="assignment_class_policies",
    )
    op.drop_index(op.f("ix_assignment_class_policies_id"), table_name="assignment_class_policies")
    op.drop_table("assignment_class_policies")
    op.drop_column("assignments", "audience_mode")
