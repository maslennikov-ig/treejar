"""Add admin action audit table.

Revision ID: 2026_05_07_admin_action_audits
Revises: 2026_04_26_outbound_audit
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_05_07_admin_action_audits"
down_revision: str | None = "2026_04_26_outbound_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_action_audits",
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("request_path", sa.String(length=500), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_action_audits_created_at",
        "admin_action_audits",
        ["created_at"],
    )
    op.create_index(
        "ix_admin_action_audits_action",
        "admin_action_audits",
        ["action"],
    )
    op.create_index(
        "ix_admin_action_audits_entity",
        "admin_action_audits",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_action_audits_entity", table_name="admin_action_audits")
    op.drop_index("ix_admin_action_audits_action", table_name="admin_action_audits")
    op.drop_index("ix_admin_action_audits_created_at", table_name="admin_action_audits")
    op.drop_table("admin_action_audits")
