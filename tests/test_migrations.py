from __future__ import annotations

import re
from pathlib import Path

REVISION_RE = re.compile(r'revision\s*(?::\s*str)?\s*=\s*"([^"]+)"')
ALEMBIC_VERSION_COLUMN_LIMIT = 32


def test_alembic_revision_ids_fit_version_column() -> None:
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"

    for migration_file in migrations_dir.glob("*.py"):
        match = REVISION_RE.search(migration_file.read_text())
        assert match is not None, f"Missing revision in {migration_file.name}"
        revision = match.group(1)
        assert len(revision) <= ALEMBIC_VERSION_COLUMN_LIMIT, (
            f"{migration_file.name} revision '{revision}' exceeds "
            f"{ALEMBIC_VERSION_COLUMN_LIMIT} characters"
        )


def test_outbound_audit_migration_defines_required_constraints() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "2026_04_26_add_outbound_message_audit.py"
    )
    text = migration.read_text()

    assert "op.create_table(" in text
    assert '"outbound_message_audits"' in text
    assert '"crm_message_id"' in text
    assert "uq_outbound_message_audits_provider_crm_message_id" in text
    assert "uq_outbound_message_audits_provider_message_id" in text
