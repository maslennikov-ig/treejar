"""Main-model intent decisions retain evidence and real quotation boundaries."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.tools import ToolDefinition

from src.dialogue.order_state import QuoteConsent, quote_workflow_from_metadata
from src.llm import engine
from src.models.conversation import Conversation


@pytest.fixture(autouse=True)
def customer_memory_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core import config

    monkeypatch.setattr(config, "get_system_config", AsyncMock(return_value="off"))


def context(text: str, metadata: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        deps=SimpleNamespace(
            user_query=text,
            pii_map={},
            source_message_id="source-1",
            recent_history=[],
            conversation=Conversation(
                phone="+971500000000", language="en", metadata_=metadata or {}
            ),
            db=SimpleNamespace(flush=AsyncMock()),
            executed_tool_names=[],
            tool_mode="full",
            product_search_calls=0,
        )
    )


@pytest.mark.asyncio
async def test_invented_evidence_cannot_change_consent_or_details() -> None:
    ctx = context("sure")
    result = await engine.record_customer_intent(
        ctx, evidence="send quotation", quotation_consent="granted"
    )
    assert result.startswith("Not recorded")
    assert ctx.deps.conversation.metadata_ == {}
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_declined_quote_can_be_reopened_by_model_with_current_evidence() -> None:
    ctx = context("Hold it for now")
    await engine.record_customer_intent(
        ctx, evidence="Hold it", quotation_consent="declined"
    )
    tools = [
        ToolDefinition(name="create_quotation"),
        ToolDefinition(name="record_customer_intent"),
    ]
    # The state tool survives withdrawal and makes quotation available again.
    from unittest.mock import patch

    with patch.object(engine, "_product_search_call_limit", return_value=3):
        assert [t.name for t in await engine._prepare_sales_tools(ctx, tools)] == [
            "record_customer_intent"
        ]
        ctx.deps.user_query = "Please prepare it now"
        await engine.record_customer_intent(
            ctx, evidence="Please prepare it now", quotation_consent="granted"
        )
        assert await engine._prepare_sales_tools(ctx, tools) == tools
    assert (
        quote_workflow_from_metadata(ctx.deps.conversation.metadata_).consent
        is QuoteConsent.GRANTED
    )


@pytest.mark.asyncio
async def test_details_persist_without_keyword_interpretation() -> None:
    ctx = context("Our company is Setup Sure. Deliver to Total Tower 12.")
    await engine.record_customer_intent(
        ctx,
        evidence=ctx.deps.user_query,
        details=[
            engine.CustomerDetailEvidence(
                field="company", value="Setup Sure", evidence="Setup Sure"
            ),
            engine.CustomerDetailEvidence(
                field="address", value="Total Tower 12", evidence="Total Tower 12"
            ),
        ],
    )
    assert ctx.deps.conversation.metadata_["quote_customer_details"] == {
        "company": "Setup Sure",
        "address": "Total Tower 12",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"proposal_followup": {}},
        {
            "proposal_followup": {"sent_at": "2026-09-17", "kp_message_id": "msg"},
            "quotation_decision_status": "rejected",
        },
    ],
)
async def test_acceptance_requires_a_real_pending_quotation(
    metadata: dict[str, Any],
) -> None:
    ctx = context("Approved", metadata)
    result = await engine.record_customer_intent(
        ctx, evidence="Approved", accept_sent_quotation=True
    )
    assert result.startswith("Not recorded")
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_acceptance_records_state_without_notifying() -> None:
    ctx = context(
        "That works, go ahead",
        {
            "proposal_followup": {"sent_at": "2026-09-17", "kp_message_id": "msg"},
            "quotation_decision_status": "pending",
        },
    )
    result = await engine.record_customer_intent(
        ctx, evidence="That works, go ahead", accept_sent_quotation=True
    )
    assert ctx.deps.conversation.metadata_["quotation_decision_status"] == "approved"
    assert ctx.deps.quote_acceptance_recorded_this_turn is True
    assert "no manager was notified" in result
    ctx.deps.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_pii_is_validated_masked_and_stored_unmasked() -> None:
    ctx = context("Email is [EMAIL_1]")
    ctx.deps.pii_map = {"[EMAIL_1]": "buyer@example.com"}
    await engine.record_customer_intent(
        ctx,
        evidence="[EMAIL_1]",
        details=[
            engine.CustomerDetailEvidence(
                field="email", value="[EMAIL_1]", evidence="[EMAIL_1]"
            )
        ],
    )
    assert (
        ctx.deps.conversation.metadata_["quote_customer_details"]["email"]
        == "buyer@example.com"
    )
    assert (
        ctx.deps.conversation.metadata_["model_customer_intent"]["evidence"]
        == "buyer@example.com"
    )


@pytest.mark.asyncio
async def test_blank_details_rejected() -> None:
    ctx = context("my name")
    result = await engine.record_customer_intent(
        ctx,
        evidence="my name",
        details=[
            engine.CustomerDetailEvidence(field="name", value="   ", evidence="my name")
        ],
    )
    assert result.startswith("Not recorded")
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_acceptance_enables_manager_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.integrations.notifications import escalation

    notify = AsyncMock()
    monkeypatch.setattr(escalation, "notify_manager_escalation", notify)
    ctx = context(
        "sure",
        {
            "proposal_followup": {"sent_at": "2026-09-17", "kp_message_id": "msg"},
            "quotation_decision_status": "pending",
        },
    )
    await engine.record_customer_intent(
        ctx, evidence="sure", accept_sent_quotation=True
    )
    from unittest.mock import patch

    with patch.object(engine, "_product_search_call_limit", return_value=3):
        assert "escalate_to_manager" in [
            tool.name
            for tool in await engine._prepare_sales_tools(
                ctx, [ToolDefinition(name="escalate_to_manager")]
            )
        ]
    await engine.escalate_to_manager(
        ctx, reason="accepted", escalation_type="order_confirmation"
    )
    notify.assert_awaited_once()
    repeated = await engine.record_customer_intent(
        ctx, evidence="sure", accept_sent_quotation=True
    )
    assert "already recorded" in repeated
    ctx.deps.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_canonical_quote_frame_details_are_preserved() -> None:
    from src.dialogue.order_state import (
        QuoteDetails,
        QuoteFrame,
        QuoteLine,
        quote_frame_from_metadata,
        quote_frame_to_metadata,
    )

    metadata = quote_frame_to_metadata(
        {},
        QuoteFrame(
            lines=[QuoteLine(sku="CH-616", quantity=2)],
            quote_details=QuoteDetails(company="Existing Co"),
        ),
    )
    ctx = context("New Tower 12", metadata)
    await engine.record_customer_intent(
        ctx,
        evidence="New Tower 12",
        details=[
            engine.CustomerDetailEvidence(
                field="address", value="New Tower 12", evidence="New Tower 12"
            )
        ],
    )
    frame = quote_frame_from_metadata(ctx.deps.conversation.metadata_)
    assert frame is not None
    assert frame.quote_details.company == "Existing Co"
    assert frame.quote_details.address == "New Tower 12"


@pytest.mark.asyncio
async def test_enforce_mode_persists_unmasked_model_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core import config
    from src.services import customer_memory

    monkeypatch.setattr(config, "get_system_config", AsyncMock(return_value="enforce"))
    persist = AsyncMock()
    monkeypatch.setattr(customer_memory, "persist_model_customer_details", persist)
    ctx = context("[EMAIL_1]")
    ctx.deps.pii_map = {"[EMAIL_1]": "buyer@example.com"}
    await engine.record_customer_intent(
        ctx,
        evidence="[EMAIL_1]",
        details=[
            engine.CustomerDetailEvidence(
                field="email", value="[EMAIL_1]", evidence="[EMAIL_1]"
            )
        ],
    )
    persist.assert_awaited_once_with(
        ctx.deps.db,
        conversation=ctx.deps.conversation,
        details={"email": "buyer@example.com"},
        evidence={"email": "buyer@example.com"},
        source_message_id="source-1",
        accept_sent_quotation=False,
    )


@pytest.mark.asyncio
async def test_memory_write_failure_does_not_leave_local_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core import config
    from src.services import customer_memory

    monkeypatch.setattr(config, "get_system_config", AsyncMock(return_value="enforce"))
    monkeypatch.setattr(
        customer_memory,
        "persist_model_customer_details",
        AsyncMock(side_effect=RuntimeError("write failed")),
    )
    ctx = context("New Name")
    with pytest.raises(RuntimeError, match="write failed"):
        await engine.record_customer_intent(
            ctx,
            evidence="New Name",
            details=[
                engine.CustomerDetailEvidence(
                    field="name", value="New Name", evidence="New Name"
                )
            ],
        )
    assert ctx.deps.conversation.metadata_ == {}
    assert ctx.deps.conversation.customer_name is None
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_proposal_response_requires_evidence_and_sent_state() -> None:
    ctx = context("Please wait")
    result = await engine.record_proposal_response(
        ctx, evidence="not interested", decision="rejected"
    )
    assert result.startswith("Not recorded")
    result = await engine.record_proposal_response(
        ctx, evidence="Please wait", decision="pause"
    )
    assert result.startswith("Not recorded")
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_rejects_sent_proposal_without_sending() -> None:
    ctx = context(
        "We decline this proposal",
        {
            "proposal_followup": {"sent_at": "2026-09-17", "kp_message_id": "msg"},
            "quotation_decision_status": "pending",
        },
    )
    result = await engine.record_proposal_response(
        ctx, evidence="We decline this proposal", decision="rejected"
    )
    assert ctx.deps.conversation.metadata_["quotation_decision_status"] == "rejected"
    assert "No messages were sent" in result
    assert (
        ctx.deps.conversation.metadata_["model_proposal_response"]["source_message_id"]
        == "source-1"
    )
    repeat = await engine.record_proposal_response(
        ctx, evidence="We decline this proposal", decision="pause"
    )
    assert repeat.startswith("Not recorded")


@pytest.mark.asyncio
async def test_model_proposal_pause_restores_neutral_stopped_chain() -> None:
    ctx = context(
        "Please wait",
        {
            "proposal_followup": {
                "sent_at": "2026-09-17",
                "kp_message_id": "msg",
                "chain_stopped": True,
                "stop_reason": "customer_reply",
            },
            "quotation_decision_status": "pending",
        },
    )
    result = await engine.record_proposal_response(
        ctx, evidence="Please wait", decision="pause"
    )
    assert "model_customer_pause" in result
    assert (
        ctx.deps.conversation.metadata_["proposal_followup"]["chain_stopped"] is False
    )
    assert ctx.deps.conversation.metadata_["quotation_decision_status"] == "pending"
