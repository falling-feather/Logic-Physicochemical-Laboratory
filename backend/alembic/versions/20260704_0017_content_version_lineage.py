"""add content version lineage metadata

Revision ID: 20260704_0017
Revises: 20260704_0016
Create Date: 2026-07-04
"""

from __future__ import annotations

import hashlib
import json

from alembic import op
import sqlalchemy as sa


revision = "20260704_0017"
down_revision = "20260704_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_pages") as batch_op:
        batch_op.add_column(sa.Column("schema_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("current_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("published_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_pages_current_version_id"), ["current_version_id"])
        batch_op.create_index(batch_op.f("ix_content_pages_published_at"), ["published_at"])
        batch_op.create_index(batch_op.f("ix_content_pages_published_by_user_id"), ["published_by_user_id"])
        batch_op.create_index(batch_op.f("ix_content_pages_schema_hash"), ["schema_hash"])
        batch_op.create_foreign_key(
            "fk_content_pages_current_version_id_content_page_versions",
            "content_page_versions",
            ["current_version_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_content_pages_published_by_user_id_users",
            "users",
            ["published_by_user_id"],
            ["id"],
        )

    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.add_column(sa.Column("schema_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("base_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("base_schema_hash", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_drafts_base_version_id"), ["base_version_id"])
        batch_op.create_index(batch_op.f("ix_content_drafts_schema_hash"), ["schema_hash"])
        batch_op.create_foreign_key(
            "fk_content_drafts_base_version_id_content_page_versions",
            "content_page_versions",
            ["base_version_id"],
            ["id"],
        )

    with op.batch_alter_table("content_page_versions") as batch_op:
        batch_op.add_column(sa.Column("previous_version_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_content_page_versions_previous_version_id"), ["previous_version_id"])
        batch_op.create_foreign_key(
            "fk_content_page_versions_previous_version_id_content_page_versions",
            "content_page_versions",
            ["previous_version_id"],
            ["id"],
        )

    _backfill_hashes_and_version_links()


def downgrade() -> None:
    with op.batch_alter_table("content_page_versions") as batch_op:
        batch_op.drop_constraint(
            "fk_content_page_versions_previous_version_id_content_page_versions",
            type_="foreignkey",
        )
        batch_op.drop_index(batch_op.f("ix_content_page_versions_previous_version_id"))
        batch_op.drop_column("previous_version_id")

    with op.batch_alter_table("content_drafts") as batch_op:
        batch_op.drop_constraint("fk_content_drafts_base_version_id_content_page_versions", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_content_drafts_schema_hash"))
        batch_op.drop_index(batch_op.f("ix_content_drafts_base_version_id"))
        batch_op.drop_column("base_schema_hash")
        batch_op.drop_column("base_version_id")
        batch_op.drop_column("schema_hash")

    with op.batch_alter_table("content_pages") as batch_op:
        batch_op.drop_constraint("fk_content_pages_published_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_content_pages_current_version_id_content_page_versions", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_content_pages_schema_hash"))
        batch_op.drop_index(batch_op.f("ix_content_pages_published_by_user_id"))
        batch_op.drop_index(batch_op.f("ix_content_pages_published_at"))
        batch_op.drop_index(batch_op.f("ix_content_pages_current_version_id"))
        batch_op.drop_column("published_at")
        batch_op.drop_column("published_by_user_id")
        batch_op.drop_column("current_version_id")
        batch_op.drop_column("schema_hash")


def _backfill_hashes_and_version_links() -> None:
    connection = op.get_bind()

    pages = connection.execute(sa.text("SELECT id, schema_json FROM content_pages")).mappings().all()
    for page in pages:
        schema_hash = _schema_hash(_json_payload(page["schema_json"]))
        connection.execute(
            sa.text("UPDATE content_pages SET schema_hash = :schema_hash WHERE id = :id"),
            {"schema_hash": schema_hash, "id": page["id"]},
        )

    drafts = connection.execute(sa.text("SELECT id, schema_json FROM content_drafts")).mappings().all()
    for draft in drafts:
        schema_hash = _schema_hash(_json_payload(draft["schema_json"]))
        connection.execute(
            sa.text("UPDATE content_drafts SET schema_hash = :schema_hash WHERE id = :id"),
            {"schema_hash": schema_hash, "id": draft["id"]},
        )

    versions = connection.execute(
        sa.text(
            """
            SELECT id, slug
            FROM content_page_versions
            ORDER BY slug ASC, published_at ASC, id ASC
            """
        )
    ).mappings().all()
    previous_by_slug: dict[str, int] = {}
    for version in versions:
        previous_id = previous_by_slug.get(version["slug"])
        if previous_id is not None:
            connection.execute(
                sa.text("UPDATE content_page_versions SET previous_version_id = :previous_id WHERE id = :id"),
                {"previous_id": previous_id, "id": version["id"]},
            )
        previous_by_slug[version["slug"]] = version["id"]

    version_rows = connection.execute(
        sa.text(
            """
            SELECT id, slug, schema_hash, published_by_user_id, published_at
            FROM content_page_versions
            ORDER BY slug ASC, published_at ASC, id ASC
            """
        )
    ).mappings().all()
    latest_by_slug = {version["slug"]: version for version in version_rows}
    for version in latest_by_slug.values():
        connection.execute(
            sa.text(
                """
                UPDATE content_pages
                SET current_version_id = :current_version_id,
                    schema_hash = :schema_hash,
                    published_by_user_id = :published_by_user_id,
                    published_at = :published_at
                WHERE slug = :slug
                """
            ),
            {
                "current_version_id": version["id"],
                "schema_hash": version["schema_hash"],
                "published_by_user_id": version["published_by_user_id"],
                "published_at": version["published_at"],
                "slug": version["slug"],
            },
        )


def _json_payload(value: object) -> object:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _schema_hash(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
