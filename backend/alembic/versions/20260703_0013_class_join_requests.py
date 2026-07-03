"""add class join requests

Revision ID: 20260703_0013
Revises: 20260703_0012
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0013"
down_revision = "20260703_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_join_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "user_id", "role", name="uq_class_join_request_user_role"),
    )
    op.create_index(op.f("ix_class_join_requests_class_id"), "class_join_requests", ["class_id"], unique=False)
    op.create_index(op.f("ix_class_join_requests_id"), "class_join_requests", ["id"], unique=False)
    op.create_index(
        op.f("ix_class_join_requests_requested_by_user_id"),
        "class_join_requests",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_class_join_requests_reviewed_by_user_id"),
        "class_join_requests",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_class_join_requests_school_id"), "class_join_requests", ["school_id"], unique=False)
    op.create_index(op.f("ix_class_join_requests_status"), "class_join_requests", ["status"], unique=False)
    op.create_index(op.f("ix_class_join_requests_user_id"), "class_join_requests", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_class_join_requests_user_id"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_status"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_school_id"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_reviewed_by_user_id"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_requested_by_user_id"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_id"), table_name="class_join_requests")
    op.drop_index(op.f("ix_class_join_requests_class_id"), table_name="class_join_requests")
    op.drop_table("class_join_requests")
