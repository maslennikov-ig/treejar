"""Add manager_reviews table and manual_takeover status.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manager_reviews",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "escalation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("escalations.id"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("manager_name", sa.String, nullable=True),
        sa.Column("total_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("max_score", sa.Integer, nullable=False, server_default="20"),
        sa.Column("rating", sa.String, nullable=False),
        sa.Column("criteria", sa.JSON, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("first_response_time_seconds", sa.Integer, nullable=True),
        sa.Column("message_count", sa.Integer, nullable=True),
        sa.Column("deal_converted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deal_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("reviewer", sa.String, nullable=False, server_default="ai"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Unique constraint: one review per escalation
    op.create_index(
        "ix_manager_reviews_escalation_id",
        "manager_reviews",
        ["escalation_id"],
        unique=True,
    )
    op.create_index(
        "ix_manager_reviews_conversation_id",
        "manager_reviews",
        ["conversation_id"],
    )
    op.create_index(
        "ix_manager_reviews_manager_name",
        "manager_reviews",
        ["manager_name"],
    )
    op.create_index(
        "ix_manager_reviews_created_at",
        "manager_reviews",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_manager_reviews_created_at", table_name="manager_reviews")
    op.drop_index("ix_manager_reviews_manager_name", table_name="manager_reviews")
    op.drop_index("ix_manager_reviews_conversation_id", table_name="manager_reviews")
    op.drop_index("ix_manager_reviews_escalation_id", table_name="manager_reviews")
    op.drop_table("manager_reviews")
