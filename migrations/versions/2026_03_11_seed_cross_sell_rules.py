"""Seed cross_sell_rules in SystemConfig.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-11
"""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

CROSS_SELL_RULES = """{
    "desk": ["chair", "monitor_arm", "cable_management"],
    "chair": ["cushion", "footrest", "armrest"],
    "storage": ["shelf", "filing_cabinet", "organizer"],
    "table": ["chair", "lighting"],
    "sofa": ["coffee_table", "side_table"],
    "partition": ["acoustic_panel", "planter"]
}"""


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_configs (id, key, value, created_at, updated_at)
        VALUES (
            gen_random_uuid(),
            'cross_sell_rules',
            '{CROSS_SELL_RULES}'::jsonb,
            now(),
            now()
        )
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_configs WHERE key = 'cross_sell_rules'")
