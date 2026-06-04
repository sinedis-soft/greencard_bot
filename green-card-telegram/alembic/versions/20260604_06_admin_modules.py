"""add admin operators tariffs and content texts

Revision ID: 20260604_06
Revises: 20260604_05
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_06"
down_revision = "20260604_05"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operators",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("languages_json", sa.Text(), nullable=False),
        sa.Column("max_active_tickets", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index(op.f("ix_operators_telegram_user_id"), "operators", ["telegram_user_id"], unique=False)
    op.create_index(op.f("ix_operators_role"), "operators", ["role"], unique=False)
    op.create_index(op.f("ix_operators_is_active"), "operators", ["is_active"], unique=False)

    op.create_table(
        "tariffs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_type", sa.String(length=50), nullable=False),
        sa.Column("vehicle_type", sa.String(length=50), nullable=False),
        sa.Column("insurance_period_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("product_type", "vehicle_type", "insurance_period_days", "valid_from", "valid_to", "is_active"):
        op.create_index(op.f(f"ix_tariffs_{column}"), "tariffs", [column], unique=False)

    op.create_table(
        "tariff_change_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tariff_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("old_value_json", sa.Text(), nullable=True),
        sa.Column("new_value_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tariff_change_logs_tariff_id"), "tariff_change_logs", ["tariff_id"], unique=False)

    op.create_table(
        "content_texts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("key", "language", "category", "is_active"):
        op.create_index(op.f(f"ix_content_texts_{column}"), "content_texts", [column], unique=False)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_admin_users_email"), "admin_users", ["email"], unique=False)
    op.create_index(op.f("ix_admin_users_is_active"), "admin_users", ["is_active"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_admin_users_is_active"), table_name="admin_users")
    op.drop_index(op.f("ix_admin_users_email"), table_name="admin_users")
    op.drop_table("admin_users")
    for column in ("is_active", "category", "language", "key"):
        op.drop_index(op.f(f"ix_content_texts_{column}"), table_name="content_texts")
    op.drop_table("content_texts")
    op.drop_index(op.f("ix_tariff_change_logs_tariff_id"), table_name="tariff_change_logs")
    op.drop_table("tariff_change_logs")
    for column in ("is_active", "valid_to", "valid_from", "insurance_period_days", "vehicle_type", "product_type"):
        op.drop_index(op.f(f"ix_tariffs_{column}"), table_name="tariffs")
    op.drop_table("tariffs")
    op.drop_index(op.f("ix_operators_is_active"), table_name="operators")
    op.drop_index(op.f("ix_operators_role"), table_name="operators")
    op.drop_index(op.f("ix_operators_telegram_user_id"), table_name="operators")
    op.drop_table("operators")
