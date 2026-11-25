"""Track the canonical template last applied to a knowledge-base row."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_11_25_kb_template_digest"
down_revision: str | None = "2026_11_09_shadow_webhooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_base", sa.Column("canonical_template_digest", sa.String(64))
    )


def downgrade() -> None:
    op.drop_column("knowledge_base", "canonical_template_digest")
