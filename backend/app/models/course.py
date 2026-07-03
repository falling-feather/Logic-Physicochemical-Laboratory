from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utc_now


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("school_id", "title", name="uq_courses_school_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True, nullable=False)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)


class CourseClass(TimestampMixin, Base):
    __tablename__ = "course_classes"
    __table_args__ = (UniqueConstraint("course_id", "class_id", name="uq_course_classes_course_class"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class CourseUnit(TimestampMixin, Base):
    __tablename__ = "course_units"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_course_units_course_position"),
        UniqueConstraint("course_id", "content_slug", name="uq_course_units_course_content_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content_slug: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="published", nullable=False)


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("unit_id", "title", name="uq_assignments_unit_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("course_units.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_submissions_assignment_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    graded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PointLedger(TimestampMixin, Base):
    __tablename__ = "point_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True, nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), index=True, nullable=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("submissions.id"), index=True, nullable=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class LearningEvent(TimestampMixin, Base):
    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), index=True, nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), index=True, nullable=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("course_units.id"), index=True, nullable=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ClassKnowledgeSnapshot(TimestampMixin, Base):
    __tablename__ = "class_knowledge_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "course_scope_id",
            "granularity",
            "period_start",
            "period_end",
            "rule_version",
            name="uq_class_knowledge_snapshot_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True, nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("class_groups.id"), index=True, nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), index=True, nullable=True)
    course_scope_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), default="custom", index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    students_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    students_active: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assignment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_submissions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_assignments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    graded_assignments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    complete_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_score_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_score_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_points_per_student: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    knowledge_stats_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
