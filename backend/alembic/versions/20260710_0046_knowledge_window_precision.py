"""preserve knowledge snapshot window microseconds on MySQL

Revision ID: 20260710_0046
Revises: 20260710_0045
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260710_0046"
down_revision = "20260710_0045"
branch_labels = None
depends_on = None


_WINDOW_TABLES = (
    "class_knowledge_snapshots",
    "user_knowledge_snapshots",
    "knowledge_snapshot_runs",
)


def upgrade() -> None:
    window_type = mysql.DATETIME(fsp=6) if op.get_bind().dialect.name == "mysql" else sa.DateTime(timezone=True)
    for table_name in _WINDOW_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "period_start",
                existing_type=sa.DateTime(timezone=True),
                type_=window_type,
                existing_nullable=False,
            )
            batch_op.alter_column(
                "period_end",
                existing_type=sa.DateTime(timezone=True),
                type_=window_type,
                existing_nullable=False,
            )

    if op.get_bind().dialect.name == "mysql":
        _repair_mysql_periodic_windows()


def downgrade() -> None:
    window_type = mysql.DATETIME(fsp=0) if op.get_bind().dialect.name == "mysql" else sa.DateTime(timezone=True)
    for table_name in reversed(_WINDOW_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "period_start",
                existing_type=sa.DateTime(timezone=True),
                type_=window_type,
                existing_nullable=False,
            )
            batch_op.alter_column(
                "period_end",
                existing_type=sa.DateTime(timezone=True),
                type_=window_type,
                existing_nullable=False,
            )


def _repair_mysql_periodic_windows() -> None:
    for table_name in _WINDOW_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET period_end = CASE "
                "WHEN granularity = 'day' THEN TIMESTAMPADD(MICROSECOND, -1, DATE_ADD(period_start, INTERVAL 1 DAY)) "
                "WHEN granularity = 'week' THEN TIMESTAMPADD(MICROSECOND, -1, DATE_ADD(period_start, INTERVAL 7 DAY)) "
                "ELSE period_end END "
                "WHERE granularity IN ('day', 'week')"
            )
        )
    op.execute(
        sa.text(
            "UPDATE knowledge_snapshot_runs SET run_key = CONCAT("
            "'knowledge:', granularity, ':', "
            "DATE_FORMAT(period_start, '%Y-%m-%dT%H:%i:%s'), ':', "
            "DATE_FORMAT(period_end, '%Y-%m-%dT%H:%i:%s.%f')"
            ") WHERE granularity IN ('day', 'week')"
        )
    )
