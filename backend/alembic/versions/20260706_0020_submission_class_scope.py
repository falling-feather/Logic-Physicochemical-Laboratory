"""scope submission uniqueness by class

Revision ID: 20260706_0020
Revises: 20260706_0019
Create Date: 2026-07-06
"""

from alembic import op


revision = "20260706_0020"
down_revision = "20260706_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_constraint("uq_submissions_assignment_student", type_="unique")
        batch_op.create_unique_constraint(
            "uq_submissions_assignment_student_class",
            ["assignment_id", "student_id", "class_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_constraint("uq_submissions_assignment_student_class", type_="unique")
        batch_op.create_unique_constraint(
            "uq_submissions_assignment_student",
            ["assignment_id", "student_id"],
        )
