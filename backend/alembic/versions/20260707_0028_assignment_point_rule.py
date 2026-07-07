"""add assignment point rule json

Revision ID: 20260707_0028
Revises: 20260707_0027
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0028"
down_revision = "20260707_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assignments", sa.Column("point_rule_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("assignments", "point_rule_json")
