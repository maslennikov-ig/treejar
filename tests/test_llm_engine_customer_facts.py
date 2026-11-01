import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm import engine as engine_module
from src.llm.engine import SalesDeps, inject_system_prompt, process_message
from src.models.conversation import Conversation
from src.schemas.common import SalesStage


class _FakeAgentResult:
    def __init__(self, output: str) -> None:
        self.output = output
        self._usage = SimpleNamespace(input_tokens=11, output_tokens=7)

    def usage(self) -> SimpleNamespace:
        return self._usage


def _deps() -> tuple[
    AsyncMock,
    Conversation,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        customer_name="Lili",
        sales_stage=SalesStage.GREETING.value,
        language="en",
        escalation_status="none",
    )
    db.get.return_value = conv

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    embedding = AsyncMock()
    zoho = AsyncMock()
    redis = AsyncMock()
    redis.get.return_value = None
    messaging = AsyncMock()
    crm = AsyncMock()
    crm.find_contact_by_phone.return_value = None
    return db, conv, embedding, zoho, redis, messaging, crm


def _unknown_name_deps() -> tuple[
    AsyncMock,
    Conversation,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    db, conv, embedding, zoho, redis, messaging, crm = _deps()
    conv.customer_name = None
    conv.metadata_ = {}
    return db, conv, embedding, zoho, redis, messaging, crm


async def _config(_db: object, key: str, default: str) -> str:
    return {
        "customer_facts_mode": "enforce",
        "customer_facts_max_context_orders": "2",
        "openrouter_model_main": "mock-model",
    }.get(key, default)


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_inject_system_prompt_includes_customer_facts_memory(
    mock_prompt: AsyncMock,
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    db, conv, embedding, zoho, redis, messaging, crm = _deps()
    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=embedding,
        zoho_inventory=zoho,
        zoho_crm=crm,
        messaging_client=messaging,
        pii_map={},
        customer_facts_context=(
            "Known customer profile:\n"
            "- Name: Lili\n"
            "Current order:\n"
            "- Delivery address: 1 Dubai\n"
            "Past orders:\n"
            "- Last closed order: 2026-05-22, 4 x CH 616, status accepted\n"
            "Missing for quotation:\n"
            "- company name or explicit individual status"
        ),
    )
    ctx = RunContext(
        deps=deps,
        retry=0,
        messages=[],
        prompt="",
        model=TestModel(),
        usage=RunUsage(),
    )

    prompt = await inject_system_prompt(ctx)

    assert "[CUSTOMER FACTS MEMORY]" in prompt
    assert "Known customer profile:" in prompt
    assert "Past orders are historical" in prompt
    assert "Last closed order: 2026-05-22, 4 x CH 616" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "customer_text,pending",
    [
        (
            "Please recommend ergonomic chairs. Lili, individual, 1 Dubai, lili@example.com",
            False,
        ),
        ("Victor Memory Test, individual, Office 1905, JLT Dubai", True),
        ("What did I order last time?", False),
    ],
)
async def test_customer_memory_is_data_for_model_not_a_semantic_interceptor(
    customer_text: str,
    pending: bool,
) -> None:
    db, conv, embedding, zoho, redis, messaging, crm = _unknown_name_deps()
    if pending:
        conv.metadata_ = {
            engine_module.NAME_GATE_PENDING_REQUEST_KEY: {
                "text": "Please recommend ergonomic chairs.",
                "source": "first_turn_name_gate",
            }
        }
    original_metadata = dict(conv.metadata_)
    memory = "Known customer profile: Lili\nPast orders: 4 x CH 616, accepted"
    with (
        patch.object(engine_module.settings, "pii_masking_enabled", True),
        patch.object(
            engine_module, "search_behavior_rules", AsyncMock(return_value=[])
        ),
        patch("src.rag.pipeline.search_knowledge", AsyncMock(return_value=[])),
        patch("src.core.config.get_system_config", AsyncMock(side_effect=_config)),
        patch.object(
            engine_module,
            "build_message_history",
            AsyncMock(
                return_value=[
                    ModelRequest(
                        parts=[
                            UserPromptPart(content="Please recommend ergonomic chairs.")
                        ]
                    ),
                    ModelResponse(
                        parts=[TextPart(content="What would you like to know?")]
                    ),
                ]
            ),
        ),
        patch.object(
            engine_module.sales_agent,
            "run",
            AsyncMock(return_value=_FakeAgentResult("Here is the model's answer.")),
        ) as run,
        patch(
            "src.services.customer_memory.load_existing_customer_context",
            AsyncMock(return_value=memory),
        ) as load,
        patch.object(
            engine_module, "get_or_create_customer_profile", AsyncMock()
        ) as create_profile,
    ):
        response = await process_message(
            conversation_id=conv.id,
            combined_text=customer_text,
            source_message_id="msg-source-1",
            db=db,
            redis=redis,
            embedding_engine=embedding,
            zoho_client=zoho,
            messaging_client=messaging,
            crm_client=crm,
        )
    assert response.text == "Here is the model's answer."
    run.assert_awaited_once()
    load.assert_awaited_once_with(db, conversation=conv, max_past_orders=2)
    create_profile.assert_not_awaited()
    deps = run.await_args.kwargs["deps"]
    assert deps.customer_facts_context == memory
    assert deps.source_message_id == "msg-source-1"
    assert conv.customer_name is None
    assert "quote_customer_details" not in conv.metadata_
    if pending:
        assert (
            conv.metadata_[engine_module.NAME_GATE_PENDING_REQUEST_KEY]
            == original_metadata[engine_module.NAME_GATE_PENDING_REQUEST_KEY]
        )
    if "lili@example.com" in customer_text:
        assert "lili@example.com" not in deps.user_query
        assert "lili@example.com" in deps.pii_map.values()
