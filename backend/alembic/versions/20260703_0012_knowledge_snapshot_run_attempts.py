"""add knowledge snapshot run attempts

Revision ID: 20260703_0012
Revises: 20260703_0011
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0012"
down_revision = "20260703_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_snapshot_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("knowledge_snapshot_runs", "attempt_count")
