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


def test_fk_and_query_indexes_migration_and_orm_alignment() -> None:
    from src.models.escalation import Escalation
    from src.models.manager_review import ManagerReview
    from src.models.message import Message
    from src.models.quality_review import QualityReview
    from src.models.referral import Referral

    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "2026_10_13_add_fk_and_query_indexes.py"
    )
    text = migration.read_text()

    for index_name in (
        "ix_messages_conversation_id",
        "ix_messages_conversation_created_at",
        "ix_escalations_conversation_id",
        "ix_escalations_status",
        "ix_quality_reviews_conversation_id",
    ):
        assert index_name in text
    assert "if_not_exists=True" in text

    msg_indexes = {idx.name for idx in Message.__table__.indexes}
    assert "ix_messages_conversation_id" in msg_indexes
    assert "ix_messages_conversation_created_at" in msg_indexes

    esc_indexes = {idx.name for idx in Escalation.__table__.indexes}
    assert "ix_escalations_conversation_id" in esc_indexes
    assert "ix_escalations_status" in esc_indexes

    qr_indexes = {idx.name for idx in QualityReview.__table__.indexes}
    assert "ix_quality_reviews_conversation_id" in qr_indexes

    mr_indexes = {idx.name for idx in ManagerReview.__table__.indexes}
    assert "ix_manager_reviews_manager_name" in mr_indexes
    assert "ix_manager_reviews_created_at" in mr_indexes
    assert ManagerReview.__table__.c.created_at.type.timezone is True  # type: ignore[attr-defined]
    assert ManagerReview.__table__.c.updated_at.type.timezone is True  # type: ignore[attr-defined]
    assert Referral.__table__.c.created_at.type.timezone is True  # type: ignore[attr-defined]
    assert Referral.__table__.c.updated_at.type.timezone is True  # type: ignore[attr-defined]
