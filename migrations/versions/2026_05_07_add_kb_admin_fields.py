"""Add admin knowledge-base soft delete and candidate queue.

Revision ID: 2026_05_07_kb_admin_fields
Revises: 2026_05_07_admin_action_audits
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_05_07_kb_admin_fields"
down_revision: str | None = "2026_05_07_admin_action_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_base",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_base",
        sa.Column("deleted_by", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "ix_knowledge_base_deleted_at",
        "knowledge_base",
        ["deleted_at"],
    )

    op.create_table(
        "knowledge_base_candidates",
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("guard_reasons", sa.JSON(), nullable=True),
        sa.Column("duplicate_similarity", sa.Numeric(5, 4), nullable=True),
        sa.Column("original_question", sa.Text(), nullable=True),
        sa.Column("manager_draft", sa.Text(), nullable=True),
        sa.Column("customer_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
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
    )
    op.create_index(
        "ix_knowledge_base_candidates_status",
        "knowledge_base_candidates",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_base_candidates_status",
        table_name="knowledge_base_candidates",
    )
    op.drop_table("knowledge_base_candidates")
    op.drop_index("ix_knowledge_base_deleted_at", table_name="knowledge_base")
    op.drop_column("knowledge_base", "deleted_by")
    op.drop_column("knowledge_base", "deleted_at")
    op.drop_column("knowledge_base", "updated_at")
