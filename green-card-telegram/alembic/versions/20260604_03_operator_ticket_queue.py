"""expand operator tickets for queue workflow

Revision ID: 20260604_03
Revises: 20260604_02
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_03"
down_revision = "20260604_02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("operator_tickets", sa.Column("bitrix_contact_id", sa.BigInteger(), nullable=True))
    op.add_column("operator_tickets", sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"))
    op.add_column("operator_tickets", sa.Column("taken_at", sa.DateTime(), nullable=True))
    op.add_column("operator_tickets", sa.Column("close_reason", sa.String(length=100), nullable=True))
    op.add_column("operator_tickets", sa.Column("sla_due_at", sa.DateTime(), nullable=True))
    op.add_column("operator_tickets", sa.Column("last_message_preview", sa.Text(), nullable=True))
    op.add_column("operator_tickets", sa.Column("internal_note", sa.Text(), nullable=True))
    op.add_column("operator_action_logs", sa.Column("details_json", sa.Text(), nullable=True))
    op.create_index(op.f("ix_operator_tickets_bitrix_contact_id"), "operator_tickets", ["bitrix_contact_id"], unique=False)
    op.create_index(op.f("ix_operator_tickets_reason"), "operator_tickets", ["reason"], unique=False)
    op.create_index(op.f("ix_operator_tickets_status"), "operator_tickets", ["status"], unique=False)
    op.create_index(op.f("ix_operator_tickets_priority"), "operator_tickets", ["priority"], unique=False)
    op.create_index(op.f("ix_operator_tickets_operator_id"), "operator_tickets", ["operator_id"], unique=False)
    op.create_index(op.f("ix_operator_tickets_sla_due_at"), "operator_tickets", ["sla_due_at"], unique=False)
    op.create_index(op.f("ix_operator_tickets_sla_breach"), "operator_tickets", ["sla_breach"], unique=False)
    op.alter_column("operator_tickets", "priority", server_default=None)


def downgrade():
    op.drop_index(op.f("ix_operator_tickets_sla_breach"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_sla_due_at"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_operator_id"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_priority"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_status"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_reason"), table_name="operator_tickets")
    op.drop_index(op.f("ix_operator_tickets_bitrix_contact_id"), table_name="operator_tickets")
    op.drop_column("operator_action_logs", "details_json")
    op.drop_column("operator_tickets", "internal_note")
    op.drop_column("operator_tickets", "last_message_preview")
    op.drop_column("operator_tickets", "sla_due_at")
    op.drop_column("operator_tickets", "close_reason")
    op.drop_column("operator_tickets", "taken_at")
    op.drop_column("operator_tickets", "priority")
    op.drop_column("operator_tickets", "bitrix_contact_id")
