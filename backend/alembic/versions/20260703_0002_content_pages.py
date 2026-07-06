"""add content pages

Revision ID: 20260703_0002
Revises: 20260703_0001
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0002"
down_revision = "20260703_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_pages_id"), "content_pages", ["id"], unique=False)
    op.create_index(op.f("ix_content_pages_slug"), "content_pages", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_content_pages_slug"), table_name="content_pages")
    op.drop_index(op.f("ix_content_pages_id"), table_name="content_pages")
    op.drop_table("content_pages")

