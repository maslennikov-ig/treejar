"""add_escalation_status

Revision ID: 0004_add_escalation_status
Revises: 0003_add_wazzup_message_id_index
Create Date: 2026-03-02 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_add_escalation_status"
down_revision: str | None = "0003_add_wazzup_message_id_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("conversations", sa.Column("escalation_status", sa.String(), server_default="none", nullable=True))
    op.execute("UPDATE conversations SET escalation_status = 'none' WHERE escalation_status IS NULL")
    op.alter_column("conversations", "escalation_status", nullable=False)

def downgrade() -> None:
    op.drop_column("conversations", "escalation_status")
