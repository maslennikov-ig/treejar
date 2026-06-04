"""Add customer profile facts and order memory tables.

Revision ID: 2026_06_04_customer_memory
Revises: 2026_05_08_bot_behavior_rules
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_06_04_customer_memory"
down_revision: str | None = "2026_05_08_bot_behavior_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_profiles",
        sa.Column("canonical_phone", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("preferred_language", sa.String(length=8), nullable=True),
        sa.Column("primary_email", sa.String(length=255), nullable=True),
        sa.Column("zoho_contact_id", sa.String(length=120), nullable=True),
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
        sa.UniqueConstraint(
            "canonical_phone",
            name="uq_customer_profiles_canonical_phone",
        ),
    )
    op.create_table(
        "customer_order_memories",
        sa.Column("customer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("zoho_salesorder_id", sa.String(length=120), nullable=True),
        sa.Column("zoho_quote_id", sa.String(length=120), nullable=True),
        sa.Column("deal_id", sa.String(length=120), nullable=True),
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
        sa.CheckConstraint(
            "status in ('active', 'quoted_snapshot', 'accepted', "
            "'closed_refused', 'closed_no_response', 'superseded')",
            name="ck_customer_order_status",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["customer_profile_id"], ["customer_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "customer_facts",
        sa.Column("customer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("order_memory_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_message_id", sa.String(length=120), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "scope in ('persistent_profile', 'current_order', "
            "'past_order_reference')",
            name="ck_customer_fact_scope",
        ),
        sa.CheckConstraint(
            "confidence in ('high', 'medium', 'low')",
            name="ck_customer_fact_confidence",
        ),
        sa.CheckConstraint(
            "status in ('accepted', 'proposed', 'conflict', "
            "'rejected', 'superseded')",
            name="ck_customer_fact_status",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["customer_profile_id"], ["customer_profiles.id"]),
        sa.ForeignKeyConstraint(
            ["order_memory_id"],
            ["customer_order_memories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_customer_order_memories_profile_status",
        "customer_order_memories",
        ["customer_profile_id", "status"],
    )
    op.create_index(
        "ix_customer_order_memories_conversation_status",
        "customer_order_memories",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_customer_facts_profile_scope_key_status",
        "customer_facts",
        ["customer_profile_id", "scope", "key", "status"],
    )
    op.create_index(
        "ix_customer_facts_source_message_id",
        "customer_facts",
        ["source_message_id"],
    )
    op.create_index(
        "ix_customer_facts_order_scope_key_status",
        "customer_facts",
        ["order_memory_id", "scope", "key", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_facts_order_scope_key_status",
        table_name="customer_facts",
    )
    op.drop_index(
        "ix_customer_facts_source_message_id",
        table_name="customer_facts",
    )
    op.drop_index(
        "ix_customer_facts_profile_scope_key_status",
        table_name="customer_facts",
    )
    op.drop_index(
        "ix_customer_order_memories_conversation_status",
        table_name="customer_order_memories",
    )
    op.drop_index(
        "ix_customer_order_memories_profile_status",
        table_name="customer_order_memories",
    )
    op.drop_table("customer_facts")
    op.drop_table("customer_order_memories")
    op.drop_table("customer_profiles")
