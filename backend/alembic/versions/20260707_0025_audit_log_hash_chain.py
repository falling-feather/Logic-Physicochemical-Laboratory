"""add audit log hash chain

Revision ID: 20260707_0025
Revises: 20260707_0024
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0025"
down_revision = "20260707_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("current_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "current_hash")
    op.drop_column("audit_logs", "prev_hash")
