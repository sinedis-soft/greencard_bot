"""init tables

Revision ID: 20260526_01
"""
from app.db.models import Base
from app.db.session import engine

def upgrade():
    Base.metadata.create_all(bind=engine)

def downgrade():
    Base.metadata.drop_all(bind=engine)
