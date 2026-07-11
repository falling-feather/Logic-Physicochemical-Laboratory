"""add auth session device metadata

Revision ID: 20260707_0023
Revises: 20260706_0022
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0023"
down_revision = "20260706_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("device_label", sa.String(length=120), nullable=True))
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(length=240), nullable=True))
    op.add_column("auth_sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_sessions", sa.Column("last_seen_ip_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_sessions", "last_seen_ip_hash")
    op.drop_column("auth_sessions", "last_seen_at")
    op.drop_column("auth_sessions", "user_agent")
    op.drop_column("auth_sessions", "device_label")
