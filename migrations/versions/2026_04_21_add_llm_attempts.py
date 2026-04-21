"""Add durable LLM attempt state.

Revision ID: 2026_04_21_llm_attempts
Revises: 2026_04_03_conv_summary_001
Create Date: 2026-04-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_04_21_llm_attempts"
down_revision: str | None = "2026_04_03_conv_summary_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_attempts",
        sa.Column("path", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("entity_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("settings_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("budget_cents", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(12, 6), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "status in ("
            "'pending', "
            "'success', "
            "'no_action', "
            "'failed_retryable', "
            "'failed_final', "
            "'budget_blocked', "
            "'needs_manual_review'"
            ")",
            name="ck_llm_attempts_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "path",
            "entity_type",
            "entity_id",
            "entity_updated_at",
            "prompt_version",
            name="uq_llm_attempts_logical_key",
        ),
    )
    op.create_index("ix_llm_attempts_status", "llm_attempts", ["status"])
    op.create_index(
        "ix_llm_attempts_status_next_retry_at",
        "llm_attempts",
        ["status", "next_retry_at"],
    )
    op.create_index(
        "ix_llm_attempts_entity",
        "llm_attempts",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_attempts_entity", table_name="llm_attempts")
    op.drop_index("ix_llm_attempts_status_next_retry_at", table_name="llm_attempts")
    op.drop_index("ix_llm_attempts_status", table_name="llm_attempts")
    op.drop_table("llm_attempts")
