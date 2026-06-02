"""store created Bitrix deal ids on applications

Revision ID: 20260531_02
Revises: 20260531_01
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20260531_02"
down_revision = "20260531_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("bitrix_deal_ids_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("applications", "bitrix_deal_ids_json")
