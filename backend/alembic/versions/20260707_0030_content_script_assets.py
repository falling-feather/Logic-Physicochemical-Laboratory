"""add content script assets

Revision ID: 20260707_0030
Revises: 20260707_0029
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260707_0030"
down_revision = "20260707_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_script_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("page_version_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("sandbox_id", sa.String(length=32), nullable=False),
        sa.Column("reference_key", sa.String(length=64), nullable=False),
        sa.Column("reference_value_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_host", sa.String(length=255), nullable=False),
        sa.Column("integrity", sa.Text(), nullable=False),
        sa.Column("matched_algorithm", sa.String(length=16), nullable=False),
        sa.Column("asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("asset_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(length=1048576), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_context_hash", sa.String(length=64), nullable=False),
        sa.Column("published_by_user_id", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["content_pages.id"]),
        sa.ForeignKeyConstraint(["page_version_id"], ["content_page_versions.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "page_version_id",
            "sandbox_id",
            "reference_value_sha256",
            name="uq_content_script_assets_version_sandbox_reference",
        ),
    )
    op.create_index(op.f("ix_content_script_assets_id"), "content_script_assets", ["id"], unique=False)
    op.create_index(op.f("ix_content_script_assets_page_id"), "content_script_assets", ["page_id"], unique=False)
    op.create_index(
        op.f("ix_content_script_assets_page_version_id"),
        "content_script_assets",
        ["page_version_id"],
        unique=False,
    )
    op.create_index(op.f("ix_content_script_assets_slug"), "content_script_assets", ["slug"], unique=False)
    op.create_index(op.f("ix_content_script_assets_sandbox_id"), "content_script_assets", ["sandbox_id"], unique=False)
    op.create_index(
        op.f("ix_content_script_assets_reference_value_sha256"),
        "content_script_assets",
        ["reference_value_sha256"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_assets_source_host"),
        "content_script_assets",
        ["source_host"],
        unique=False,
    )
    op.create_index(op.f("ix_content_script_assets_asset_sha256"), "content_script_assets", ["asset_sha256"], unique=False)
    op.create_index(
        op.f("ix_content_script_assets_policy_context_hash"),
        "content_script_assets",
        ["policy_context_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_assets_published_by_user_id"),
        "content_script_assets",
        ["published_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_script_assets_published_at"),
        "content_script_assets",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        "ix_content_script_assets_slug_sandbox_reference",
        "content_script_assets",
        ["slug", "sandbox_id", "reference_value_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_content_script_assets_slug_sandbox_reference", table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_published_at"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_published_by_user_id"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_policy_context_hash"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_asset_sha256"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_source_host"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_reference_value_sha256"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_sandbox_id"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_slug"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_page_version_id"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_page_id"), table_name="content_script_assets")
    op.drop_index(op.f("ix_content_script_assets_id"), table_name="content_script_assets")
    op.drop_table("content_script_assets")
