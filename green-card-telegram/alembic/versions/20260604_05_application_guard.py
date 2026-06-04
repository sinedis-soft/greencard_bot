"""add application guard privacy and compliance tables

Revision ID: 20260604_05
Revises: 20260604_04
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_05"
down_revision = "20260604_04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "application_duplicate_index",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("phone_hash", sa.String(length=128), nullable=True),
        sa.Column("email_hash", sa.String(length=128), nullable=True),
        sa.Column("plate_hash", sa.String(length=128), nullable=True),
        sa.Column("vin_hash", sa.String(length=128), nullable=True),
        sa.Column("bitrix_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("application_id", "telegram_user_id", "phone_hash", "email_hash", "plate_hash", "vin_hash", "bitrix_deal_id", "status", "expires_at"):
        op.create_index(op.f(f"ix_application_duplicate_index_{column}"), "application_duplicate_index", [column], unique=False)

    op.create_table(
        "consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("consent_type", sa.String(length=100), nullable=False),
        sa.Column("consent_version", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("consent_text_hash", sa.String(length=128), nullable=False),
        sa.Column("consent_text_snapshot", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("application_id", "telegram_user_id", "consent_type"):
        op.create_index(op.f(f"ix_consents_{column}"), "consents", [column], unique=False)

    op.create_table(
        "data_deletion_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=50), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("bitrix_contact_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("decision", sa.String(length=50), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    for column in ("request_id", "telegram_user_id", "bitrix_contact_id", "status"):
        op.create_index(op.f(f"ix_data_deletion_requests_{column}"), "data_deletion_requests", [column], unique=False)

    op.create_table(
        "blocked_telegram_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
        sa.Column("blocked_by_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_blocked_telegram_users_telegram_user_id"), "blocked_telegram_users", ["telegram_user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_blocked_telegram_users_telegram_user_id"), table_name="blocked_telegram_users")
    op.drop_table("blocked_telegram_users")
    for column in ("status", "bitrix_contact_id", "telegram_user_id", "request_id"):
        op.drop_index(op.f(f"ix_data_deletion_requests_{column}"), table_name="data_deletion_requests")
    op.drop_table("data_deletion_requests")
    for column in ("consent_type", "telegram_user_id", "application_id"):
        op.drop_index(op.f(f"ix_consents_{column}"), table_name="consents")
    op.drop_table("consents")
    for column in ("expires_at", "status", "bitrix_deal_id", "vin_hash", "plate_hash", "email_hash", "phone_hash", "telegram_user_id", "application_id"):
        op.drop_index(op.f(f"ix_application_duplicate_index_{column}"), table_name="application_duplicate_index")
    op.drop_table("application_duplicate_index")
