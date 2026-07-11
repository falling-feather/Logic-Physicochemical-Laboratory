"""add content draft active uniqueness key

Revision ID: 20260706_0019
Revises: 20260704_0018
Create Date: 2026-07-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260706_0019"
down_revision = "20260704_0018"
branch_labels = None
depends_on = None


ACTIVE_DRAFT_KEY = "active"
ACTIVE_DRAFT_UNIQUE_CONSTRAINT = "uq_content_drafts_active_author_target"


def upgrade() -> None:
    _reject_duplicate_active_drafts()

    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.add_column(sa.Column("active_key", sa.String(length=16), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_drafts_active_key"), ["active_key"])

    op.execute(
        sa.text(
            """
            UPDATE content_drafts
            SET active_key = :active_key
            WHERE status IN ('draft', 'submitted', 'changes_requested')
            """
        ).bindparams(active_key=ACTIVE_DRAFT_KEY)
    )

    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.create_unique_constraint(
            ACTIVE_DRAFT_UNIQUE_CONSTRAINT,
            ["author_user_id", "target_slug", "active_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.drop_constraint(ACTIVE_DRAFT_UNIQUE_CONSTRAINT, type_="unique")
        batch_op.drop_index(batch_op.f("ix_content_drafts_active_key"))
        batch_op.drop_column("active_key")


def _reject_duplicate_active_drafts() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            """
            SELECT author_user_id, target_slug, COUNT(*) AS draft_count, GROUP_CONCAT(id) AS draft_ids
            FROM content_drafts
            WHERE status IN ('draft', 'submitted', 'changes_requested')
            GROUP BY author_user_id, target_slug
            HAVING COUNT(*) > 1
            """
        )
    ).mappings().all()
    if not duplicates:
        return

    details = "; ".join(
        f"author={row['author_user_id']} target={row['target_slug']} draft_ids={row['draft_ids']}"
        for row in duplicates
    )
    raise RuntimeError(
        "Cannot add active content draft uniqueness while duplicate active drafts exist. "
        "Withdraw, publish, or merge duplicates before running this migration: "
        f"{details}"
    )
