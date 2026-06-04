"""add notification service tables

Revision ID: 20260604_07
Revises: 20260604_06
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_07"
down_revision = "20260604_06"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("recipient_type", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", "recipient_type", "language"),
    )
    for column in ("event_key", "recipient_type", "language", "is_active"):
        op.create_index(op.f(f"ix_notification_templates_{column}"), "notification_templates", [column], unique=False)

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("recipient_type", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("throttle_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("event_key", "recipient_type", "channel", "is_enabled"):
        op.create_index(op.f(f"ix_notification_rules_{column}"), "notification_rules", [column], unique=False)

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("recipient_type", sa.String(length=50), nullable=False),
        sa.Column("recipient_id", sa.String(length=100), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("event_key", "recipient_type", "recipient_id", "channel", "status"):
        op.create_index(op.f(f"ix_notification_logs_{column}"), "notification_logs", [column], unique=False)

    op.create_table(
        "notification_deduplication",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=100), nullable=False),
        sa.Column("recipient_id", sa.String(length=100), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("event_key", "recipient_id", "dedupe_key", "sent_at"):
        op.create_index(op.f(f"ix_notification_deduplication_{column}"), "notification_deduplication", [column], unique=False)


def downgrade():
    for column in ("sent_at", "dedupe_key", "recipient_id", "event_key"):
        op.drop_index(op.f(f"ix_notification_deduplication_{column}"), table_name="notification_deduplication")
    op.drop_table("notification_deduplication")
    for column in ("status", "channel", "recipient_id", "recipient_type", "event_key"):
        op.drop_index(op.f(f"ix_notification_logs_{column}"), table_name="notification_logs")
    op.drop_table("notification_logs")
    for column in ("is_enabled", "channel", "recipient_type", "event_key"):
        op.drop_index(op.f(f"ix_notification_rules_{column}"), table_name="notification_rules")
    op.drop_table("notification_rules")
    for column in ("is_active", "language", "recipient_type", "event_key"):
        op.drop_index(op.f(f"ix_notification_templates_{column}"), table_name="notification_templates")
    op.drop_table("notification_templates")
