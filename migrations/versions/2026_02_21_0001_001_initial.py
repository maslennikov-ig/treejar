"""initial

Revision ID: 001
Revises:
Create Date: 2026-02-21 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("phone", sa.String(), nullable=False, index=True),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("zoho_contact_id", sa.String(), nullable=True),
        sa.Column("zoho_deal_id", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("sales_stage", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("wazzup_message_id", sa.String(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # products
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("zoho_item_id", sa.String(), nullable=True, unique=True),
        sa.Column("name_en", sa.String(), nullable=False),
        sa.Column("name_ar", sa.String(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True, index=True),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # knowledge_base
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # quality_reviews
    op.create_table(
        "quality_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("total_score", sa.Numeric(4, 1), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("rating", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # escalations
    op.create_table(
        "escalations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("escalations")
    op.drop_table("quality_reviews")
    op.drop_table("knowledge_base")
    op.drop_table("products")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP EXTENSION IF EXISTS vector")
