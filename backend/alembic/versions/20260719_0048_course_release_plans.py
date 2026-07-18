"""add stable course keys and class release plans

Revision ID: 20260719_0048
Revises: 20260716_0047
Create Date: 2026-07-19
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260719_0048"
down_revision = "20260716_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("galaxy_key", sa.String(length=32), nullable=True))
    op.add_column("courses", sa.Column("course_key", sa.String(length=96), nullable=True))
    op.add_column("course_units", sa.Column("activity_key", sa.String(length=120), nullable=True))
    op.add_column(
        "course_classes",
        sa.Column("plan_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    bind = op.get_bind()
    for course in bind.execute(sa.text("SELECT id FROM courses ORDER BY id")).mappings():
        bind.execute(
            sa.text(
                "UPDATE courses SET galaxy_key = :galaxy_key, course_key = :course_key WHERE id = :id"
            ),
            {
                "id": course["id"],
                "galaxy_key": "englab",
                "course_key": f"legacy-course-{course['id']}",
            },
        )

    for unit in bind.execute(
        sa.text("SELECT id FROM course_units ORDER BY id")
    ).mappings():
        bind.execute(
            sa.text("UPDATE course_units SET activity_key = :activity_key WHERE id = :id"),
            {"id": unit["id"], "activity_key": f"legacy-unit-{unit['id']}"},
        )
    missing_keys = bind.execute(
        sa.text(
            "SELECT "
            "(SELECT COUNT(*) FROM courses WHERE galaxy_key IS NULL OR course_key IS NULL) "
            "+ (SELECT COUNT(*) FROM course_units WHERE activity_key IS NULL)"
        )
    ).scalar_one()
    if int(missing_keys or 0) != 0:
        raise RuntimeError("0048 stable course key backfill did not complete")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.alter_column("galaxy_key", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("course_key", existing_type=sa.String(length=96), nullable=False)
        batch_op.create_unique_constraint(
            "uq_courses_school_galaxy_course_key",
            ["school_id", "galaxy_key", "course_key"],
        )
    with op.batch_alter_table("course_units") as batch_op:
        batch_op.alter_column("activity_key", existing_type=sa.String(length=120), nullable=False)
        batch_op.create_unique_constraint(
            "uq_course_units_course_activity_key",
            ["course_id", "activity_key"],
        )

    op.create_table(
        "course_unit_class_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_class_id", sa.Integer(), sa.ForeignKey("course_classes.id"), nullable=False),
        sa.Column("course_unit_id", sa.Integer(), sa.ForeignKey("course_units.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("release_mode", sa.String(length=16), nullable=False),
        sa.Column("open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prerequisite_unit_id", sa.Integer(), sa.ForeignKey("course_units.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_class_id", "course_unit_id", name="uq_course_unit_class_plans_class_unit"),
        sa.UniqueConstraint("course_class_id", "position", name="uq_course_unit_class_plans_class_position"),
        sa.CheckConstraint("position > 0", name="ck_course_unit_class_plans_position_positive"),
        sa.CheckConstraint(
            "release_mode IN ('hidden', 'locked', 'open')",
            name="ck_course_unit_class_plans_release_mode",
        ),
    )
    op.create_index(
        "ix_course_unit_class_plans_class_release_open",
        "course_unit_class_plans",
        ["course_class_id", "release_mode", "open_at"],
    )
    op.create_index(
        "ix_course_unit_class_plans_course_class_id",
        "course_unit_class_plans",
        ["course_class_id"],
    )
    op.create_index(
        "ix_course_unit_class_plans_course_unit_id",
        "course_unit_class_plans",
        ["course_unit_id"],
    )
    op.create_index(
        "ix_course_unit_class_plans_prerequisite_unit_id",
        "course_unit_class_plans",
        ["prerequisite_unit_id"],
    )

    now = datetime.now(UTC)
    plan_table = sa.table(
        "course_unit_class_plans",
        sa.column("course_class_id", sa.Integer()),
        sa.column("course_unit_id", sa.Integer()),
        sa.column("position", sa.Integer()),
        sa.column("release_mode", sa.String()),
        sa.column("open_at", sa.DateTime(timezone=True)),
        sa.column("prerequisite_unit_id", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    class_rows = bind.execute(sa.text("SELECT id, course_id FROM course_classes ORDER BY id")).mappings()
    for course_class in class_rows:
        insert_rows: list[dict] = []
        units = bind.execute(
            sa.text("SELECT id, position FROM course_units WHERE course_id = :course_id ORDER BY position, id"),
            {"course_id": course_class["course_id"]},
        ).mappings()
        for unit in units:
            insert_rows.append(
                {
                    "course_class_id": course_class["id"],
                    "course_unit_id": unit["id"],
                    "position": unit["position"],
                    "release_mode": "open",
                    "open_at": None,
                    "prerequisite_unit_id": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        for index in range(0, len(insert_rows), 1000):
            op.bulk_insert(plan_table, insert_rows[index : index + 1000])
    expected_plan_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM course_classes cc "
            "JOIN course_units cu ON cu.course_id = cc.course_id"
        )
    ).scalar_one()
    actual_plan_count = bind.execute(sa.text("SELECT COUNT(*) FROM course_unit_class_plans")).scalar_one()
    if int(actual_plan_count) != int(expected_plan_count):
        raise RuntimeError("0048 default open course release plan backfill did not complete")


def downgrade() -> None:
    op.drop_index("ix_course_unit_class_plans_prerequisite_unit_id", table_name="course_unit_class_plans")
    op.drop_index("ix_course_unit_class_plans_course_unit_id", table_name="course_unit_class_plans")
    op.drop_index("ix_course_unit_class_plans_course_class_id", table_name="course_unit_class_plans")
    op.drop_index("ix_course_unit_class_plans_class_release_open", table_name="course_unit_class_plans")
    op.drop_table("course_unit_class_plans")
    with op.batch_alter_table("course_units") as batch_op:
        batch_op.drop_constraint("uq_course_units_course_activity_key", type_="unique")
        batch_op.drop_column("activity_key")
    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_constraint("uq_courses_school_galaxy_course_key", type_="unique")
        batch_op.drop_column("course_key")
        batch_op.drop_column("galaxy_key")
    with op.batch_alter_table("course_classes") as batch_op:
        batch_op.drop_column("plan_version")
