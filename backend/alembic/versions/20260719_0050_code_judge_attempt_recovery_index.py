"""add bounded code-judge expiry recovery index

Revision ID: 20260719_0050
Revises: 20260719_0049
Create Date: 2026-07-19
"""

from alembic import op


revision = "20260719_0050"
down_revision = "20260719_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_code_judge_attempts_expired_claim",
        "code_judge_attempts",
        ["status", "claim_expires_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_code_judge_attempts_expired_claim", table_name="code_judge_attempts")
