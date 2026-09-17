"""Real PydanticAI requests must retain persona and retrieved tool evidence."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel

import src.llm.message_processor as processor
from src.dialogue.claim_contract import RetrievedRow
from src.llm import engine
from src.llm.catalog_planning import SalesDeps
from src.llm.message_processor import _sales_agent_route, _Turn
from src.models.conversation import Conversation


@pytest.mark.asyncio
async def test_catalog_repair_keeps_real_prompt_and_completed_tool_history(monkeypatch):
    conv = Conversation(
        id=uuid4(),
        phone="local",
        customer_name="Aisha",
        language="en",
        sales_stage="qualifying",
        metadata_={},
    )
    db = AsyncMock()
    deps = SalesDeps(
        db=db,
        redis=AsyncMock(),
        conversation=conv,
        embedding_engine=None,
        zoho_inventory=None,
        zoho_crm=None,
        messaging_client=None,
        pii_map={},
        user_query="Compare LUMA and NOVO",
        recent_history=["assistant: Shall I compare them?"],
    )
    calls = []
    snapshot = "LUMA 9719-4: catalog price AED 1000; stock unconfirmed. NOVO: catalog price AED 800."

    async def search_products(ctx: RunContext[SalesDeps], query: str) -> str:
        ctx.deps.claim_rows["LUMA"] = RetrievedRow(
            sku="LUMA", fields={"price": "1000", "name": "LUMA 9719-4"}
        )
        return snapshot

    def model_request(messages, info):
        calls.append((messages, info))
        assert "NOOR BASE PERSONA" in (info.instructions or "")
        assert "MODEL-OWNED CUSTOMER INTENT" in info.instructions
        if len(calls) == 1:
            assert any(
                isinstance(p, TextPart) and "Shall I compare" in p.content
                for m in messages
                for p in m.parts
            )
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "search_products",
                        {"query": "LUMA NOVO"},
                        tool_call_id="catalog-1",
                    )
                ]
            )
        assert any(
            isinstance(p, ToolReturnPart) and p.content == snapshot
            for m in messages
            for p in m.parts
        )
        if len(calls) == 2:
            return ModelResponse(parts=[TextPart("LUMA is AED 1000; NOVO is AED 800.")])
        assert len(calls) == 3
        assert "retrieved_rows" in info.instructions
        assert '"price":"1000"' in info.instructions
        assert "Compare LUMA and NOVO" in info.instructions
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps(
                        {
                            "claims": [],
                            "answer": "LUMA is AED 1000; NOVO is AED 800. Stock remains unconfirmed.",
                        }
                    )
                )
            ]
        )

    model = FunctionModel(model_request)
    turn = _Turn(
        pending_reference_route=None,
        order_quote_route=None,
        db=db,
        redis=deps.redis,
        conversation_id=conv.id,
        embedding_engine=None,
        zoho_client=None,
        messaging_client=None,
        crm_client=None,
        source_message_id=None,
        latency_trace=None,
        context_started=None,
        conv=conv,
        crm_context=None,
        pii_map={},
        history=[
            ModelRequest(parts=[UserPromptPart("Furniture for our team")]),
            ModelResponse(parts=[TextPart("Shall I compare them?")]),
        ],
        is_first_turn=False,
        model_runtime=SimpleNamespace(
            get=AsyncMock(return_value=("local-function-model", model))
        ),
        current_message_quote_customer_details={},
        combined_text=deps.user_query,
        masked_text=deps.user_query,
        recent_history=deps.recent_history,
        deps=deps,
    )
    monkeypatch.setattr(
        engine, "build_system_prompt", AsyncMock(return_value="NOOR BASE PERSONA")
    )
    monkeypatch.setattr(
        processor, "_materialize_verified_catalog_facts", lambda _deps: snapshot
    )
    with engine.sales_agent.override(model=model, tools=[search_products]):
        response = await _sales_agent_route(
            turn,
            db_model_main="local-function-model",
            dynamic_model=model,
            claim_contract_every_catalog_turn=False,
        )
    assert len(calls) == 3
    assert "catalog-fact-repair" in response.model
    assert "LUMA is AED 1000" in response.text
    assert "NOVO is AED 800" in response.text


@pytest.mark.asyncio
async def test_output_repair_payload_keeps_catalog_and_masks_history(monkeypatch):
    from src.core.config import settings
    from src.llm.repair_judge import (
        RepairJudgeDecision,
        RepairJudgeEvidence,
        RepairJudgeProviderResult,
        _request_payload,
        review_flagged_reply_with_pii,
    )
    from src.llm.response_policy import ReplyGuardFlag, ReplyPolicyState

    captured = []

    async def runner(request):
        captured.append(json.loads(_request_payload(request)))
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="approve", rationale="Evidence retained"
            ),
            model="local",
        )

    monkeypatch.setattr(settings, "pii_masking_enabled", True)
    await review_flagged_reply_with_pii(
        "LUMA is AED 1000.",
        state=ReplyPolicyState(language="en"),
        flags=(
            ReplyGuardFlag(
                guard_name="empty_list_items", reason="rewrite list coherently"
            ),
        ),
        evidence=RepairJudgeEvidence(
            language="en",
            retrieved_catalog_rows={"LUMA": {"price": "1000", "name": "LUMA 9719-4"}},
            recent_history=(
                "user: aisha@example.com",
                "assistant: Shall I compare LUMA and NOVO?",
            ),
        ),
        provenance="model",
        runner=runner,
    )
    payload = captured[0]
    assert payload["evidence"]["retrieved_catalog_rows"]["LUMA"]["price"] == "1000"
    assert "Shall I compare" in payload["evidence"]["recent_history"][-1]
    assert "aisha@example.com" not in json.dumps(payload)
