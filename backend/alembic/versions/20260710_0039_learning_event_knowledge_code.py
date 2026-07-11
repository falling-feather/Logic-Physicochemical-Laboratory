"""add learning event knowledge code

Revision ID: 20260710_0039
Revises: 20260710_0038
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0039"
down_revision = "20260710_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_events", sa.Column("knowledge_code", sa.String(length=120), nullable=True))
    op.create_index(
        op.f("ix_learning_events_knowledge_code"),
        "learning_events",
        ["knowledge_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_events_knowledge_code"), table_name="learning_events")
    op.drop_column("learning_events", "knowledge_code")
