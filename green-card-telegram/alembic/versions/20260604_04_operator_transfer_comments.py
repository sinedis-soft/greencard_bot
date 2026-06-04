"""add operator ticket transfers and internal comments

Revision ID: 20260604_04
Revises: 20260604_03
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_04"
down_revision = "20260604_03"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("operator_tickets", sa.Column("assigned_at", sa.DateTime(), nullable=True))
    op.add_column("operator_tickets", sa.Column("assigned_by_operator_id", sa.BigInteger(), nullable=True))
    op.add_column("operator_tickets", sa.Column("previous_operator_id", sa.BigInteger(), nullable=True))
    op.add_column("operator_tickets", sa.Column("transfer_reason", sa.Text(), nullable=True))
    op.add_column("operator_tickets", sa.Column("transferred_at", sa.DateTime(), nullable=True))
    op.create_table(
        "operator_ticket_transfers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("from_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("to_operator_id", sa.BigInteger(), nullable=True),
        sa.Column("transferred_by_operator_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operator_ticket_transfers_ticket_id"), "operator_ticket_transfers", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_operator_ticket_transfers_transferred_by_operator_id"), "operator_ticket_transfers", ["transferred_by_operator_id"], unique=False)
    op.create_table(
        "operator_internal_comments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("bitrix_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("comment_type", sa.String(length=32), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operator_internal_comments_ticket_id"), "operator_internal_comments", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_operator_internal_comments_bitrix_deal_id"), "operator_internal_comments", ["bitrix_deal_id"], unique=False)
    op.create_index(op.f("ix_operator_internal_comments_operator_id"), "operator_internal_comments", ["operator_id"], unique=False)
    op.create_index(op.f("ix_operator_internal_comments_comment_type"), "operator_internal_comments", ["comment_type"], unique=False)
    op.create_index(op.f("ix_operator_internal_comments_is_pinned"), "operator_internal_comments", ["is_pinned"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_operator_internal_comments_is_pinned"), table_name="operator_internal_comments")
    op.drop_index(op.f("ix_operator_internal_comments_comment_type"), table_name="operator_internal_comments")
    op.drop_index(op.f("ix_operator_internal_comments_operator_id"), table_name="operator_internal_comments")
    op.drop_index(op.f("ix_operator_internal_comments_bitrix_deal_id"), table_name="operator_internal_comments")
    op.drop_index(op.f("ix_operator_internal_comments_ticket_id"), table_name="operator_internal_comments")
    op.drop_table("operator_internal_comments")
    op.drop_index(op.f("ix_operator_ticket_transfers_transferred_by_operator_id"), table_name="operator_ticket_transfers")
    op.drop_index(op.f("ix_operator_ticket_transfers_ticket_id"), table_name="operator_ticket_transfers")
    op.drop_table("operator_ticket_transfers")
    op.drop_column("operator_tickets", "transferred_at")
    op.drop_column("operator_tickets", "transfer_reason")
    op.drop_column("operator_tickets", "previous_operator_id")
    op.drop_column("operator_tickets", "assigned_by_operator_id")
    op.drop_column("operator_tickets", "assigned_at")
