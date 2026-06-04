from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.conversation import Conversation
from src.models.customer_memory import (
    CustomerFact,
    CustomerOrderMemory,
    CustomerProfile,
)


class _FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.add = self.added.append
        self.flush = AsyncMock()


def _profile() -> CustomerProfile:
    profile = CustomerProfile(canonical_phone="+971500000001")
    profile.id = uuid4()
    return profile


def _conversation() -> Conversation:
    conversation = Conversation(phone="+971500000001")
    conversation.id = uuid4()
    return conversation


def _order(profile: CustomerProfile, conversation: Conversation) -> CustomerOrderMemory:
    order = CustomerOrderMemory(
        customer_profile_id=profile.id,
        conversation_id=conversation.id,
        status="active",
        profile=profile,
        conversation=conversation,
    )
    order.id = uuid4()
    return order


def _fact_input(**overrides: object) -> SimpleNamespace:
    values = {
        "scope": "persistent_profile",
        "key": "customer.name",
        "value": "Lili",
        "confidence": "high",
        "source": "deterministic",
        "evidence": "Lili",
        "source_message_id": "msg-1",
        "needs_confirmation": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_get_or_create_customer_profile_returns_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    existing = _profile()
    monkeypatch.setattr(
        customer_memory,
        "_fetch_profile_by_phone",
        AsyncMock(return_value=existing),
    )

    profile = await customer_memory.get_or_create_customer_profile(
        db,  # type: ignore[arg-type]
        phone=" +971500000001 ",
    )

    assert profile is existing
    assert db.added == []
    db.flush.assert_not_awaited()
    customer_memory._fetch_profile_by_phone.assert_awaited_once_with(  # type: ignore[attr-defined]
        db,
        "+971500000001",
    )


@pytest.mark.asyncio
async def test_get_or_create_customer_profile_creates_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    monkeypatch.setattr(
        customer_memory,
        "_fetch_profile_by_phone",
        AsyncMock(return_value=None),
    )

    profile = await customer_memory.get_or_create_customer_profile(
        db,  # type: ignore[arg-type]
        phone=" +971500000002 ",
    )

    assert isinstance(profile, CustomerProfile)
    assert profile.canonical_phone == "+971500000002"
    assert db.added == [profile]
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_active_order_creates_order_scoped_to_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    profile = _profile()
    conversation = _conversation()
    monkeypatch.setattr(
        customer_memory,
        "_fetch_active_order",
        AsyncMock(return_value=None),
    )

    order = await customer_memory.get_or_create_active_order(
        db,  # type: ignore[arg-type]
        profile=profile,
        conversation=conversation,
    )

    assert isinstance(order, CustomerOrderMemory)
    assert order.profile is profile
    assert order.conversation is conversation
    assert order.status == "active"
    assert db.added == [order]
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_high_confidence_profile_fact_is_accepted_and_updates_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    profile = _profile()
    conversation = _conversation()
    order = _order(profile, conversation)
    monkeypatch.setattr(
        customer_memory,
        "_fetch_accepted_fact",
        AsyncMock(return_value=None),
    )

    result = await customer_memory.apply_extracted_facts(
        db,  # type: ignore[arg-type]
        profile=profile,
        order=order,
        message=None,
        facts=[_fact_input(value="Lili")],
    )

    saved = db.added[0]
    assert isinstance(saved, CustomerFact)
    assert saved.status == "accepted"
    assert saved.order_memory_id is None
    assert profile.display_name == "Lili"
    assert result.accepted == [saved]
    assert result.proposed == []
    assert result.conflicts == []


@pytest.mark.asyncio
async def test_lower_confidence_conflict_is_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    profile = _profile()
    profile.display_name = "Lili"
    conversation = _conversation()
    order = _order(profile, conversation)
    existing = CustomerFact(
        profile=profile,
        scope="persistent_profile",
        key="customer.name",
        value="Lili",
        confidence="high",
        status="accepted",
        source="deterministic",
    )
    monkeypatch.setattr(
        customer_memory,
        "_fetch_accepted_fact",
        AsyncMock(return_value=existing),
    )

    result = await customer_memory.apply_extracted_facts(
        db,  # type: ignore[arg-type]
        profile=profile,
        order=order,
        message=None,
        facts=[_fact_input(value="Lily", confidence="medium")],
    )

    saved = db.added[0]
    assert isinstance(saved, CustomerFact)
    assert saved.status == "conflict"
    assert saved.value == "Lily"
    assert profile.display_name == "Lili"
    assert result.accepted == []
    assert result.conflicts == [saved]


@pytest.mark.asyncio
async def test_current_order_fact_remains_order_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    profile = _profile()
    conversation = _conversation()
    order = _order(profile, conversation)
    monkeypatch.setattr(
        customer_memory,
        "_fetch_accepted_fact",
        AsyncMock(return_value=None),
    )

    await customer_memory.apply_extracted_facts(
        db,  # type: ignore[arg-type]
        profile=profile,
        order=order,
        message=None,
        facts=[
            _fact_input(
                scope="current_order",
                key="delivery.address",
                value="1 Dubai",
                evidence="delivery to 1 Dubai",
            )
        ],
    )

    saved = db.added[0]
    assert isinstance(saved, CustomerFact)
    assert saved.status == "accepted"
    assert saved.order_memory_id == order.id
    assert saved.scope == "current_order"


@pytest.mark.asyncio
async def test_past_order_reference_requires_confirmation_not_order_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    db = _FakeDb()
    profile = _profile()
    conversation = _conversation()
    order = _order(profile, conversation)
    monkeypatch.setattr(
        customer_memory,
        "_fetch_accepted_fact",
        AsyncMock(return_value=None),
    )

    result = await customer_memory.apply_extracted_facts(
        db,  # type: ignore[arg-type]
        profile=profile,
        order=order,
        message=None,
        facts=[
            _fact_input(
                scope="past_order_reference",
                key="past_order.reuse_request",
                value={"intent": "same_as_last_time"},
                needs_confirmation=True,
            )
        ],
    )

    saved = db.added[0]
    assert isinstance(saved, CustomerFact)
    assert saved.status == "proposed"
    assert saved.order_memory_id is None
    assert result.confirmation_required == [saved]
    assert result.accepted == []


@pytest.mark.asyncio
async def test_mark_order_quoted_freezes_snapshot_without_closing() -> None:
    from src.services.customer_memory import mark_order_quoted

    profile = _profile()
    conversation = _conversation()
    order = _order(profile, conversation)
    snapshot = {"items": [{"sku": "CH 616", "quantity": 6}], "quote_id": "Q-1"}

    updated = await mark_order_quoted(_FakeDb(), order=order, snapshot=snapshot)  # type: ignore[arg-type]

    assert updated is order
    assert order.status == "quoted_snapshot"
    assert order.snapshot == snapshot
    assert order.quoted_at is not None
    assert order.closed_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["accepted", "closed_refused", "closed_no_response"])
async def test_close_order_sets_terminal_status(status: str) -> None:
    from src.services.customer_memory import close_order

    profile = _profile()
    conversation = _conversation()
    order = _order(profile, conversation)

    updated = await close_order(
        _FakeDb(),  # type: ignore[arg-type]
        order=order,
        status=status,
        snapshot={"final_status": status},
    )

    assert updated is order
    assert order.status == status
    assert order.closed_at is not None
    assert order.snapshot == {"final_status": status}


@pytest.mark.asyncio
async def test_build_customer_facts_context_is_compact_and_marks_past_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    profile = _profile()
    profile.display_name = "Lili"
    profile.primary_email = "lili@example.com"
    conversation = _conversation()
    active_order = _order(profile, conversation)
    active_order.status = "quoted_snapshot"
    past_order = CustomerOrderMemory(
        profile=profile,
        status="accepted",
        closed_at=datetime(2026, 5, 22, tzinfo=UTC),
        snapshot={"items": [{"sku": "CH 616", "quantity": 4}]},
    )

    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_profile_facts",
        AsyncMock(
            return_value=[
                CustomerFact(
                    profile=profile,
                    scope="persistent_profile",
                    key="customer.company",
                    value="LLD",
                    confidence="high",
                    status="accepted",
                    source="deterministic",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_order_facts",
        AsyncMock(
            return_value=[
                CustomerFact(
                    profile=profile,
                    order_memory=active_order,
                    scope="current_order",
                    key="delivery.address",
                    value="1 Dubai",
                    confidence="high",
                    status="accepted",
                    source="deterministic",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        customer_memory,
        "_fetch_past_orders",
        AsyncMock(return_value=[past_order]),
    )

    context = await customer_memory.build_customer_facts_context(
        _FakeDb(),  # type: ignore[arg-type]
        profile=profile,
        active_order=active_order,
        max_past_orders=1,
    )

    rendered = context.render()
    assert "Known customer profile:" in rendered
    assert "- Name: Lili" in rendered
    assert "- Known company: LLD" in rendered
    assert "Current order:" in rendered
    assert "- Delivery address: 1 Dubai" in rendered
    assert "- Quote status: quoted_snapshot" in rendered
    assert "Past orders:" in rendered
    assert "Last closed order: 2026-05-22, 4 x CH 616, status accepted" in rendered
    assert "Missing for quotation:" in rendered


@pytest.mark.asyncio
async def test_build_customer_facts_context_requires_specific_delivery_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    profile = _profile()
    profile.display_name = "Lili"
    profile.primary_email = "lili@example.com"
    conversation = _conversation()
    active_order = _order(profile, conversation)

    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_profile_facts",
        AsyncMock(
            return_value=[
                CustomerFact(
                    profile=profile,
                    scope="persistent_profile",
                    key="customer.company",
                    value="LLD",
                    confidence="high",
                    status="accepted",
                    source="deterministic",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_order_facts",
        AsyncMock(
            return_value=[
                CustomerFact(
                    profile=profile,
                    order_memory=active_order,
                    scope="current_order",
                    key="delivery.address",
                    value="Dubai",
                    confidence="medium",
                    status="accepted",
                    source="deterministic",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        customer_memory, "_fetch_past_orders", AsyncMock(return_value=[])
    )

    context = await customer_memory.build_customer_facts_context(
        _FakeDb(),  # type: ignore[arg-type]
        profile=profile,
        active_order=active_order,
        max_past_orders=1,
    )

    assert "- specific delivery address" in context.missing_quote_fields


@pytest.mark.asyncio
async def test_build_customer_facts_context_accepts_current_order_individual_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import customer_memory

    profile = _profile()
    profile.display_name = "Lili"
    profile.primary_email = "lili@example.com"
    conversation = _conversation()
    active_order = _order(profile, conversation)

    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_profile_facts",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        customer_memory,
        "_fetch_context_order_facts",
        AsyncMock(
            return_value=[
                CustomerFact(
                    profile=profile,
                    order_memory=active_order,
                    scope="current_order",
                    key="customer.type",
                    value="individual",
                    confidence="high",
                    status="accepted",
                    source="deterministic",
                ),
                CustomerFact(
                    profile=profile,
                    order_memory=active_order,
                    scope="current_order",
                    key="delivery.address",
                    value="1 Dubai",
                    confidence="high",
                    status="accepted",
                    source="deterministic",
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        customer_memory, "_fetch_past_orders", AsyncMock(return_value=[])
    )

    context = await customer_memory.build_customer_facts_context(
        _FakeDb(),  # type: ignore[arg-type]
        profile=profile,
        active_order=active_order,
        max_past_orders=1,
    )

    assert "- company name or explicit individual status" not in (
        context.missing_quote_fields
    )
