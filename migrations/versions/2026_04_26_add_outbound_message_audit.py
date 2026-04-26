"""Add outbound Wazzup message audit table.

Revision ID: 2026_04_26_outbound_audit
Revises: 2026_04_21_llm_attempts
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_04_26_outbound_audit"
down_revision: str | None = "2026_04_21_llm_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbound_message_audits",
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.String(length=255), nullable=False),
        sa.Column("outbound_chat_id", sa.String(length=255), nullable=True),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("content_uri", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("crm_message_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "crm_message_id",
            name="uq_outbound_message_audits_provider_crm_message_id",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_message_id",
            name="uq_outbound_message_audits_provider_message_id",
        ),
    )
    op.create_index(
        "ix_outbound_message_audits_conversation_id",
        "outbound_message_audits",
        ["conversation_id"],
    )
    op.create_index(
        "ix_outbound_message_audits_status",
        "outbound_message_audits",
        ["status"],
    )
    op.create_index(
        "ix_outbound_message_audits_source",
        "outbound_message_audits",
        ["source"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outbound_message_audits_source",
        table_name="outbound_message_audits",
    )
    op.drop_index(
        "ix_outbound_message_audits_status",
        table_name="outbound_message_audits",
    )
    op.drop_index(
        "ix_outbound_message_audits_conversation_id",
        table_name="outbound_message_audits",
    )
    op.drop_table("outbound_message_audits")
