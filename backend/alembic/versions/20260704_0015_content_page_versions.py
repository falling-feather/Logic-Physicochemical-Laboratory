"""add content page versions

Revision ID: 20260704_0015
Revises: 20260704_0014
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0015"
down_revision = "20260704_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_page_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("source_draft_id", sa.Integer(), nullable=True),
        sa.Column("restored_from_version_id", sa.Integer(), nullable=True),
        sa.Column("published_by_user_id", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["content_pages.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["restored_from_version_id"], ["content_page_versions.id"]),
        sa.ForeignKeyConstraint(["source_draft_id"], ["content_drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", "version", name="uq_content_page_versions_slug_version"),
    )
    op.create_index(op.f("ix_content_page_versions_id"), "content_page_versions", ["id"], unique=False)
    op.create_index(op.f("ix_content_page_versions_page_id"), "content_page_versions", ["page_id"], unique=False)
    op.create_index(
        op.f("ix_content_page_versions_published_at"),
        "content_page_versions",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_page_versions_published_by_user_id"),
        "content_page_versions",
        ["published_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_page_versions_restored_from_version_id"),
        "content_page_versions",
        ["restored_from_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_content_page_versions_slug"), "content_page_versions", ["slug"], unique=False)
    op.create_index(
        op.f("ix_content_page_versions_source_draft_id"),
        "content_page_versions",
        ["source_draft_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_content_page_versions_source_draft_id"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_slug"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_restored_from_version_id"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_published_by_user_id"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_published_at"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_page_id"), table_name="content_page_versions")
    op.drop_index(op.f("ix_content_page_versions_id"), table_name="content_page_versions")
    op.drop_table("content_page_versions")
