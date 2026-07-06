"""add courses assignments and learning events

Revision ID: 20260703_0003
Revises: 20260703_0002
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0003"
down_revision = "20260703_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("creator_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "title", name="uq_courses_school_title"),
    )
    op.create_index(op.f("ix_courses_creator_user_id"), "courses", ["creator_user_id"], unique=False)
    op.create_index(op.f("ix_courses_id"), "courses", ["id"], unique=False)
    op.create_index(op.f("ix_courses_school_id"), "courses", ["school_id"], unique=False)

    op.create_table(
        "course_classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "class_id", name="uq_course_classes_course_class"),
    )
    op.create_index(op.f("ix_course_classes_class_id"), "course_classes", ["class_id"], unique=False)
    op.create_index(op.f("ix_course_classes_course_id"), "course_classes", ["course_id"], unique=False)
    op.create_index(op.f("ix_course_classes_id"), "course_classes", ["id"], unique=False)

    op.create_table(
        "course_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_slug", sa.String(length=180), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "content_slug", name="uq_course_units_course_content_slug"),
        sa.UniqueConstraint("course_id", "position", name="uq_course_units_course_position"),
    )
    op.create_index(op.f("ix_course_units_course_id"), "course_units", ["course_id"], unique=False)
    op.create_index(op.f("ix_course_units_id"), "course_units", ["id"], unique=False)

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["course_units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", "title", name="uq_assignments_unit_title"),
    )
    op.create_index(op.f("ix_assignments_id"), "assignments", ["id"], unique=False)
    op.create_index(op.f("ix_assignments_unit_id"), "assignments", ["unit_id"], unique=False)

    op.create_table(
        "learning_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class_groups.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["course_units.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_events_assignment_id"), "learning_events", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_learning_events_class_id"), "learning_events", ["class_id"], unique=False)
    op.create_index(op.f("ix_learning_events_course_id"), "learning_events", ["course_id"], unique=False)
    op.create_index(op.f("ix_learning_events_event_type"), "learning_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_learning_events_id"), "learning_events", ["id"], unique=False)
    op.create_index(op.f("ix_learning_events_school_id"), "learning_events", ["school_id"], unique=False)
    op.create_index(op.f("ix_learning_events_unit_id"), "learning_events", ["unit_id"], unique=False)
    op.create_index(op.f("ix_learning_events_user_id"), "learning_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_events_user_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_unit_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_school_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_event_type"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_course_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_class_id"), table_name="learning_events")
    op.drop_index(op.f("ix_learning_events_assignment_id"), table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_index(op.f("ix_assignments_unit_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_id"), table_name="assignments")
    op.drop_table("assignments")
    op.drop_index(op.f("ix_course_units_id"), table_name="course_units")
    op.drop_index(op.f("ix_course_units_course_id"), table_name="course_units")
    op.drop_table("course_units")
    op.drop_index(op.f("ix_course_classes_id"), table_name="course_classes")
    op.drop_index(op.f("ix_course_classes_course_id"), table_name="course_classes")
    op.drop_index(op.f("ix_course_classes_class_id"), table_name="course_classes")
    op.drop_table("course_classes")
    op.drop_index(op.f("ix_courses_school_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_creator_user_id"), table_name="courses")
    op.drop_table("courses")
