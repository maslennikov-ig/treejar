"""add unique constraint on knowledge_base source+title

Revision ID: 002
Revises: 001
Create Date: 2026-02-25 00:01:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_knowledge_base_source_title",
        "knowledge_base",
        ["source", "title"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_knowledge_base_source_title",
        "knowledge_base",
        type_="unique",
    )
