"""add content draft script policy metadata

Revision ID: 20260704_0018
Revises: 20260704_0017
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260704_0018"
down_revision = "20260704_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.add_column(sa.Column("script_risk_level", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("script_analysis_json", sa.JSON(), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_drafts_script_risk_level"), ["script_risk_level"])

    op.execute(
        sa.text(
            """
            UPDATE content_drafts
            SET script_risk_level = CASE
                WHEN allow_script THEN 'medium'
                ELSE 'none'
            END
            WHERE script_risk_level IS NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.drop_index(batch_op.f("ix_content_drafts_script_risk_level"))
        batch_op.drop_column("script_analysis_json")
        batch_op.drop_column("script_risk_level")
