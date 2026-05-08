"""Add bot behavior rules.

Revision ID: 2026_05_08_bot_behavior_rules
Revises: 2026_05_07_kb_admin_fields
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "2026_05_08_bot_behavior_rules"
down_revision: str | None = "2026_05_07_kb_admin_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_behavior_rules",
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("segment", sa.String(length=120), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("trigger_examples", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bot_behavior_rules_status",
        "bot_behavior_rules",
        ["status"],
    )
    op.create_index(
        "ix_bot_behavior_rules_type",
        "bot_behavior_rules",
        ["type"],
    )
    op.create_index(
        "ix_bot_behavior_rules_context",
        "bot_behavior_rules",
        ["stage", "language", "segment"],
    )
    op.create_index(
        "ix_bot_behavior_rules_priority",
        "bot_behavior_rules",
        ["priority"],
    )
    op.create_index(
        "ix_bot_behavior_rules_archived_at",
        "bot_behavior_rules",
        ["archived_at"],
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bot_behavior_rules_embedding_hnsw "
        "ON bot_behavior_rules USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bot_behavior_rules_embedding_hnsw")
    op.drop_index("ix_bot_behavior_rules_archived_at", table_name="bot_behavior_rules")
    op.drop_index("ix_bot_behavior_rules_priority", table_name="bot_behavior_rules")
    op.drop_index("ix_bot_behavior_rules_context", table_name="bot_behavior_rules")
    op.drop_index("ix_bot_behavior_rules_type", table_name="bot_behavior_rules")
    op.drop_index("ix_bot_behavior_rules_status", table_name="bot_behavior_rules")
    op.drop_table("bot_behavior_rules")
