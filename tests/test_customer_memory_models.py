from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import ForeignKey, Index, UniqueConstraint


def test_customer_memory_models_declare_required_tables_and_columns() -> None:
    from src.models.customer_memory import (
        CUSTOMER_FACT_CONFIDENCES,
        CUSTOMER_FACT_SCOPES,
        CUSTOMER_FACT_STATUSES,
        CUSTOMER_ORDER_STATUSES,
        CustomerFact,
        CustomerOrderMemory,
        CustomerProfile,
    )

    assert CustomerProfile.__tablename__ == "customer_profiles"
    assert CustomerOrderMemory.__tablename__ == "customer_order_memories"
    assert CustomerFact.__tablename__ == "customer_facts"

    assert set(CustomerProfile.__table__.columns) >= {
        CustomerProfile.__table__.columns.id,
        CustomerProfile.__table__.columns.canonical_phone,
        CustomerProfile.__table__.columns.display_name,
        CustomerProfile.__table__.columns.preferred_language,
        CustomerProfile.__table__.columns.primary_email,
        CustomerProfile.__table__.columns.zoho_contact_id,
        CustomerProfile.__table__.columns.metadata,
    }
    assert set(CustomerOrderMemory.__table__.columns.keys()) >= {
        "customer_profile_id",
        "conversation_id",
        "status",
        "started_at",
        "quoted_at",
        "closed_at",
        "snapshot",
        "zoho_salesorder_id",
        "zoho_quote_id",
        "deal_id",
    }
    assert set(CustomerFact.__table__.columns.keys()) >= {
        "customer_profile_id",
        "order_memory_id",
        "conversation_id",
        "scope",
        "key",
        "value",
        "confidence",
        "status",
        "source",
        "source_message_id",
        "source_excerpt",
        "superseded_at",
    }

    assert set(CUSTOMER_ORDER_STATUSES) == {
        "active",
        "quoted_snapshot",
        "accepted",
        "closed_refused",
        "closed_no_response",
        "superseded",
    }
    assert set(CUSTOMER_FACT_SCOPES) == {
        "persistent_profile",
        "current_order",
        "past_order_reference",
    }
    assert set(CUSTOMER_FACT_CONFIDENCES) == {"high", "medium", "low"}
    assert set(CUSTOMER_FACT_STATUSES) == {
        "accepted",
        "proposed",
        "conflict",
        "rejected",
        "superseded",
    }


def test_customer_memory_models_declare_relationships_and_json_value() -> None:
    from src.models.conversation import Conversation
    from src.models.customer_memory import (
        CustomerFact,
        CustomerOrderMemory,
        CustomerProfile,
    )

    profile = CustomerProfile(canonical_phone="+971500000001")
    conversation = Conversation(phone="+971500000001")
    order = CustomerOrderMemory(
        profile=profile,
        conversation=conversation,
        snapshot={"items": [{"sku": "CH 616", "quantity": 6}]},
    )
    fact = CustomerFact(
        profile=profile,
        order_memory=order,
        conversation=conversation,
        scope="current_order",
        key="order.items",
        value=[{"sku": "CH 616", "quantity": 6}],
        confidence="high",
        status="accepted",
        source="deterministic",
    )

    assert order.profile is profile
    assert order.conversation is conversation
    assert fact.order_memory is order
    assert fact.value == [{"sku": "CH 616", "quantity": 6}]

    order_fk_targets = {
        fk.target_fullname
        for column in CustomerOrderMemory.__table__.columns
        for fk in column.foreign_keys
        if isinstance(fk, ForeignKey)
    }
    fact_fk_targets = {
        fk.target_fullname
        for column in CustomerFact.__table__.columns
        for fk in column.foreign_keys
        if isinstance(fk, ForeignKey)
    }
    assert "customer_profiles.id" in order_fk_targets
    assert "conversations.id" in order_fk_targets
    assert "customer_profiles.id" in fact_fk_targets
    assert "customer_order_memories.id" in fact_fk_targets


def test_customer_memory_models_declare_useful_indexes() -> None:
    from src.models.customer_memory import (
        CustomerFact,
        CustomerOrderMemory,
        CustomerProfile,
    )

    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in CustomerProfile.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    order_indexes = {
        (index.name, tuple(column.name for column in index.columns))
        for index in CustomerOrderMemory.__table__.indexes
        if isinstance(index, Index)
    }
    fact_indexes = {
        (index.name, tuple(column.name for column in index.columns))
        for index in CustomerFact.__table__.indexes
        if isinstance(index, Index)
    }

    assert ("canonical_phone",) in unique_constraints
    assert (
        "ix_customer_order_memories_profile_status",
        ("customer_profile_id", "status"),
    ) in order_indexes
    assert (
        "ix_customer_facts_profile_scope_key_status",
        ("customer_profile_id", "scope", "key", "status"),
    ) in fact_indexes
    assert (
        "ix_customer_facts_source_message_id",
        ("source_message_id",),
    ) in fact_indexes


def test_customer_memory_migration_is_non_destructive_and_reversible() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "2026_06_04_add_customer_memory.py"
    )
    assert migration_path.exists()

    spec = importlib.util.spec_from_file_location(
        "customer_memory_migration", migration_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.down_revision == "2026_05_08_bot_behavior_rules"

    text = migration_path.read_text()
    assert '"customer_profiles"' in text
    assert '"customer_order_memories"' in text
    assert '"customer_facts"' in text
    assert "op.add_column" not in text
    assert "op.drop_column" not in text
    assert 'op.drop_table("customer_facts")' in text
    assert 'op.drop_table("customer_order_memories")' in text
    assert 'op.drop_table("customer_profiles")' in text
