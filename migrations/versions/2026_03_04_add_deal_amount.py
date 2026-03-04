"""Add deal_amount to conversations.

Revision ID: a1b2c3d4e5f6
Revises: 357b6e18989e
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "357b6e18989e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("deal_amount", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "deal_amount")
