import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm import engine as engine_module
from src.llm.engine import SalesDeps, inject_system_prompt, process_message
from src.models.conversation import Conversation
from src.models.customer_memory import CustomerOrderMemory, CustomerProfile
from src.schemas.common import SalesStage
from src.services.customer_memory import CustomerFactsContext


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


async def _config(_db: object, key: str, default: str) -> str:
    return {
        "customer_facts_mode": "enforce",
        "customer_facts_trace_enabled": "true",
        "customer_facts_fast_extractor_enabled": "false",
        "customer_facts_max_context_orders": "2",
        "dialogue_kernel_mode": "legacy",
        "dialogue_kernel_trace_enabled": "true",
        "dialogue_kernel_enforced_flows": "",
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
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_customer_facts_enforce_persists_and_injects_context(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
) -> None:
    db, conv, embedding, zoho, redis, messaging, crm = _deps()
    profile = CustomerProfile(canonical_phone=conv.phone, display_name="Lili")
    profile.id = uuid.uuid4()
    order = CustomerOrderMemory(
        customer_profile_id=profile.id,
        conversation_id=conv.id,
        status="active",
    )
    order.id = uuid.uuid4()
    context = CustomerFactsContext(
        profile_lines=["- Name: Lili"],
        current_order_lines=["- Delivery address: 1 Dubai"],
        past_order_lines=[],
        missing_quote_fields=["- company name or explicit individual status"],
    )

    async def apply_side_effect(
        _db: object,
        *,
        profile: CustomerProfile,
        order: CustomerOrderMemory,
        message: object,
        facts: list[object],
    ) -> object:
        return SimpleNamespace(
            accepted=list(facts),
            proposed=[],
            conflicts=[],
            confirmation_required=[],
        )

    mock_build_history.return_value = [
        ModelRequest(parts=[SystemPromptPart(content="summary")]),
        ModelResponse(parts=[TextPart(content="Here are chair options.")]),
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=(
                        "Please recommend ergonomic chairs. "
                        "Lili, individual, 1 Dubai, lili@example.com"
                    )
                )
            ]
        ),
    ]
    mock_get_system_config.side_effect = _config
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Thanks, I saved those details.")

    with (
        patch.object(
            engine_module,
            "get_or_create_customer_profile",
            AsyncMock(return_value=profile),
        ) as mock_profile,
        patch.object(
            engine_module,
            "get_or_create_active_order",
            AsyncMock(return_value=order),
        ) as mock_order,
        patch.object(
            engine_module,
            "apply_extracted_facts",
            AsyncMock(side_effect=apply_side_effect),
        ) as mock_apply,
        patch.object(
            engine_module,
            "build_customer_facts_context",
            AsyncMock(return_value=context),
        ) as mock_context,
    ):
        response = await process_message(
            conversation_id=conv.id,
            combined_text=(
                "Please recommend ergonomic chairs. "
                "Lili, individual, 1 Dubai, lili@example.com"
            ),
            db=db,
            redis=redis,
            embedding_engine=embedding,
            zoho_client=zoho,
            messaging_client=messaging,
            crm_client=crm,
        )

    assert response.text == "Thanks, I saved those details."
    mock_profile.assert_awaited_once()
    mock_order.assert_awaited_once()
    mock_apply.assert_awaited_once()
    mock_context.assert_awaited_once()
    call_deps = mock_run.await_args.kwargs["deps"]
    assert "Known customer profile:" in call_deps.customer_facts_context
    assert conv.metadata_["quote_customer_details"] == {
        "name": "Lili",
        "email": "lili@example.com",
        "address": "1 Dubai",
        "customer_type": "individual",
    }
    trace = conv.metadata_["customer_facts"]["traces"][-1]
    assert trace["mode"] == "enforce"
    assert trace["accepted_count"] >= 4


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_customer_facts_passes_source_message_id(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
) -> None:
    db, conv, embedding, zoho, redis, messaging, crm = _deps()
    profile = CustomerProfile(canonical_phone=conv.phone, display_name="Lili")
    profile.id = uuid.uuid4()
    order = CustomerOrderMemory(
        customer_profile_id=profile.id,
        conversation_id=conv.id,
        status="active",
    )
    order.id = uuid.uuid4()
    context = CustomerFactsContext(
        profile_lines=["- Name: Lili"],
        current_order_lines=["- Quote status: active"],
        past_order_lines=[],
        missing_quote_fields=[],
    )
    mock_build_history.return_value = [
        ModelRequest(parts=[UserPromptPart(content="Lili, individual, 1 Dubai")])
    ]
    mock_get_system_config.side_effect = _config
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Saved.")

    with (
        patch.object(
            engine_module,
            "get_or_create_customer_profile",
            AsyncMock(return_value=profile),
        ),
        patch.object(
            engine_module,
            "get_or_create_active_order",
            AsyncMock(return_value=order),
        ),
        patch.object(
            engine_module,
            "apply_extracted_facts",
            AsyncMock(
                return_value=SimpleNamespace(
                    accepted=[],
                    proposed=[],
                    conflicts=[],
                    confirmation_required=[],
                )
            ),
        ) as mock_apply,
        patch.object(
            engine_module,
            "build_customer_facts_context",
            AsyncMock(return_value=context),
        ),
    ):
        await process_message(
            conversation_id=conv.id,
            combined_text="Lili, individual, 1 Dubai",
            source_message_id="msg-source-1",
            db=db,
            redis=redis,
            embedding_engine=embedding,
            zoho_client=zoho,
            messaging_client=messaging,
            crm_client=crm,
        )

    facts = mock_apply.await_args.kwargs["facts"]
    assert facts
    assert {fact.source_message_id for fact in facts} == {"msg-source-1"}


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_customer_facts_answers_past_order_query(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
) -> None:
    db, conv, embedding, zoho, redis, messaging, crm = _deps()
    profile = CustomerProfile(canonical_phone=conv.phone, display_name="Lili")
    profile.id = uuid.uuid4()
    order = CustomerOrderMemory(
        customer_profile_id=profile.id,
        conversation_id=conv.id,
        status="active",
    )
    order.id = uuid.uuid4()
    context = CustomerFactsContext(
        profile_lines=["- Name: Lili"],
        current_order_lines=["- Quote status: active"],
        past_order_lines=[
            "- Last closed order: 2026-05-22, 4 x CH 616, status accepted"
        ],
        missing_quote_fields=[],
    )
    mock_build_history.return_value = [
        ModelRequest(parts=[SystemPromptPart(content="summary")]),
        ModelRequest(parts=[UserPromptPart(content="What did I order last time?")]),
    ]
    mock_get_system_config.side_effect = _config
    mock_search_knowledge.return_value = []

    with (
        patch.object(
            engine_module,
            "get_or_create_customer_profile",
            AsyncMock(return_value=profile),
        ),
        patch.object(
            engine_module,
            "get_or_create_active_order",
            AsyncMock(return_value=order),
        ),
        patch.object(
            engine_module,
            "apply_extracted_facts",
            AsyncMock(
                return_value=SimpleNamespace(
                    accepted=[],
                    proposed=[],
                    conflicts=[],
                    confirmation_required=[],
                )
            ),
        ),
        patch.object(
            engine_module,
            "build_customer_facts_context",
            AsyncMock(return_value=context),
        ),
    ):
        response = await process_message(
            conversation_id=conv.id,
            combined_text="What did I order last time?",
            db=db,
            redis=redis,
            embedding_engine=embedding,
            zoho_client=zoho,
            messaging_client=messaging,
            crm_client=crm,
        )

    assert "previous completed order" in response.text
    assert "4 x CH 616" in response.text
    assert "previous completed order" in response.text.lower()
    mock_run.assert_not_awaited()


class _Savepoint:
    def __init__(self) -> None:
        self.entered = False
        self.rolled_back = False

    async def __aenter__(self) -> "_Savepoint":
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        self.rolled_back = exc_type is not None
        return False


class _SavepointDb:
    def __init__(self) -> None:
        self.savepoint = _Savepoint()
        self.flush = AsyncMock()

    def begin_nested(self) -> _Savepoint:
        return self.savepoint


@pytest.mark.asyncio
async def test_customer_facts_layer_fail_open_rolls_back_savepoint() -> None:
    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        customer_name="Lili",
        sales_stage=SalesStage.GREETING.value,
        language="en",
        escalation_status="none",
    )
    db = _SavepointDb()
    profile = CustomerProfile(canonical_phone=conv.phone, display_name="Lili")
    profile.id = uuid.uuid4()
    order = CustomerOrderMemory(
        customer_profile_id=profile.id,
        conversation_id=conv.id,
        status="active",
    )
    order.id = uuid.uuid4()

    with (
        patch.object(
            engine_module,
            "get_or_create_customer_profile",
            AsyncMock(return_value=profile),
        ),
        patch.object(
            engine_module,
            "get_or_create_active_order",
            AsyncMock(return_value=order),
        ),
        patch.object(
            engine_module,
            "apply_extracted_facts",
            AsyncMock(side_effect=RuntimeError("flush failed")),
        ),
    ):
        result = await engine_module._run_customer_facts_layer(
            db,  # type: ignore[arg-type]
            conversation=conv,
            text="Lili, individual, 1 Dubai",
            mode="enforce",
            trace_enabled=True,
            fast_extractor_enabled=False,
            max_context_orders=1,
        )

    assert result == engine_module.CustomerFactsRun()
    assert db.savepoint.entered is True
    assert db.savepoint.rolled_back is True
    db.flush.assert_not_awaited()
    assert conv.metadata_ is None
