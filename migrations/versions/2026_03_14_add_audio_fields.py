"""Add audio fields to message table.

Revision ID: 2026_03_14_add_audio_fields
Revises: 2026_03_13_add_manager_reviews_table
Create Date: 2026-03-14 09:40:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2026_03_14_add_audio_fields"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("audio_url", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("transcription", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "transcription")
    op.drop_column("messages", "audio_url")
