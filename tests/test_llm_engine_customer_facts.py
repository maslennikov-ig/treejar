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
from src.models.customer_memory import CustomerOrderMemory, CustomerProfile
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
            engine_module,
            "_run_customer_facts_layer",
            AsyncMock(side_effect=AssertionError("No pre-model extraction")),
        ) as extract,
        patch.object(
            engine_module, "get_or_create_customer_profile", AsyncMock()
        ) as create_profile,
        patch.object(engine_module, "apply_extracted_facts", AsyncMock()) as apply,
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
    extract.assert_not_awaited()
    create_profile.assert_not_awaited()
    apply.assert_not_awaited()
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


@pytest.mark.asyncio
async def test_customer_facts_syncs_quote_only_fields_after_canonical_consent() -> None:
    db, conv, _embedding, _zoho, _redis, _messaging, _crm = _deps()
    conv.metadata_ = {
        "order_runtime": {
            "quote_workflow": {
                "version": 2,
                "consent": "granted",
                "lifecycle": "quote_requested",
            }
        }
    }
    facts = [
        SimpleNamespace(scope="persistent_profile", key="customer.name", value="Lili"),
        SimpleNamespace(
            scope="persistent_profile",
            key="customer.email",
            value="lili@example.com",
        ),
        SimpleNamespace(scope="current_order", key="customer.type", value="individual"),
        SimpleNamespace(scope="current_order", key="delivery.address", value="1 Dubai"),
    ]

    await engine_module._apply_customer_facts_to_legacy_quote_details(
        db,
        conv,
        facts,
    )

    assert conv.metadata_["quote_customer_details"] == {
        "name": "Lili",
        "email": "lili@example.com",
        "address": "1 Dubai",
        "customer_type": "individual",
    }


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
