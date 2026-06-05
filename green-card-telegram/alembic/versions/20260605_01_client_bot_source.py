"""store source client bot on operator tickets

Revision ID: 20260605_01
Revises: 20260604_08
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa

revision = "20260605_01"
down_revision = "20260604_08"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "operator_tickets",
        sa.Column(
            "client_bot", sa.String(length=32), nullable=False, server_default="default"
        ),
    )
    op.create_index(
        op.f("ix_operator_tickets_client_bot"),
        "operator_tickets",
        ["client_bot"],
        unique=False,
    )
    op.alter_column("operator_tickets", "client_bot", server_default=None)


def downgrade():
    op.drop_index(op.f("ix_operator_tickets_client_bot"), table_name="operator_tickets")
    op.drop_column("operator_tickets", "client_bot")
