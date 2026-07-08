"""add admin alert outbox dispatch plan hashes

Revision ID: 20260708_0037
Revises: 20260708_0036
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0037"
down_revision = "20260708_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_alert_outbox_dispatch_plans") as batch_op:
        batch_op.add_column(sa.Column("ready_entry_payload_hashes_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("admin_alert_outbox_dispatch_plans") as batch_op:
        batch_op.drop_column("ready_entry_payload_hashes_json")
