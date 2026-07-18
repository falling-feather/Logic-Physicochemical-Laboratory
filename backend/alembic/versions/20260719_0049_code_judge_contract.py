"""add vendor-neutral code judge persistence contract

Revision ID: 20260719_0049
Revises: 20260719_0048
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_0049"
down_revision = "20260719_0048"
branch_labels = None
depends_on = None


_SUBMISSION_STATES = (
    "'queued', 'runner_unavailable', 'running', 'accepted', 'wrong_answer', 'partial', "
    "'compile_error', 'runtime_error', 'time_limit', 'memory_limit', 'output_limit', "
    "'internal_error', 'cancelled'"
)


def upgrade() -> None:
    op.create_table(
        "code_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("course_unit_id", sa.Integer(), sa.ForeignKey("course_units.id"), nullable=False),
        sa.Column("activity_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_id", "course_unit_id", name="uq_code_problems_course_unit"),
        sa.UniqueConstraint("course_id", "activity_key", name="uq_code_problems_course_activity_key"),
    )
    op.create_index("ix_code_problems_school_id", "code_problems", ["school_id"])
    op.create_index("ix_code_problems_course_id", "code_problems", ["course_id"])
    op.create_index("ix_code_problems_course_unit_id", "code_problems", ["course_unit_id"])
    op.create_index("ix_code_problems_created_by_user_id", "code_problems", ["created_by_user_id"])
    op.create_index(
        "ix_code_problems_course_activity_status",
        "code_problems",
        ["course_id", "activity_key", "status"],
    )

    op.create_table(
        "code_problem_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("code_problems.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("statement_markdown", sa.Text(), nullable=False),
        sa.Column("test_spec_json", sa.JSON(), nullable=False),
        sa.Column("language_allowlist_json", sa.JSON(), nullable=False),
        sa.Column("resource_policy_json", sa.JSON(), nullable=False),
        sa.Column("source_max_bytes", sa.Integer(), nullable=False),
        sa.Column("input_max_bytes", sa.Integer(), nullable=False),
        sa.Column("output_max_bytes", sa.Integer(), nullable=False),
        sa.Column("spec_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("problem_id", "version_number", name="uq_code_problem_versions_problem_number"),
        sa.CheckConstraint("version_number > 0", name="ck_code_problem_versions_number_positive"),
        sa.CheckConstraint("source_max_bytes > 0", name="ck_code_problem_versions_source_limit_positive"),
        sa.CheckConstraint("input_max_bytes >= 0", name="ck_code_problem_versions_input_limit_nonnegative"),
        sa.CheckConstraint("output_max_bytes > 0", name="ck_code_problem_versions_output_limit_positive"),
    )
    op.create_index("ix_code_problem_versions_problem_id", "code_problem_versions", ["problem_id"])
    op.create_index("ix_code_problem_versions_created_by_user_id", "code_problem_versions", ["created_by_user_id"])
    op.create_index(
        "ix_code_problem_versions_problem_status_number",
        "code_problem_versions",
        ["problem_id", "status", "version_number"],
    )

    op.create_table(
        "code_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("class_groups.id"), nullable=False),
        sa.Column("course_unit_id", sa.Integer(), sa.ForeignKey("course_units.id"), nullable=False),
        sa.Column("activity_key", sa.String(length=120), nullable=False),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("code_problems.id"), nullable=False),
        sa.Column("problem_version_id", sa.Integer(), sa.ForeignKey("code_problem_versions.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("language", sa.String(length=24), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("stdin", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("problem_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("resource_policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_summary_json", sa.JSON(), nullable=False),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "student_id",
            "problem_version_id",
            "class_id",
            name="uq_code_submissions_student_version_class",
        ),
        sa.CheckConstraint(f"status IN ({_SUBMISSION_STATES})", name="ck_code_submissions_status"),
    )
    for column in (
        "school_id",
        "course_id",
        "class_id",
        "course_unit_id",
        "problem_id",
        "problem_version_id",
        "student_id",
    ):
        op.create_index(f"ix_code_submissions_{column}", "code_submissions", [column])
    op.create_index(
        "ix_code_submissions_class_course_activity_created",
        "code_submissions",
        ["class_id", "course_id", "activity_key", "created_at", "id"],
    )
    op.create_index("ix_code_submissions_student_created", "code_submissions", ["student_id", "created_at", "id"])
    op.create_index("ix_code_submissions_status_created", "code_submissions", ["status", "created_at", "id"])

    op.create_table(
        "code_judge_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("code_submissions.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("adapter_name", sa.String(length=80), nullable=False),
        sa.Column("resource_policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("result_summary_json", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_owner", sa.String(length=160), nullable=True),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_id", "attempt_number", name="uq_code_judge_attempts_submission_number"),
        sa.CheckConstraint(f"status IN ({_SUBMISSION_STATES})", name="ck_code_judge_attempts_status"),
        sa.CheckConstraint("attempt_number > 0", name="ck_code_judge_attempts_number_positive"),
    )
    op.create_index("ix_code_judge_attempts_submission_id", "code_judge_attempts", ["submission_id"])
    op.create_index("ix_code_judge_attempts_claim", "code_judge_attempts", ["status", "available_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_code_judge_attempts_claim", table_name="code_judge_attempts")
    op.drop_index("ix_code_judge_attempts_submission_id", table_name="code_judge_attempts")
    op.drop_table("code_judge_attempts")
    op.drop_index("ix_code_submissions_status_created", table_name="code_submissions")
    op.drop_index("ix_code_submissions_student_created", table_name="code_submissions")
    op.drop_index("ix_code_submissions_class_course_activity_created", table_name="code_submissions")
    for column in (
        "student_id",
        "problem_version_id",
        "problem_id",
        "course_unit_id",
        "class_id",
        "course_id",
        "school_id",
    ):
        op.drop_index(f"ix_code_submissions_{column}", table_name="code_submissions")
    op.drop_table("code_submissions")
    op.drop_index("ix_code_problem_versions_problem_status_number", table_name="code_problem_versions")
    op.drop_index("ix_code_problem_versions_created_by_user_id", table_name="code_problem_versions")
    op.drop_index("ix_code_problem_versions_problem_id", table_name="code_problem_versions")
    op.drop_table("code_problem_versions")
    op.drop_index("ix_code_problems_course_activity_status", table_name="code_problems")
    op.drop_index("ix_code_problems_created_by_user_id", table_name="code_problems")
    op.drop_index("ix_code_problems_course_unit_id", table_name="code_problems")
    op.drop_index("ix_code_problems_course_id", table_name="code_problems")
    op.drop_index("ix_code_problems_school_id", table_name="code_problems")
    op.drop_table("code_problems")
