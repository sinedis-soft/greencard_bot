"""use bigint for telegram/operator ids

Revision ID: 20260528_01
Revises: 20260526_01
Create Date: 2026-05-28
"""

from alembic import op

revision = "20260528_01"
down_revision = "20260526_01"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE applications ALTER COLUMN telegram_user_id TYPE BIGINT")
    op.execute("ALTER TABLE operator_tickets ALTER COLUMN telegram_user_id TYPE BIGINT")
    op.execute("ALTER TABLE operator_tickets ALTER COLUMN operator_id TYPE BIGINT")
    op.execute("ALTER TABLE operator_action_logs ALTER COLUMN operator_id TYPE BIGINT")
    op.execute("ALTER TABLE analytics_events ALTER COLUMN telegram_user_id TYPE BIGINT")


def downgrade():
    op.execute("ALTER TABLE analytics_events ALTER COLUMN telegram_user_id TYPE INTEGER")
    op.execute("ALTER TABLE operator_action_logs ALTER COLUMN operator_id TYPE INTEGER")
    op.execute("ALTER TABLE operator_tickets ALTER COLUMN operator_id TYPE INTEGER")
    op.execute("ALTER TABLE operator_tickets ALTER COLUMN telegram_user_id TYPE INTEGER")
    op.execute("ALTER TABLE applications ALTER COLUMN telegram_user_id TYPE INTEGER")
