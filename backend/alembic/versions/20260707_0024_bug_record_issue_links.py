"""add bug record external issue links

Revision ID: 20260707_0024
Revises: 20260707_0023
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0024"
down_revision = "20260707_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bug_records", sa.Column("external_issue_provider", sa.String(length=80), nullable=True))
    op.add_column("bug_records", sa.Column("external_issue_id", sa.String(length=120), nullable=True))
    op.add_column("bug_records", sa.Column("external_issue_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("bug_records", "external_issue_url")
    op.drop_column("bug_records", "external_issue_id")
    op.drop_column("bug_records", "external_issue_provider")
