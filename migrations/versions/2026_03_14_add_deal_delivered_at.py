"""Add deal_delivered_at column to conversations.

Revision ID: deal_delivered_at_001
Revises: feedback_001
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "deal_delivered_at_001"
down_revision = "feedback_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "deal_delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "deal_delivered_at")
