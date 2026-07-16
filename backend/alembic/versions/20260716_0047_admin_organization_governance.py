"""add versioned organization governance fields

Revision ID: 20260716_0047
Revises: 20260710_0046
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_0047"
down_revision = "20260710_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("schools", "class_groups"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
            batch_op.add_column(
                sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False)
            )


def downgrade() -> None:
    for table_name in ("class_groups", "schools"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("version")
            batch_op.drop_column("description")
