"""add course collaborators

Revision ID: 20260707_0029
Revises: 20260707_0028
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0029"
down_revision = "20260707_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_collaborators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_collaborators_course_user"),
    )
    op.create_index(op.f("ix_course_collaborators_id"), "course_collaborators", ["id"], unique=False)
    op.create_index(op.f("ix_course_collaborators_course_id"), "course_collaborators", ["course_id"], unique=False)
    op.create_index(op.f("ix_course_collaborators_user_id"), "course_collaborators", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_course_collaborators_user_id"), table_name="course_collaborators")
    op.drop_index(op.f("ix_course_collaborators_course_id"), table_name="course_collaborators")
    op.drop_index(op.f("ix_course_collaborators_id"), table_name="course_collaborators")
    op.drop_table("course_collaborators")
