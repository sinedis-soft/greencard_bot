"""add repeat application drafts

Revision ID: 20260604_02
Revises: 20260604_01
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_02"
down_revision = "20260604_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "repeat_application_drafts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("old_bitrix_deal_id", sa.BigInteger(), nullable=False),
        sa.Column("new_start_date", sa.String(length=32), nullable=True),
        sa.Column("new_period_days", sa.Integer(), nullable=True),
        sa.Column("docs_mode", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repeat_application_drafts_telegram_user_id"), "repeat_application_drafts", ["telegram_user_id"], unique=False)
    op.create_index(op.f("ix_repeat_application_drafts_old_bitrix_deal_id"), "repeat_application_drafts", ["old_bitrix_deal_id"], unique=False)
    op.create_index(op.f("ix_repeat_application_drafts_status"), "repeat_application_drafts", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_repeat_application_drafts_status"), table_name="repeat_application_drafts")
    op.drop_index(op.f("ix_repeat_application_drafts_old_bitrix_deal_id"), table_name="repeat_application_drafts")
    op.drop_index(op.f("ix_repeat_application_drafts_telegram_user_id"), table_name="repeat_application_drafts")
    op.drop_table("repeat_application_drafts")
