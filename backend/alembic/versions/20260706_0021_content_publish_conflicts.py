"""guard content publish conflicts

Revision ID: 20260706_0021
Revises: 20260706_0020
Create Date: 2026-07-06
"""

from alembic import op


revision = "20260706_0021"
down_revision = "20260706_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_page_versions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_content_page_versions_source_draft_id",
            ["source_draft_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("content_page_versions") as batch_op:
        batch_op.drop_constraint("uq_content_page_versions_source_draft_id", type_="unique")
