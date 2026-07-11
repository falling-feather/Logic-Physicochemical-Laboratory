"""add content drafts

Revision ID: 20260704_0014
Revises: 20260703_0013
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0014"
down_revision = "20260703_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("target_slug", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("allow_script", sa.Boolean(), nullable=False),
        sa.Column("script_review_status", sa.String(length=32), nullable=False),
        sa.Column("script_reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("script_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("script_review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["script_reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_drafts_author_user_id"), "content_drafts", ["author_user_id"], unique=False)
    op.create_index(op.f("ix_content_drafts_id"), "content_drafts", ["id"], unique=False)
    op.create_index(
        op.f("ix_content_drafts_script_review_status"),
        "content_drafts",
        ["script_review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_drafts_script_reviewed_by_user_id"),
        "content_drafts",
        ["script_reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_content_drafts_status"), "content_drafts", ["status"], unique=False)
    op.create_index(op.f("ix_content_drafts_target_slug"), "content_drafts", ["target_slug"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_content_drafts_target_slug"), table_name="content_drafts")
    op.drop_index(op.f("ix_content_drafts_status"), table_name="content_drafts")
    op.drop_index(op.f("ix_content_drafts_script_reviewed_by_user_id"), table_name="content_drafts")
    op.drop_index(op.f("ix_content_drafts_script_review_status"), table_name="content_drafts")
    op.drop_index(op.f("ix_content_drafts_id"), table_name="content_drafts")
    op.drop_index(op.f("ix_content_drafts_author_user_id"), table_name="content_drafts")
    op.drop_table("content_drafts")
