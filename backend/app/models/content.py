from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ContentPageRecord(TimestampMixin, Base):
    __tablename__ = "content_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "content_page_versions.id",
            name="fk_content_pages_current_version_id_content_page_versions",
            use_alter=True,
        ),
        index=True,
        nullable=True,
    )
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)


class ContentDraft(TimestampMixin, Base):
    __tablename__ = "content_drafts"
    __table_args__ = (
        UniqueConstraint(
            "author_user_id",
            "target_slug",
            "active_key",
            name="uq_content_drafts_active_author_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    target_slug: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True, nullable=False)
    active_key: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    base_version_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "content_page_versions.id",
            name="fk_content_drafts_base_version_id_content_page_versions",
            use_alter=True,
        ),
        index=True,
        nullable=True,
    )
    base_schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allow_script: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    script_risk_level: Mapped[str | None] = mapped_column(String(32), default="none", index=True, nullable=True)
    script_analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script_review_status: Mapped[str] = mapped_column(String(32), default="not_required", index=True, nullable=False)
    script_reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    script_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    script_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    change_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_page_id: Mapped[int | None] = mapped_column(ForeignKey("content_pages.id"), index=True, nullable=True)
    published_version_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "content_page_versions.id",
            name="fk_content_drafts_published_version_id_content_page_versions",
            use_alter=True,
        ),
        index=True,
        nullable=True,
    )
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentPageVersion(TimestampMixin, Base):
    __tablename__ = "content_page_versions"
    __table_args__ = (UniqueConstraint("slug", "version", name="uq_content_page_versions_slug_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("content_pages.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_draft_id: Mapped[int | None] = mapped_column(ForeignKey("content_drafts.id"), index=True, nullable=True)
    restored_from_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_page_versions.id"),
        index=True,
        nullable=True,
    )
    previous_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_page_versions.id"),
        index=True,
        nullable=True,
    )
    published_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

