"""Rejected customer writes must reach the real agent as corrective feedback."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from src.dialogue.order_state import QuoteConsent, quote_workflow_from_metadata
from src.dialogue.state import DialogueState
from src.llm import engine
from src.llm.catalog_planning import SalesDeps
from tests.test_customer_intent_tools import context


@pytest.fixture(autouse=True)
def local_agent_dependencies(monkeypatch):
    from src.core import config

    monkeypatch.setattr(config, "get_system_config", AsyncMock(return_value="off"))
    monkeypatch.setattr(
        engine, "build_system_prompt", AsyncMock(return_value="You are Noor.")
    )


def sales_deps(text):
    ctx = context(text)
    return SalesDeps(
        db=ctx.deps.db,
        redis=AsyncMock(),
        conversation=ctx.deps.conversation,
        embedding_engine=None,
        zoho_inventory=None,
        zoho_crm=None,
        messaging_client=None,
        pii_map={},
        user_query=text,
        source_message_id="local-owner-test",
        # Saving requirements remains available after the search budget is spent.
        product_search_calls=20,
    )


@pytest.mark.asyncio
async def test_noncontiguous_refusal_is_retried_then_literal_hold_is_persisted():
    text = (
        "I need two walnut LUMA 9719-4 workstations for eight people in Dubai. "
        "My budget is AED 6000. Please do not prepare a quotation yet.” “"
        "Make it three units for twelve people in the same walnut finish. "
        "Keep the same budget and summarise the updated requirements. "
        "Do not prepare a quotation.” “Please show me CT 1065 coffee tables "
        "in Oak Devon and Wenge Magic, with photos"
    )
    deps = sales_deps(text)
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        names = {tool.name for tool in info.function_tools}
        if calls == 1:
            assert "record_customer_intent" in names
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "Please do not prepare a quotation yet. Do not prepare a quotation.",
                            "quotation_consent": "declined",
                        },
                        tool_call_id="bad-literal",
                    )
                ]
            )
        if calls == 2:
            assert deps.conversation.metadata_ == {}
            deps.db.flush.assert_not_awaited()
            feedback = [
                part
                for message in messages
                for part in message.parts
                if isinstance(part, RetryPromptPart)
            ]
            assert len(feedback) == 1
            assert feedback[0].tool_name == "record_customer_intent"
            assert "literal excerpt" in str(feedback[0].content)
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "Please do not prepare a quotation yet.",
                            "quotation_consent": "declined",
                        },
                        tool_call_id="correct-literal",
                    )
                ]
            )
        assert calls == 3
        assert (
            quote_workflow_from_metadata(deps.conversation.metadata_).consent
            is QuoteConsent.DECLINED
        )
        assert "create_quotation" not in names
        return ModelResponse(parts=[TextPart("Quotation preparation stays on hold.")])

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        result = await engine.sales_agent.run(text, deps=deps)
    assert result.output == "Quotation preparation stays on hold."
    assert calls == 3
    assert deps.conversation.metadata_["model_customer_intent"]["evidence"] == (
        "Please do not prepare a quotation yet."
    )
    deps.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_replacement_is_retried_without_losing_retained_budget(
    monkeypatch,
):
    text = "Make it three LUMA units. Keep the same budget and summarise the update."
    deps = sales_deps(text)
    state = DialogueState.from_conversation(deps.conversation)
    state.slots.selected_items = [{"sku": "LUMA", "quantity": 2}]
    state.slots.budget_cap_aed = 6000
    deps.conversation.metadata_ = state.to_metadata({"unrelated": "preserved"})
    before = deepcopy(deps.conversation.metadata_)
    monkeypatch.setattr(
        engine,
        "_find_catalog_product_by_sku",
        AsyncMock(
            side_effect=[None, SimpleNamespace(sku="LUMA", name_en="LUMA walnut")]
        ),
    )
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        assert "record_customer_requirements" in {
            tool.name for tool in info.function_tools
        }
        if calls == 2:
            assert deps.conversation.metadata_ == before
            deps.db.flush.assert_not_awaited()
            feedback = [
                part
                for message in messages
                for part in message.parts
                if isinstance(part, RetryPromptPart)
            ]
            assert len(feedback) == 1
            assert feedback[0].tool_name == "record_customer_requirements"
            assert "not a catalog SKU" in str(feedback[0].content)
        if calls < 3:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_requirements",
                        {
                            "items": [
                                {
                                    "sku": "INVENTED" if calls == 1 else "LUMA",
                                    "quantity": 3,
                                }
                            ],
                            "replace_items": True,
                        },
                        tool_call_id=f"selection-{calls}",
                    )
                ]
            )
        assert calls == 3
        slots = DialogueState.from_conversation(deps.conversation).slots
        assert slots.selected_items == [
            {"sku": "LUMA", "quantity": 3, "name": "LUMA walnut"}
        ]
        assert slots.budget_cap_aed == 6000
        return ModelResponse(
            parts=[TextPart("Updated: 3 walnut LUMA units; AED 6,000 budget.")]
        )

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        result = await engine.sales_agent.run(text, deps=deps)
    assert "AED 6,000" in result.output
    assert calls == 3
    assert deps.conversation.metadata_["unrelated"] == "preserved"
    deps.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_repeated_invalid_evidence_exhausts_existing_retry_budget(caplog):
    deps = sales_deps("Please do not prepare a quotation.")
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "record_customer_intent",
                    {"evidence": "Invented permission", "quotation_consent": "granted"},
                    tool_call_id=f"invalid-{calls}",
                )
            ]
        )

    model = FunctionModel(model_request)
    with (
        caplog.at_level("INFO", logger="src.llm.engine"),
        engine.sales_agent.override(model=model),
        pytest.raises(UnexpectedModelBehavior, match="retries"),
    ):
        await engine.sales_agent.run(deps.user_query, deps=deps)
    assert calls == 3
    assert deps.conversation.metadata_ == {}
    deps.db.flush.assert_not_awaited()
    assert caplog.text.count("tool=record_customer_intent outcome=rejected") == 3
    assert "Invented permission" not in caplog.text


@pytest.mark.asyncio
async def test_ignored_write_rejection_cannot_be_bypassed_by_final_hold_prose():
    deps = sales_deps("Please do not prepare a quotation yet.")
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "No quotation now",
                            "quotation_consent": "declined",
                        },
                        tool_call_id="rejected-hold",
                    )
                ]
            )
        if calls == 2:
            assert deps.conversation.metadata_ == {}
            return ModelResponse(parts=[TextPart("I'll keep the quotation on hold.")])
        if calls == 3:
            assert deps.conversation.metadata_ == {}
            feedback = [
                str(part.content)
                for message in messages
                for part in message.parts
                if isinstance(part, RetryPromptPart)
            ]
            assert any("record_customer_intent" in content for content in feedback)
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "Please do not prepare a quotation yet.",
                            "quotation_consent": "declined",
                        },
                        tool_call_id="saved-hold",
                    )
                ]
            )
        assert calls == 4
        assert (
            quote_workflow_from_metadata(deps.conversation.metadata_).consent
            is QuoteConsent.DECLINED
        )
        return ModelResponse(parts=[TextPart("Quotation preparation stays on hold.")])

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        result = await engine.sales_agent.run(deps.user_query, deps=deps)
    assert result.output == "Quotation preparation stays on hold."
    assert calls == 4
    deps.db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_batch_quote_is_blocked_after_a_rejected_customer_write(monkeypatch):
    deps = sales_deps("Please do not prepare a quotation yet.")
    deps.conversation.metadata_ = {
        "order_runtime": {
            "quote_workflow": {
                "version": 2,
                "consent": "granted",
                "lifecycle": "quote_requested",
            }
        }
    }
    quotation_boundary = AsyncMock(return_value="Unexpected quotation boundary.")
    monkeypatch.setattr(
        engine, "run_quotation_with_inventory_deferral", quotation_boundary
    )
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        names = {tool.name for tool in info.function_tools}
        if calls == 1:
            assert "create_quotation" in names
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {"evidence": "Don't quote", "quotation_consent": "declined"},
                        tool_call_id="rejected-withdrawal",
                    ),
                    ToolCallPart(
                        "create_quotation",
                        {"items": [{"sku": "LUMA", "quantity": 3}]},
                        tool_call_id="stale-grant",
                    ),
                ]
            )
        quotation_boundary.assert_not_awaited()
        assert "create_quotation" not in names
        if calls == 2:
            assert deps.pending_customer_write_rejections
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "Please do not prepare a quotation yet.",
                            "quotation_consent": "declined",
                        },
                        tool_call_id="correct-withdrawal",
                    )
                ]
            )
        assert calls == 3
        assert not deps.pending_customer_write_rejections
        return ModelResponse(parts=[TextPart("Quotation preparation stays on hold.")])

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        result = await engine.sales_agent.run(deps.user_query, deps=deps)
    assert result.output == "Quotation preparation stays on hold."
    assert (
        quote_workflow_from_metadata(deps.conversation.metadata_).consent
        is QuoteConsent.DECLINED
    )
    quotation_boundary.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("unrelated", ["actionless", "name"])
async def test_unrelated_intent_write_cannot_clear_rejected_consent(unrelated):
    text = "I'm Dana. Please do not prepare a quotation yet."
    deps = sales_deps(text)
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        if calls < 3:
            arguments = {"evidence": text}
            if calls == 1:
                arguments.update(evidence="No quote", quotation_consent="declined")
            elif unrelated == "name":
                arguments["details"] = [
                    {"field": "name", "value": "Dana", "evidence": "Dana"}
                ]
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        arguments,
                        tool_call_id=f"intent-{calls}",
                    )
                ]
            )
        if calls == 3:
            assert deps.pending_customer_write_rejections[
                "record_customer_intent"
            ].required_fields == frozenset({"quotation_consent"})
            assert (
                quote_workflow_from_metadata(deps.conversation.metadata_).consent
                is QuoteConsent.NOT_REQUESTED
            )
            return ModelResponse(
                parts=[TextPart("Quotation preparation stays on hold.")]
            )
        if calls == 4:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {"evidence": text, "quotation_consent": "declined"},
                        tool_call_id="correct-consent",
                    )
                ]
            )
        assert calls == 5
        assert not deps.pending_customer_write_rejections
        assert (
            quote_workflow_from_metadata(deps.conversation.metadata_).consent
            is QuoteConsent.DECLINED
        )
        return ModelResponse(parts=[TextPart("Quotation preparation stays on hold.")])

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        await engine.sales_agent.run(text, deps=deps)
    assert calls == 5


@pytest.mark.asyncio
async def test_budget_write_does_not_clear_rejected_selection(monkeypatch):
    deps = sales_deps("Three LUMA units; budget AED 6000.")
    monkeypatch.setattr(
        engine,
        "_find_catalog_product_by_sku",
        AsyncMock(side_effect=[None, SimpleNamespace(sku="LUMA")]),
    )
    calls = 0

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        if calls in {1, 2, 4}:
            arguments = (
                {"budget_cap_aed": 6000}
                if calls == 2
                else {
                    "items": [
                        {"sku": "INVENTED" if calls == 1 else "LUMA", "quantity": 3}
                    ],
                    "replace_items": True,
                }
            )
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_requirements",
                        arguments,
                        tool_call_id=f"requirements-{calls}",
                    )
                ]
            )
        if calls == 3:
            assert deps.pending_customer_write_rejections[
                "record_customer_requirements"
            ].required_fields == frozenset({"items"})
            assert not DialogueState.from_conversation(
                deps.conversation
            ).slots.selected_items
            return ModelResponse(parts=[TextPart("Recorded three LUMA units.")])
        assert calls == 5
        assert not deps.pending_customer_write_rejections
        assert DialogueState.from_conversation(
            deps.conversation
        ).slots.selected_items == [{"sku": "LUMA", "quantity": 3}]
        return ModelResponse(parts=[TextPart("Three LUMA units; budget AED 6000.")])

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        await engine.sales_agent.run(deps.user_query, deps=deps)
    assert calls == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_literal_first", [False, True])
async def test_policy_denied_consent_can_recover_to_selection_and_quote_offer(
    monkeypatch, bad_literal_first
):
    text = "I will take three LUMA units."
    deps = sales_deps(text)
    monkeypatch.setattr(
        engine,
        "_find_catalog_product_by_sku",
        AsyncMock(return_value=SimpleNamespace(sku="LUMA")),
    )
    calls = 0
    consent_calls = 2 if bad_literal_first else 1

    def model_request(messages, info):
        nonlocal calls
        calls += 1
        if calls <= consent_calls:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "Please quote"
                            if bad_literal_first and calls == 1
                            else text,
                            "quotation_consent": "granted",
                        },
                        tool_call_id=f"ungrounded-consent-{calls}",
                    )
                ]
            )
        assert not deps.pending_customer_write_rejections
        if calls == consent_calls + 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_requirements",
                        {"items": [{"sku": "LUMA", "quantity": 3}]},
                        tool_call_id="save-selection",
                    )
                ]
            )
        assert calls == consent_calls + 2
        assert (
            quote_workflow_from_metadata(deps.conversation.metadata_).consent
            is QuoteConsent.NOT_REQUESTED
        )
        assert DialogueState.from_conversation(
            deps.conversation
        ).slots.selected_items == [{"sku": "LUMA", "quantity": 3}]
        return ModelResponse(
            parts=[TextPart("Three LUMA units. Would you like a quotation?")]
        )

    model = FunctionModel(model_request)
    with engine.sales_agent.override(model=model):
        result = await engine.sales_agent.run(text, deps=deps)
    assert result.output == "Three LUMA units. Would you like a quotation?"
    assert calls == consent_calls + 2
