"""add admin alert outbox review fields

Revision ID: 20260708_0035
Revises: 20260708_0034
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0035"
down_revision = "20260708_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_alert_outbox_entries") as batch_op:
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_admin_alert_outbox_entries_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_admin_alert_outbox_entries_reviewed_by_user_id"),
            ["reviewed_by_user_id"],
            unique=False,
        )
        batch_op.create_index(op.f("ix_admin_alert_outbox_entries_reviewed_at"), ["reviewed_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("admin_alert_outbox_entries") as batch_op:
        batch_op.drop_index(op.f("ix_admin_alert_outbox_entries_reviewed_at"))
        batch_op.drop_index(op.f("ix_admin_alert_outbox_entries_reviewed_by_user_id"))
        batch_op.drop_constraint(
            "fk_admin_alert_outbox_entries_reviewed_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by_user_id")
