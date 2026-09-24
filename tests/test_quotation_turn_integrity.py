"""One quotation per document, created on the turn that makes it ready (tj-2ey4).

Replays conversation 76bc49c8 (live WhatsApp check, 2026-09-24) through the
real turn pipeline with a scripted model, mocked Zoho and a mocked WhatsApp
provider:

- Defect A. Consent was recorded and one LUMA line chosen; the customer sent
  company, address and email in one message. The model recorded them, skipped
  `create_quotation` and asked for the name it already had. No quotation.
- Defect B. After Fr4032 was sent the customer wrote "it's okay". Acceptance
  was recorded and, in the same turn, Fr4033 went out with the same content.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.dialogue.state import DialogueState
from src.llm import engine
from src.models.conversation import Conversation

pytestmark = pytest.mark.usefixtures("authorized_outbound_unit_path")

LUMA = "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut"
LUMA_NAME = "Four person workstation SKYLAND LUMA 9719-4"
ADDRESS = "5, Street 27A, Ad Jafiliya, Bur Dubai, Emirate of Dubai"
EMAIL = "Anjela.abramian@mail.ru"
DETAILS_MESSAGE = f"{ADDRESS}\nAIDevTeam\n{EMAIL}"
ASKED_FOR_DETAILS = (
    "Great, I've noted you're ready to proceed with 1 x SKYLAND LUMA 9719-4. "
    "To prepare the quotation, please send your company name, specific "
    "delivery address, and email address."
)
SKIPPED_REPLY = "Thank you! Could you please confirm your full name for the quotation?"


def _conversation_after_consent() -> Conversation:
    """State after turn 2 ("I'm ready"): consent granted, one line chosen."""

    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA, "quantity": 1, "name": LUMA_NAME}]
    metadata = {
        **state.to_metadata(),
        "order_runtime": {
            "quote_workflow": {
                "version": 2,
                "consent": "granted",
                "lifecycle": "quote_requested",
            }
        },
    }
    return Conversation(
        id=uuid4(),
        phone="+971500000076",
        customer_name="Nadia",
        sales_stage="solution",
        language="en",
        escalation_status="none",
        metadata_=deepcopy(metadata),
    )


def _zoho() -> AsyncMock:
    zoho = AsyncMock()
    zoho.get_stock_bulk.return_value = [
        {
            "sku": LUMA,
            "item_id": "zoho-luma-1",
            "rate": 1883.0,
            "stock_on_hand": 30,
            "description": "Four person workstation",
            "name": LUMA_NAME,
        }
    ]
    zoho.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-76",
        "contact_type": "customer",
        "status": "active",
    }
    zoho.create_sale_order.side_effect = [
        {"saleorder": {"salesorder_id": f"so-{n}", "salesorder_number": f"Fr{n}"}}
        for n in (4032, 4033, 4034)
    ]
    return zoho


def _messaging() -> AsyncMock:
    messaging = AsyncMock()
    messaging.send_media.side_effect = ["media-1", "media-2", "media-3"]
    return messaging


def _db(conversation: Conversation) -> AsyncMock:
    db = AsyncMock()
    db.get.return_value = conversation
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    return db


async def _config(_db: Any, key: str, default: Any = None) -> Any:
    return {
        "openrouter_model_main": "mock-model",
        "customer_facts_mode": "disabled",
    }.get(key, default)


def _history(*turns: tuple[str, str]) -> list[ModelMessage]:
    history: list[ModelMessage] = []
    for user, assistant in turns:
        history.append(ModelRequest(parts=[UserPromptPart(content=user)]))
        history.append(ModelResponse(parts=[TextPart(content=assistant)]))
    return history


async def _turn(
    conversation: Conversation,
    *,
    message: str,
    history: list[ModelMessage],
    model_fn: Any,
    zoho: AsyncMock,
    messaging: AsyncMock,
    source_message_id: str,
) -> Any:
    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return model_fn(messages, info)

    with (
        patch.object(engine, "build_message_history", AsyncMock(return_value=history)),
        patch("src.core.config.get_system_config", side_effect=_config),
        patch("src.rag.pipeline.search_knowledge", AsyncMock(return_value=[])),
        patch.object(engine, "search_behavior_rules", AsyncMock(return_value=[])),
        patch.object(
            engine, "build_system_prompt", AsyncMock(return_value="You are Noor.")
        ),
        patch("src.llm.engine.OpenAIChatModel", return_value=FunctionModel(scripted)),
        patch(
            "src.services.pdf.generator.generate_pdf",
            AsyncMock(return_value=b"pdf"),
        ),
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>",
        ),
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            AsyncMock(),
        ),
    ):
        return await engine.process_message(
            conversation.id,
            message,
            _db(conversation),
            AsyncMock(get=AsyncMock(return_value=None)),
            AsyncMock(),
            zoho,
            messaging,
            source_message_id=source_message_id,
        )


def _record_details_call() -> ToolCallPart:
    return ToolCallPart(
        "record_customer_intent",
        {
            "evidence": "AIDevTeam",
            "details": [
                {"field": "company", "value": "AIDevTeam", "evidence": "AIDevTeam"},
                {"field": "address", "value": ADDRESS, "evidence": ADDRESS},
                {"field": "email", "value": EMAIL, "evidence": EMAIL},
            ],
        },
    )


class _DetailsTurnModel:
    """Turn 3 as it went live: details recorded, the quotation call skipped."""

    def __init__(self, *, calls_create_quotation: bool = False) -> None:
        self.calls_create_quotation = calls_create_quotation
        self.steps: list[AgentInfo] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.steps.append(info)
        if not info.function_tools:
            assert "QUOTATION CALL MADE BY THE RUNTIME" in (info.instructions or "")
            assert "Fr4032" in (info.instructions or "")
            return ModelResponse(
                parts=[
                    TextPart(
                        "Thank you, Nadia. I have AIDevTeam, your Bur Dubai address "
                        "and your email. Quotation Fr4032 has been sent to you; "
                        "does it work for you?"
                    )
                ]
            )
        if len(self.steps) == 1:
            return ModelResponse(parts=[_record_details_call()])
        if self.calls_create_quotation and len(self.steps) == 2:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "create_quotation", {"items": [{"sku": LUMA, "quantity": 1}]}
                    )
                ]
            )
        if self.calls_create_quotation:
            return ModelResponse(
                parts=[TextPart("Quotation Fr4032 has been sent to you.")]
            )
        return ModelResponse(parts=[TextPart(SKIPPED_REPLY)])


@pytest.mark.asyncio
async def test_details_completing_turn_creates_the_quotation_the_model_skipped() -> (
    None
):
    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    model = _DetailsTurnModel()

    response = await _turn(
        conversation,
        message=DETAILS_MESSAGE,
        history=_history(("I'm ready", ASKED_FOR_DETAILS)),
        model_fn=model,
        zoho=zoho,
        messaging=messaging,
        source_message_id="244fc940",
    )

    zoho.create_sale_order.assert_awaited_once()
    line = zoho.create_sale_order.await_args.kwargs["items"][0]
    assert (line["item_id"], line["quantity"]) == ("zoho-luma-1", 1)
    messaging.send_media.assert_awaited_once()
    assert "Fr4032" in response.text
    assert "already have your name" not in response.text
    assert SKIPPED_REPLY not in response.text
    assert response.model.endswith("|quotation-completion")
    assert [trace.tool_name for trace in response.tool_traces] == ["create_quotation"]
    # Two steps of the ordinary turn, then one tool-less reply over the result.
    assert len(model.steps) == 3
    metadata = conversation.metadata_
    assert metadata["order_runtime"]["quote_workflow"]["lifecycle"] == "created"
    assert metadata["quotation_effect"]["sale_order_number"] == "Fr4032"
    assert DialogueState.from_conversation(conversation).slots.quote_sent is True


@pytest.mark.asyncio
async def test_details_turn_where_the_model_quotes_itself_is_left_alone() -> None:
    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    model = _DetailsTurnModel(calls_create_quotation=True)

    response = await _turn(
        conversation,
        message=DETAILS_MESSAGE,
        history=_history(("I'm ready", ASKED_FOR_DETAILS)),
        model_fn=model,
        zoho=zoho,
        messaging=messaging,
        source_message_id="244fc940",
    )

    zoho.create_sale_order.assert_awaited_once()
    assert response.text.endswith("Quotation Fr4032 has been sent to you.")
    assert not response.model.endswith("|quotation-completion")
    assert len(model.steps) == 3


@pytest.mark.asyncio
async def test_details_turn_still_missing_a_detail_does_not_quote() -> None:
    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    partial = f"{ADDRESS}\nAIDevTeam"

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len([m for m in messages if isinstance(m, ModelResponse)]) == 0:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {
                            "evidence": "AIDevTeam",
                            "details": [
                                {
                                    "field": "company",
                                    "value": "AIDevTeam",
                                    "evidence": "AIDevTeam",
                                },
                                {
                                    "field": "address",
                                    "value": ADDRESS,
                                    "evidence": ADDRESS,
                                },
                            ],
                        },
                    )
                ]
            )
        return ModelResponse(
            parts=[TextPart("Thank you. Which email should the quotation go to?")]
        )

    response = await _turn(
        conversation,
        message=partial,
        history=_history(("I'm ready", ASKED_FOR_DETAILS)),
        model_fn=model_fn,
        zoho=zoho,
        messaging=messaging,
        source_message_id="244fc940",
    )

    zoho.create_sale_order.assert_not_awaited()
    assert "email" in response.text
    lifecycle = conversation.metadata_["order_runtime"]["quote_workflow"]["lifecycle"]
    assert lifecycle == "quote_requested"


class _LaterTurnModel:
    """A later turn whose model calls create_quotation for the same document."""

    def __init__(self, *, accept: bool) -> None:
        self.accept = accept
        self.steps: list[AgentInfo] = []
        self.tool_results: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.steps.append(info)
        last = messages[-1]
        for part in getattr(last, "parts", ()):
            content = getattr(part, "content", None)
            if getattr(part, "part_kind", "") == "tool-return":
                self.tool_results.append(str(content))
        step = len(self.steps)
        if self.accept and step == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "record_customer_intent",
                        {"evidence": "it's okay", "accept_sent_quotation": True},
                    )
                ]
            )
        if step == (2 if self.accept else 1):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "create_quotation", {"items": [{"sku": LUMA, "quantity": 1}]}
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("Thank you, noted.")])


@pytest.mark.asyncio
@pytest.mark.parametrize("accept", [True, False], ids=["acceptance", "no-change"])
async def test_a_later_turn_never_reissues_the_sent_quotation(accept: bool) -> None:
    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    await _turn(
        conversation,
        message=DETAILS_MESSAGE,
        history=_history(("I'm ready", ASKED_FOR_DETAILS)),
        model_fn=_DetailsTurnModel(),
        zoho=zoho,
        messaging=messaging,
        source_message_id="244fc940",
    )
    assert zoho.create_sale_order.await_count == 1

    model = _LaterTurnModel(accept=accept)
    response = await _turn(
        conversation,
        message="it's okay",
        history=_history(
            ("I'm ready", ASKED_FOR_DETAILS),
            (DETAILS_MESSAGE, "Quotation Fr4032 has been sent to you."),
        ),
        model_fn=model,
        zoho=zoho,
        messaging=messaging,
        source_message_id="29c653d1",
    )

    # The directive that sent the model to Fr4033 is gone...
    first_instructions = model.steps[0].instructions or ""
    assert "call create_quotation now" not in first_instructions
    # ...and a call made anyway creates nothing.
    assert zoho.create_sale_order.await_count == 1
    assert messaging.send_media.await_count == 1
    assert any(
        "No new quotation was created" in r or "no new quotation" in r
        for r in model.tool_results
    )
    assert "Fr4033" not in response.text
    metadata = conversation.metadata_
    assert metadata["quotation_effect"]["sale_order_number"] == "Fr4032"
    if accept:
        assert metadata["quotation_decision"]["status"] == "approved"


@pytest.mark.asyncio
async def test_a_quotation_call_refused_too_early_is_still_owed() -> None:
    """Called before the details were recorded, refused, never retried."""

    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    steps: list[AgentInfo] = []

    def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        steps.append(info)
        if not info.function_tools:
            return ModelResponse(
                parts=[TextPart("Thank you, Nadia. Quotation Fr4032 has been sent.")]
            )
        if len(steps) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "create_quotation", {"items": [{"sku": LUMA, "quantity": 1}]}
                    )
                ]
            )
        if len(steps) == 2:
            return ModelResponse(parts=[_record_details_call()])
        return ModelResponse(parts=[TextPart(SKIPPED_REPLY)])

    response = await _turn(
        conversation,
        message=DETAILS_MESSAGE,
        history=_history(("I'm ready", ASKED_FOR_DETAILS)),
        model_fn=model_fn,
        zoho=zoho,
        messaging=messaging,
        source_message_id="244fc940",
    )

    zoho.create_sale_order.assert_awaited_once()
    assert "Fr4032" in response.text
    assert response.model.endswith("|quotation-completion")


@pytest.mark.asyncio
async def test_a_deferred_quotation_call_is_not_repeated() -> None:
    """Zoho refused the call this turn: the deferral already told the customer."""

    import httpx

    from src.integrations.inventory.zoho_inventory import ZohoRateLimitError

    conversation = _conversation_after_consent()
    zoho, messaging = _zoho(), _messaging()
    request = httpx.Request("GET", "https://www.zohoapis.eu/inventory/v1/items")
    zoho.get_stock_bulk.side_effect = ZohoRateLimitError(
        "429 Too Many Requests",
        request=request,
        response=httpx.Response(429, request=request),
        retry_after_seconds=None,
    )
    model = _DetailsTurnModel(calls_create_quotation=True)

    with patch(
        "src.llm.quotation_deferral.alert_managers_for_conversation",
        AsyncMock(return_value=True),
    ):
        response = await _turn(
            conversation,
            message=DETAILS_MESSAGE,
            history=_history(("I'm ready", ASKED_FOR_DETAILS)),
            model_fn=model,
            zoho=zoho,
            messaging=messaging,
            source_message_id="244fc940",
        )

    assert zoho.get_stock_bulk.await_count == 1
    zoho.create_sale_order.assert_not_awaited()
    assert not response.model.endswith("|quotation-completion")
    assert conversation.metadata_["pending_quotation"]["status"] == "pending"
