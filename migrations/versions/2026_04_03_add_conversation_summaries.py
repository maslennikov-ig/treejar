"""Add persistent conversation summaries.

Revision ID: 2026_04_03_conv_summary_001
Revises: 2026_03_18_auto_faq
Create Date: 2026-04-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_04_03_conv_summary_001"
down_revision: str | None = "2026_03_18_auto_faq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("covered_through_message_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            name="uq_conversation_summaries_conversation_id",
        ),
    )
    op.create_index(
        "ix_conversation_summaries_conversation_id",
        "conversation_summaries",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_summaries_conversation_id",
        table_name="conversation_summaries",
    )
    op.drop_table("conversation_summaries")
