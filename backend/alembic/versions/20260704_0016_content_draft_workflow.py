"""add content draft workflow metadata

Revision ID: 20260704_0016
Revises: 20260704_0015
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260704_0016"
down_revision = "20260704_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("change_requested_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("change_requested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("change_request_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("published_page_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("published_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("published_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_drafts_change_requested_by_user_id"), ["change_requested_by_user_id"])
        batch_op.create_index(batch_op.f("ix_content_drafts_published_by_user_id"), ["published_by_user_id"])
        batch_op.create_index(batch_op.f("ix_content_drafts_published_page_id"), ["published_page_id"])
        batch_op.create_index(batch_op.f("ix_content_drafts_published_version_id"), ["published_version_id"])
        batch_op.create_index(batch_op.f("ix_content_drafts_submitted_at"), ["submitted_at"])
        batch_op.create_foreign_key(
            "fk_content_drafts_change_requested_by_user_id_users",
            "users",
            ["change_requested_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_content_drafts_published_by_user_id_users",
            "users",
            ["published_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_content_drafts_published_page_id_content_pages",
            "content_pages",
            ["published_page_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_content_drafts_published_version_id_content_page_versions",
            "content_page_versions",
            ["published_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.drop_constraint("fk_content_drafts_published_version_id_content_page_versions", type_="foreignkey")
        batch_op.drop_constraint("fk_content_drafts_published_page_id_content_pages", type_="foreignkey")
        batch_op.drop_constraint("fk_content_drafts_published_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_content_drafts_change_requested_by_user_id_users", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_content_drafts_submitted_at"))
        batch_op.drop_index(batch_op.f("ix_content_drafts_published_version_id"))
        batch_op.drop_index(batch_op.f("ix_content_drafts_published_page_id"))
        batch_op.drop_index(batch_op.f("ix_content_drafts_published_by_user_id"))
        batch_op.drop_index(batch_op.f("ix_content_drafts_change_requested_by_user_id"))
        batch_op.drop_column("published_at")
        batch_op.drop_column("published_by_user_id")
        batch_op.drop_column("published_version_id")
        batch_op.drop_column("published_page_id")
        batch_op.drop_column("change_request_note")
        batch_op.drop_column("change_requested_at")
        batch_op.drop_column("change_requested_by_user_id")
        batch_op.drop_column("withdrawn_at")
        batch_op.drop_column("submitted_at")
