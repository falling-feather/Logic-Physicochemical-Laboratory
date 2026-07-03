"""add audit log metadata

Revision ID: 20260703_0008
Revises: 20260703_0007
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260703_0008"
down_revision = "20260703_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("event_result", sa.String(length=32), nullable=True))
    op.add_column("audit_logs", sa.Column("failure_reason", sa.String(length=80), nullable=True))
    op.add_column("audit_logs", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("client_ip_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=240), nullable=True))
    op.add_column("audit_logs", sa.Column("request_method", sa.String(length=12), nullable=True))
    op.add_column("audit_logs", sa.Column("request_path", sa.String(length=240), nullable=True))
    op.create_index(op.f("ix_audit_logs_event_result"), "audit_logs", ["event_result"], unique=False)
    op.create_index(op.f("ix_audit_logs_failure_reason"), "audit_logs", ["failure_reason"], unique=False)
    op.create_index(op.f("ix_audit_logs_request_id"), "audit_logs", ["request_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_client_ip_hash"), "audit_logs", ["client_ip_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_client_ip_hash"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_request_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_failure_reason"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_event_result"), table_name="audit_logs")
    op.drop_column("audit_logs", "request_path")
    op.drop_column("audit_logs", "request_method")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "client_ip_hash")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "failure_reason")
    op.drop_column("audit_logs", "event_result")
