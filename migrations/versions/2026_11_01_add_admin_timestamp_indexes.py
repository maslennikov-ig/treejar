"""Add timestamp indexes for messages and conversations admin/dashboard queries.

Revision ID: 2026_11_01_admin_ts_indexes
Revises: 2026_10_13_fk_query_indexes
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026_11_01_admin_ts_indexes"
down_revision: str | None = "2026_10_13_fk_query_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_created_at",
        "messages",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversations_created_at",
        "conversations",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversations_updated_at",
        "conversations",
        ["updated_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_updated_at",
        table_name="conversations",
        if_exists=True,
    )
    op.drop_index(
        "ix_conversations_created_at",
        table_name="conversations",
        if_exists=True,
    )
    op.drop_index(
        "ix_messages_created_at",
        table_name="messages",
        if_exists=True,
    )
