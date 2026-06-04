"""add reminder tasks and safe draft leads

Revision ID: 20260604_08
Revises: 20260604_07
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_08"
down_revision = "20260604_07"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reminder_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("reminder_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("bitrix_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("telegram_user_id", "telegram_chat_id", "reminder_type", "status", "bitrix_deal_id", "request_id", "dedupe_key", "scheduled_at"):
        op.create_index(op.f(f"ix_reminder_tasks_{column}"), "reminder_tasks", [column], unique=False)

    op.create_table(
        "calculator_leads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("product_type", sa.String(length=50), nullable=False),
        sa.Column("vehicle_type", sa.String(length=50), nullable=True),
        sa.Column("insurance_period_days", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("estimated_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("converted_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("telegram_user_id", "telegram_chat_id", "product_type", "vehicle_type", "status"):
        op.create_index(op.f(f"ix_calculator_leads_{column}"), "calculator_leads", [column], unique=False)

    op.create_table(
        "application_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("draft_id", sa.String(length=100), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("product_type", sa.String(length=50), nullable=False),
        sa.Column("source_channel", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("safe_context_json", sa.Text(), nullable=True),
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id"),
    )
    for column in ("draft_id", "telegram_user_id", "telegram_chat_id", "product_type", "status", "expires_at"):
        op.create_index(op.f(f"ix_application_drafts_{column}"), "application_drafts", [column], unique=False)

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("allow_service_notifications", sa.Boolean(), nullable=False),
        sa.Column("allow_marketing_notifications", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_notification_preferences_telegram_user_id"), "notification_preferences", ["telegram_user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_notification_preferences_telegram_user_id"), table_name="notification_preferences")
    op.drop_table("notification_preferences")
    for column in ("expires_at", "status", "product_type", "telegram_chat_id", "telegram_user_id", "draft_id"):
        op.drop_index(op.f(f"ix_application_drafts_{column}"), table_name="application_drafts")
    op.drop_table("application_drafts")
    for column in ("status", "vehicle_type", "product_type", "telegram_chat_id", "telegram_user_id"):
        op.drop_index(op.f(f"ix_calculator_leads_{column}"), table_name="calculator_leads")
    op.drop_table("calculator_leads")
    for column in ("scheduled_at", "dedupe_key", "request_id", "bitrix_deal_id", "status", "reminder_type", "telegram_chat_id", "telegram_user_id"):
        op.drop_index(op.f(f"ix_reminder_tasks_{column}"), table_name="reminder_tasks")
    op.drop_table("reminder_tasks")
