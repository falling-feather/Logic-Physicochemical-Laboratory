"""serialize security-sensitive control-plane transitions

Revision ID: 20260710_0045
Revises: 20260710_0044
Create Date: 2026-07-10
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op


revision = "20260710_0045"
down_revision = "20260710_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_control_locks",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "security_control_locks",
            sa.column("name", sa.String(length=80)),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [{"name": "admin-authority", "created_at": now, "updated_at": now}],
    )


def downgrade() -> None:
    op.drop_table("security_control_locks")
