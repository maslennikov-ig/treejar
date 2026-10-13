"""Add missing foreign-key and query indexes for messages, escalations, and quality_reviews.

Revision ID: 2026_10_13_fk_query_indexes
Revises: 2026_06_04_customer_memory
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026_10_13_fk_query_indexes"
down_revision: str | None = "2026_06_04_customer_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_escalations_conversation_id",
        "escalations",
        ["conversation_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_escalations_status",
        "escalations",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_quality_reviews_conversation_id",
        "quality_reviews",
        ["conversation_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_escalations_status",
        table_name="escalations",
        if_exists=True,
    )
    op.drop_index(
        "ix_escalations_conversation_id",
        table_name="escalations",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_conversation_created_at",
        table_name="messages",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_conversation_id",
        table_name="messages",
        if_exists=True,
    )
