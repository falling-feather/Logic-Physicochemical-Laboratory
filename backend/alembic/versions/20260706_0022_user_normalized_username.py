"""add normalized username guard

Revision ID: 20260706_0022
Revises: 20260706_0021
Create Date: 2026-07-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260706_0022"
down_revision = "20260706_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    _raise_for_duplicate_users(connection)
    _raise_for_blank_users(connection)
    _clear_invalid_login_attempts(connection)

    op.add_column("users", sa.Column("normalized_username", sa.String(length=64), nullable=True))
    op.add_column("login_attempts", sa.Column("normalized_username", sa.String(length=64), nullable=True))
    op.execute(sa.text("UPDATE users SET normalized_username = lower(trim(username))"))
    op.execute(sa.text("UPDATE login_attempts SET normalized_username = lower(trim(username))"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "normalized_username",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint("uq_users_normalized_username", ["normalized_username"])

    with op.batch_alter_table("login_attempts") as batch_op:
        batch_op.alter_column(
            "normalized_username",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint("uq_login_attempts_normalized_username", ["normalized_username"])


def downgrade() -> None:
    with op.batch_alter_table("login_attempts") as batch_op:
        batch_op.drop_constraint("uq_login_attempts_normalized_username", type_="unique")
        batch_op.drop_column("normalized_username")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_normalized_username", type_="unique")
        batch_op.drop_column("normalized_username")


def _raise_for_duplicate_users(connection) -> None:
    duplicates = connection.execute(
        sa.text(
            """
            SELECT lower(trim(username)) AS normalized_username
            FROM users
            GROUP BY lower(trim(username))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if duplicates:
        sample = ", ".join(str(row[0]) for row in duplicates[:5])
        raise RuntimeError(f"Duplicate normalized usernames prevent migration: {sample}")


def _raise_for_blank_users(connection) -> None:
    blanks = connection.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE username IS NULL OR lower(trim(username)) = ''")
    ).scalar_one()
    if int(blanks) > 0:
        raise RuntimeError("Blank normalized usernames prevent migration")


def _clear_invalid_login_attempts(connection) -> None:
    connection.execute(
        sa.text("DELETE FROM login_attempts WHERE username IS NULL OR lower(trim(username)) = ''")
    )
    duplicates = connection.execute(
        sa.text(
            """
            SELECT lower(trim(username)) AS normalized_username
            FROM login_attempts
            GROUP BY lower(trim(username))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for row in duplicates:
        connection.execute(
            sa.text("DELETE FROM login_attempts WHERE lower(trim(username)) = :normalized_username"),
            {"normalized_username": row[0]},
        )
