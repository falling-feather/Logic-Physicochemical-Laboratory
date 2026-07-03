"""add admin bug records

Revision ID: 20260703_0005
Revises: 20260703_0004
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0005"
down_revision = "20260703_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bug_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=240), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bug_records_id"), "bug_records", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bug_records_id"), table_name="bug_records")
    op.drop_table("bug_records")
