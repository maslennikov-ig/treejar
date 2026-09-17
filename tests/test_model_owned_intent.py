"""Customer meaning must reach the tool-using model, including old route triggers.

These are offline routing contracts, not a claim about live model quality.
"""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.usage import RunUsage

from src.llm import engine
from src.models.conversation import Conversation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("previous", "message", "metadata"),
    [
        (
            "Would you like me to suggest a 4-person setup (4 desks + 4 chairs) and check availability and pricing for that quantity?",
            "sure",
            {},
        ),
        ("Would you like assembly included?", "sure", {}),
        ("Would you like assembly included?", "sure, but only if it is free", {}),
        ("Would you like me to check alternatives?", "yes please", {}),
        ("How can I help?", "Where is your showroom?", {}),
        ("How can I help?", "Can you install these tomorrow?", {}),
        ("How can I help?", "Please prepare a proposal", {}),
        ("How can I help?", "Do you have office chairs and assembly?", {}),
        ("What do you prefer?", "Open collaborative workspace", {}),
        ("How can I help?", "Can you repair my chair?", {}),
        ("What do you need?", "2 CH-616, please", {}),
        (
            "Would you like a quotation?",
            "sure",
            {
                "pending_quote_selection": {
                    "source": "exact_quote",
                    "items": [{"sku": "CH-616", "quantity": 2}],
                    "unresolved_items": [],
                }
            },
        ),
        (
            "Please confirm the quotation.",
            "ok",
            {
                "order_runtime": {
                    "quote_frame": {
                        "status": "quoted",
                        "lines": [{"sku": "CH-616", "quantity": 2}],
                    }
                }
            },
        ),
        ("Please confirm the quotation.", "Let me think about it", {}),
        (
            "May I know your name?",
            "Nadia",
            {"name_gate_pending_request": "Find me a desk"},
        ),
        ("Which address should I use?", "Office 402, Tower A, Dubai Marina", {}),
        ("How can I help?", "Show me my previous order", {}),
        ("Хотите подобрать комплект для офиса?", "Конечно", {}),
        ("هل تريد خيارات أخرى؟", "نعم", {}),
    ],
)
async def test_every_customer_intent_reaches_model_without_automatic_actions(
    previous: str,
    message: str,
    metadata: dict,
) -> None:
    await _assert_model_receives_turn(previous, message, metadata)


async def _assert_model_receives_turn(previous, message, metadata, *, saved_case=None):
    conv = Conversation(
        id=uuid4(),
        phone="test",
        customer_name="Nadia",
        sales_stage="qualifying",
        language="en",
        escalation_status="none",
        metadata_=deepcopy(metadata),
    )
    if saved_case is not None:
        for field in ("customer_name", "language", "sales_stage"):
            setattr(conv, field, saved_case[field])
    db = AsyncMock()
    db.get.return_value = conv
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    redis = AsyncMock()
    redis.get.return_value = None
    history = [
        ModelRequest(parts=[UserPromptPart(content="Help me choose furniture")]),
        ModelResponse(parts=[TextPart(content=previous)]),
    ]
    if saved_case is not None:
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        history = ModelMessagesTypeAdapter.validate_python(saved_case["history"])
    model_text = (
        "سأساعدك في هذا الطلب."
        if conv.language == "ar"
        else "I can help with that request."
    )
    model_result = SimpleNamespace(
        output=model_text,
        usage=lambda: RunUsage(input_tokens=12, output_tokens=8),
    )

    async def config(_db, key, default=None):
        return {
            "openrouter_model_main": "mock-model",
            "customer_facts_mode": "disabled",
            "dialogue_kernel_mode": "enforce",
        }.get(key, default)

    with (
        patch.object(engine, "build_message_history", AsyncMock(return_value=history)),
        patch("src.core.config.get_system_config", side_effect=config),
        patch("src.rag.pipeline.search_knowledge", AsyncMock(return_value=[])),
        patch.object(engine, "search_behavior_rules", AsyncMock(return_value=[])),
        patch.object(
            engine.sales_agent, "run", AsyncMock(return_value=model_result)
        ) as run,
        patch.object(
            engine,
            "run_dialogue_kernel",
            AsyncMock(side_effect=AssertionError("semantic kernel invoked")),
        ) as kernel,
        patch.object(
            engine,
            "evaluate_verified_answer_policy",
            side_effect=AssertionError("lexical policy invoked"),
        ),
        patch.object(engine, "create_quotation", AsyncMock()) as quote,
        patch.object(engine, "_create_or_reuse_sales_opportunity", AsyncMock()) as deal,
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            AsyncMock(),
        ) as notify,
    ):
        response = await engine.process_message(
            conv.id, message, db, redis, AsyncMock(), AsyncMock(), AsyncMock()
        )
    run.assert_awaited_once()
    call = run.await_args
    assert call.kwargs["deps"].user_query == engine._strip_synthetic_test_marker(
        message
    )
    assert call.kwargs["deps"].tool_mode == "full"
    if saved_case is None:
        assert f"assistant: {previous}" in call.kwargs["deps"].recent_history
    assert call.kwargs["message_history"] == history
    assert model_text in response.text
    assert response.tokens_in == 12
    for automatic_action in (kernel, quote, deal, notify):
        automatic_action.assert_not_awaited()
    assert conv.escalation_status == "none"
    # Existing order state is context, never authorization to act this turn.
    for key in (
        "pending_quote_selection",
        "order_runtime",
        "name_gate_pending_request",
    ):
        assert (conv.metadata_ or {}).get(key) == metadata.get(key)


_LEGACY_CASES = json.loads(
    (
        Path(__file__).parent / "fixtures/model_owned_intent_legacy_cases.json"
    ).read_text()
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _LEGACY_CASES, ids=lambda case: case["id"])
async def test_former_route_inputs_are_model_owned(case):
    await _assert_model_receives_turn(
        "", case["user_text"], case["metadata"], saved_case=case
    )
