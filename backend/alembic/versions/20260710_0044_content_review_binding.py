"""bind content review to the last editor and exact schema

Revision ID: 20260710_0044
Revises: 20260710_0043
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op


revision = "20260710_0044"
down_revision = "20260710_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.add_column(sa.Column("last_editor_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("script_reviewed_schema_hash", sa.String(length=64), nullable=True))

    op.execute(
        sa.text(
            "UPDATE content_drafts "
            "SET last_editor_user_id = author_user_id "
            "WHERE last_editor_user_id IS NULL"
        )
    )

    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.alter_column("last_editor_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_content_drafts_last_editor_user_id_users",
            "users",
            ["last_editor_user_id"],
            ["id"],
        )
        batch_op.create_index("ix_content_drafts_last_editor_user_id", ["last_editor_user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.drop_constraint("fk_content_drafts_last_editor_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_content_drafts_last_editor_user_id")
        batch_op.drop_column("script_reviewed_schema_hash")
        batch_op.drop_column("last_editor_user_id")
