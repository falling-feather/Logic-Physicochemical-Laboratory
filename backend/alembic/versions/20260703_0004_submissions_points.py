"""add submissions and point ledger

Revision ID: 20260703_0004
Revises: 20260703_0003
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0004"
down_revision = "20260703_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("graded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["graded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_submissions_assignment_student"),
    )
    op.create_index(op.f("ix_submissions_assignment_id"), "submissions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_submissions_class_id"), "submissions", ["class_id"], unique=False)
    op.create_index(op.f("ix_submissions_graded_by_user_id"), "submissions", ["graded_by_user_id"], unique=False)
    op.create_index(op.f("ix_submissions_id"), "submissions", ["id"], unique=False)
    op.create_index(op.f("ix_submissions_student_id"), "submissions", ["student_id"], unique=False)

    op.create_table(
        "point_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_point_ledger_assignment_id"), "point_ledger", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_point_ledger_class_id"), "point_ledger", ["class_id"], unique=False)
    op.create_index(op.f("ix_point_ledger_created_by_user_id"), "point_ledger", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_point_ledger_id"), "point_ledger", ["id"], unique=False)
    op.create_index(op.f("ix_point_ledger_school_id"), "point_ledger", ["school_id"], unique=False)
    op.create_index(op.f("ix_point_ledger_submission_id"), "point_ledger", ["submission_id"], unique=False)
    op.create_index(op.f("ix_point_ledger_user_id"), "point_ledger", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_point_ledger_user_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_submission_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_school_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_created_by_user_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_class_id"), table_name="point_ledger")
    op.drop_index(op.f("ix_point_ledger_assignment_id"), table_name="point_ledger")
    op.drop_table("point_ledger")
    op.drop_index(op.f("ix_submissions_student_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_graded_by_user_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_class_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_assignment_id"), table_name="submissions")
    op.drop_table("submissions")
