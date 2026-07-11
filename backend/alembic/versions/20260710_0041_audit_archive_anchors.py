"""add audit chain head and external archive anchor ledger

Revision ID: 20260710_0041
Revises: 20260710_0040
Create Date: 2026-07-10
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260710_0041"
down_revision = "20260710_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit_chain_heads = op.create_table(
        "audit_chain_heads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_audit_log_id", sa.Integer(), nullable=True),
        sa.Column("current_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    connection = op.get_bind()
    latest = connection.execute(
        sa.text(
            "SELECT id, current_hash FROM audit_logs "
            "WHERE current_hash IS NOT NULL ORDER BY id DESC LIMIT 1"
        )
    ).mappings().first()
    now = datetime.now(UTC)
    connection.execute(
        audit_chain_heads.insert().values(
            {
                "id": 1,
                "current_audit_log_id": latest["id"] if latest is not None else None,
                "current_hash": latest["current_hash"] if latest is not None else None,
                "created_at": now,
                "updated_at": now,
            }
        )
    )

    op.create_table(
        "audit_archive_anchors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("manifest_schema_version", sa.Integer(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_path_sha256", sa.String(length=64), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("evidence_level", sa.String(length=32), nullable=False),
        sa.Column("exported_count", sa.Integer(), nullable=False),
        sa.Column("first_log_id", sa.Integer(), nullable=True),
        sa.Column("last_log_id", sa.Integer(), nullable=True),
        sa.Column("oldest_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("newest_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chain_start_prev_hash", sa.String(length=64), nullable=True),
        sa.Column("chain_end_current_hash", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_receipt_id", sa.String(length=200), nullable=True),
        sa.Column("external_anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_sha256", name="uq_audit_archive_anchors_manifest_sha256"),
    )
    for column in ("id", "status", "anchored_at", "created_by_user_id"):
        op.create_index(
            op.f(f"ix_audit_archive_anchors_{column}"),
            "audit_archive_anchors",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("created_by_user_id", "anchored_at", "status", "id"):
        op.drop_index(op.f(f"ix_audit_archive_anchors_{column}"), table_name="audit_archive_anchors")
    op.drop_table("audit_archive_anchors")
    op.drop_table("audit_chain_heads")
