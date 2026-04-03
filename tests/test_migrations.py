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
