"""Add feedbacks table and deal_status column.

Revision ID: feedback_001
Create Date: 2026-03-14
"""

import sqlalchemy as sa
from alembic import op

revision = "feedback_001"
down_revision = "2026_03_14_add_audio_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("deal_id", sa.String(), nullable=True),
        sa.Column("rating_overall", sa.Integer(), nullable=False),
        sa.Column("rating_delivery", sa.Integer(), nullable=False),
        sa.Column("recommend", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating_overall BETWEEN 1 AND 5",
            name="ck_feedbacks_rating_overall",
        ),
        sa.CheckConstraint(
            "rating_delivery BETWEEN 1 AND 5",
            name="ck_feedbacks_rating_delivery",
        ),
    )
    op.create_index(
        "ix_feedbacks_conversation_id", "feedbacks", ["conversation_id"]
    )

    op.add_column(
        "conversations",
        sa.Column("deal_status", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "deal_status")
    op.drop_index("ix_feedbacks_conversation_id", table_name="feedbacks")
    op.drop_table("feedbacks")
