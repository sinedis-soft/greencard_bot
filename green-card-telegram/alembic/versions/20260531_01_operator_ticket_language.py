"""add preferred language to operator tickets

Revision ID: 20260531_01
Revises: 20260528_01
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20260531_01"
down_revision = "20260528_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("operator_tickets", sa.Column("preferred_language", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("operator_tickets", "preferred_language")
