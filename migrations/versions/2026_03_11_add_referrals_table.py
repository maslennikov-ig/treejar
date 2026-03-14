"""Add referrals table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-11
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String, nullable=False),
        sa.Column("referrer_phone", sa.String, nullable=False),
        sa.Column("referee_phone", sa.String, nullable=True),
        sa.Column(
            "referrer_discount_percent", sa.Float, nullable=False, server_default="5.0"
        ),
        sa.Column(
            "referee_discount_percent", sa.Float, nullable=False, server_default="10.0"
        ),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_referrals_code", "referrals", ["code"], unique=True)
    op.create_index("ix_referrals_referrer_phone", "referrals", ["referrer_phone"])


def downgrade() -> None:
    op.drop_index("ix_referrals_referrer_phone", table_name="referrals")
    op.drop_index("ix_referrals_code", table_name="referrals")
    op.drop_table("referrals")
