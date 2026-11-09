"""Add passive observe-only shadow_webhook_events table.

Revision ID: 2026_11_09_shadow_webhooks
Revises: 2026_11_01_admin_ts_indexes
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_09_shadow_webhooks"
down_revision: str | None = "2026_11_01_admin_ts_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shadow_webhook_events",
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("chat_id", sa.String(length=255), nullable=False),
        sa.Column("chat_type", sa.String(length=64), nullable=True),
        sa.Column(
            "is_echo",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("author_type", sa.String(length=64), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("message_type", sa.String(length=64), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("content_uri", sa.Text(), nullable=True),
        sa.Column("provider_timestamp", sa.String(length=128), nullable=True),
        sa.Column("raw_message", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            name="uq_shadow_webhook_events_message_id",
        ),
    )
    op.create_index(
        "ix_shadow_webhook_events_message_id",
        "shadow_webhook_events",
        ["message_id"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_shadow_webhook_events_channel_id",
        "shadow_webhook_events",
        ["channel_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_shadow_webhook_events_chat_id",
        "shadow_webhook_events",
        ["chat_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_shadow_webhook_events_chat_created_at",
        "shadow_webhook_events",
        ["chat_id", "created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_shadow_webhook_events_created_at",
        "shadow_webhook_events",
        ["created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shadow_webhook_events_created_at",
        table_name="shadow_webhook_events",
        if_exists=True,
    )
    op.drop_index(
        "ix_shadow_webhook_events_chat_created_at",
        table_name="shadow_webhook_events",
        if_exists=True,
    )
    op.drop_index(
        "ix_shadow_webhook_events_chat_id",
        table_name="shadow_webhook_events",
        if_exists=True,
    )
    op.drop_index(
        "ix_shadow_webhook_events_channel_id",
        table_name="shadow_webhook_events",
        if_exists=True,
    )
    op.drop_index(
        "ix_shadow_webhook_events_message_id",
        table_name="shadow_webhook_events",
        if_exists=True,
    )
    op.drop_table("shadow_webhook_events")
