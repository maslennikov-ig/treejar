"""Explicit model facts remain durable without a second semantic extractor."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.conversation import Conversation
from src.models.customer_memory import (
    CustomerFact,
    CustomerOrderMemory,
    CustomerProfile,
)
from src.services import customer_memory as memory


@pytest.mark.asyncio
async def test_model_detail_replaces_prior_fact_preserving_provenance() -> None:
    conv = Conversation(id=uuid4(), phone="test", language="en")
    profile = CustomerProfile(id=uuid4(), canonical_phone="test")
    order = CustomerOrderMemory(
        id=uuid4(), conversation_id=conv.id, customer_profile_id=profile.id
    )
    old = CustomerFact(value="Old company", status="accepted")
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock())
    with (
        patch.object(
            memory, "get_or_create_customer_profile", AsyncMock(return_value=profile)
        ),
        patch.object(
            memory, "get_or_create_active_order", AsyncMock(return_value=order)
        ),
        patch.object(memory, "_fetch_accepted_fact", AsyncMock(return_value=old)),
    ):
        await memory.persist_model_customer_details(
            db,
            conversation=conv,
            details={"company": "Setup Sure"},
            evidence={"company": "Setup Sure"},
            source_message_id="msg-1",
        )
    assert old.status == "superseded"
    assert old.superseded_at is not None
    fact = db.add.call_args.args[0]
    assert fact.value == "Setup Sure"
    assert fact.source == "main_model"
    assert fact.source_message_id == "msg-1"
    assert fact.source_excerpt == "Setup Sure"
    assert fact.conversation_id == conv.id
    assert fact.scope == "persistent_profile"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_identical_fact_is_not_duplicated() -> None:
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock())
    conv = Conversation(id=uuid4(), phone="test")
    with (
        patch.object(
            memory,
            "get_or_create_customer_profile",
            AsyncMock(return_value=CustomerProfile(id=uuid4())),
        ),
        patch.object(
            memory,
            "get_or_create_active_order",
            AsyncMock(return_value=CustomerOrderMemory(id=uuid4())),
        ),
        patch.object(
            memory,
            "_fetch_accepted_fact",
            AsyncMock(return_value=CustomerFact(value="Nadia", status="accepted")),
        ),
    ):
        await memory.persist_model_customer_details(
            db,
            conversation=conv,
            details={"name": "Nadia"},
            evidence={"name": "Nadia"},
            source_message_id="msg-2",
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_reading_history_never_creates_profile_or_order() -> None:
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock())
    conv = Conversation(id=uuid4(), phone="test")
    with patch.object(memory, "_fetch_profile_by_phone", AsyncMock(return_value=None)):
        assert (
            await memory.load_existing_customer_context(
                db, conversation=conv, max_past_orders=3
            )
            == ""
        )
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_awaitable_transaction_is_entered_and_rolls_back_on_failure() -> None:
    """SQLAlchemy nested transactions implement BOTH protocols."""
    from src.llm.response_runtime import _customer_facts_write_scope

    events = []

    class Transaction:
        def __await__(self):
            raise AssertionError("Use the transaction context manager")
            yield

        async def __aenter__(self):
            events.append("savepoint")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("rollback" if exc_type else "commit")
            return False

    db = SimpleNamespace(begin_nested=lambda: Transaction())
    with pytest.raises(ValueError, match="failed persistence"):
        async with _customer_facts_write_scope(db):
            events.append("write")
            raise ValueError("failed persistence")
    assert events == ["savepoint", "write", "rollback"]
