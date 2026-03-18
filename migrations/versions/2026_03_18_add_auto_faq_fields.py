"""Add auto-FAQ fields to knowledge_base.

Revision ID: 2026_03_18_auto_faq
Revises: feedback_001
Create Date: 2026-03-18
"""

import sqlalchemy as sa
from alembic import op

revision = "2026_03_18_auto_faq"
down_revision = "feedback_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base",
        sa.Column(
            "is_auto_generated",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_base",
        sa.Column("original_question", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_base",
        sa.Column("manager_draft", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_base", "manager_draft")
    op.drop_column("knowledge_base", "original_question")
    op.drop_column("knowledge_base", "is_auto_generated")
