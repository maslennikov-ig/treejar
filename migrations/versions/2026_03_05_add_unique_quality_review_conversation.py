"""Add unique constraint to quality_reviews.conversation_id.

CR-12: Prevents duplicate reviews for the same conversation at DB level.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-05
"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint + index on conversation_id
    op.create_index(
        "ix_quality_reviews_conversation_id",
        "quality_reviews",
        ["conversation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_quality_reviews_conversation_id", table_name="quality_reviews")
