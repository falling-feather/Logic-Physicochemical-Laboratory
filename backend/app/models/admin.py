from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BugRecord(TimestampMixin, Base):
    __tablename__ = "bug_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="general", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="P2", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
