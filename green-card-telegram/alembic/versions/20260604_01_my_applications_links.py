"""add my applications link tables

Revision ID: 20260604_01
Revises: 20260531_02
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_01"
down_revision = "20260531_02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telegram_bitrix_links",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("bitrix_contact_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_telegram_bitrix_links_telegram_user_id"), "telegram_bitrix_links", ["telegram_user_id"], unique=False)
    op.create_table(
        "client_action_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("bitrix_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_action_logs_telegram_user_id"), "client_action_logs", ["telegram_user_id"], unique=False)
    op.create_index(op.f("ix_client_action_logs_bitrix_deal_id"), "client_action_logs", ["bitrix_deal_id"], unique=False)
    op.add_column("operator_tickets", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("operator_tickets", sa.Column("bitrix_deal_id", sa.BigInteger(), nullable=True))
    op.add_column("operator_tickets", sa.Column("reason", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_operator_tickets_bitrix_deal_id"), "operator_tickets", ["bitrix_deal_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_operator_tickets_bitrix_deal_id"), table_name="operator_tickets")
    op.drop_column("operator_tickets", "reason")
    op.drop_column("operator_tickets", "bitrix_deal_id")
    op.drop_column("operator_tickets", "telegram_chat_id")
    op.drop_index(op.f("ix_client_action_logs_bitrix_deal_id"), table_name="client_action_logs")
    op.drop_index(op.f("ix_client_action_logs_telegram_user_id"), table_name="client_action_logs")
    op.drop_table("client_action_logs")
    op.drop_index(op.f("ix_telegram_bitrix_links_telegram_user_id"), table_name="telegram_bitrix_links")
    op.drop_table("telegram_bitrix_links")
