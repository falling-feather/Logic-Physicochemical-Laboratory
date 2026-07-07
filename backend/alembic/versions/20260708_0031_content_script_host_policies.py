"""add content script host policies

Revision ID: 20260708_0031
Revises: 20260707_0030
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260708_0031"
down_revision = "20260707_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_script_host_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_host", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_host"),
    )
    op.create_index(op.f("ix_content_script_host_policies_id"), "content_script_host_policies", ["id"], unique=False)
    op.create_index(
        op.f("ix_content_script_host_policies_source_host"),
        "content_script_host_policies",
        ["source_host"],
        unique=True,
    )
    op.create_index(
        op.f("ix_content_script_host_policies_status"),
        "content_script_host_policies",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_host_policies_reviewed_by_user_id"),
        "content_script_host_policies",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_host_policies_reviewed_at"),
        "content_script_host_policies",
        ["reviewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_content_script_host_policies_reviewed_at"), table_name="content_script_host_policies")
    op.drop_index(
        op.f("ix_content_script_host_policies_reviewed_by_user_id"),
        table_name="content_script_host_policies",
    )
    op.drop_index(op.f("ix_content_script_host_policies_status"), table_name="content_script_host_policies")
    op.drop_index(op.f("ix_content_script_host_policies_source_host"), table_name="content_script_host_policies")
    op.drop_index(op.f("ix_content_script_host_policies_id"), table_name="content_script_host_policies")
    op.drop_table("content_script_host_policies")
