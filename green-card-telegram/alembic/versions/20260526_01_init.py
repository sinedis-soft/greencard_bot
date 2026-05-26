"""init tables

Revision ID: 20260526_01
Revises:
Create Date: 2026-05-26
"""

from app.db.models import Base
from app.db.session import engine

revision = "20260526_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=engine)


def downgrade():
    Base.metadata.drop_all(bind=engine)