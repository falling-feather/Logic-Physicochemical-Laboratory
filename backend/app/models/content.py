from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ContentPageRecord(TimestampMixin, Base):
    __tablename__ = "content_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class ContentDraft(TimestampMixin, Base):
    __tablename__ = "content_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    target_slug: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    allow_script: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    script_review_status: Mapped[str] = mapped_column(String(32), default="not_required", index=True, nullable=False)
    script_reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    script_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    script_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

