import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext, ToolReturn
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from src.llm.engine import (
    QuotationItem,
    SalesDeps,
    extract_exact_quote_candidate,
    inject_system_prompt,
    process_message,
    sales_agent,
)
from src.models.conversation import Conversation
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead


@pytest.fixture
def mock_deps() -> tuple[
    AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
]:
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        sales_stage=SalesStage.GREETING.value,
        language="Russian",
        escalation_status="none",
    )
    db.get.return_value = conv
    from unittest.mock import MagicMock

    from src.models.system_config import SystemConfig

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    # Mock for get_system_config
    mock_config = SystemConfig(key="openrouter_model_main", value="mock_model")
    mock_result.scalar_one_or_none.return_value = mock_config

    db.execute.return_value = mock_result  # Handles both queries

    engine = AsyncMock()
    zoho = AsyncMock()
    zoho_crm = AsyncMock()
    zoho_crm.find_contact_by_phone.return_value = {
        "id": "DEFAULT_CONTACT_ID",
        "First_Name": "Test",
        "Last_Name": "User",
        "Segment": "B2C",
    }
    redis = AsyncMock()
    redis.get.return_value = None
    messaging = AsyncMock()

    return db, conv, engine, zoho, zoho_crm, redis, messaging


def _first_turn_history(text: str) -> list[ModelRequest]:
    return [
        ModelRequest(parts=[SystemPromptPart(content="summary")]),
        ModelRequest(parts=[UserPromptPart(content=text)]),
    ]


def _split_first_turn_history(*parts: str) -> list[ModelRequest]:
    history = [ModelRequest(parts=[SystemPromptPart(content="summary")])]
    history.extend(ModelRequest(parts=[UserPromptPart(content=part)]) for part in parts)
    return history


class _FakeAgentResult:
    def __init__(
        self,
        output: str,
        *,
        input_tokens: int = 11,
        output_tokens: int = 7,
    ) -> None:
        self.output = output
        self._usage = SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def usage(self) -> SimpleNamespace:
        return self._usage


@pytest.mark.asyncio
async def test_engine_process_message_success(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    test_model = TestModel()

    with sales_agent.override(model=test_model):
        response = await process_message(
            conversation_id=conv.id,
            combined_text="Hello, what do you sell?",
            db=db,
            redis=redis,
            embedding_engine=engine,
            zoho_client=zoho,
            crm_client=zoho_crm,
            messaging_client=messaging,
        )

    assert isinstance(response.text, str)
    assert response.tokens_in is not None
    assert response.tokens_out is not None
    assert response.model.startswith("mock_model")


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_inject_system_prompt_appends_runtime_directives(
    mock_prompt: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        runtime_directives=(
            "likely concrete order handoff",
            "do not ask qualifying questions",
        ),
    )

    from pydantic_ai.usage import RunUsage

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    prompt = await inject_system_prompt(ctx)

    assert prompt.startswith("BASE PROMPT")
    assert "[RUNTIME DIRECTIVES]" in prompt
    assert "likely concrete order handoff" in prompt
    assert "do not ask qualifying questions" in prompt


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_inject_system_prompt_omits_search_requirement_in_order_handoff_mode(
    mock_prompt: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        faq_context=[{"title": "Pods", "content": "Acoustic pods are available."}],
        tool_mode="order_handoff",
        runtime_directives=("prefer manager handoff",),
    )

    from pydantic_ai.usage import RunUsage

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    prompt = await inject_system_prompt(ctx)

    assert "[KNOWLEDGE BASE (FAQ)]" in prompt
    assert "Acoustic pods are available." in prompt
    assert "MUST call the `search_products` tool" not in prompt


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_inject_system_prompt_bounds_returning_customer_context(
    mock_prompt: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        crm_context={
            "Name": "Aisha Khan",
            "Segment": "Wholesale",
            "Recent_Status": "Last quotation rejected",
            "Returning_Customer": "yes",
            "Transcript": "FULL TRANSCRIPT " + ("old message " * 80),
        },
    )

    from pydantic_ai.usage import RunUsage

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    prompt = await inject_system_prompt(ctx)

    assert "[CRM CUSTOMER CONTEXT]" in prompt
    assert "Name: Aisha Khan" in prompt
    assert "Segment: Wholesale" in prompt
    assert "Recent_Status: Last quotation rejected" in prompt
    assert "Returning_Customer: yes" in prompt
    assert "FULL TRANSCRIPT" not in prompt
    assert prompt.count("[CRM CUSTOMER CONTEXT]") == 1


@pytest.mark.asyncio
async def test_engine_process_message_db_error(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    db.get.return_value = None  # Force a not found error

    with pytest.raises(ValueError, match="Conversation .* not found"):
        await process_message(
            conversation_id=uuid.uuid4(),
            combined_text="Help",
            db=db,
            redis=redis,
            embedding_engine=engine,
            zoho_client=zoho,
            crm_client=zoho_crm,
            messaging_client=messaging,
        )


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_order_handoff_mode_limits_available_tools(
    mock_prompt: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    mock_prompt.return_value = "You are Noor."
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        tool_mode="order_handoff",
    )
    seen_tool_names: list[set[str]] = []

    def model_fn(messages: list[object], info: AgentInfo) -> object:
        seen_tool_names.append({tool.name for tool in info.function_tools})
        from pydantic_ai import ModelResponse, TextPart

        return ModelResponse(parts=[TextPart("Manager handoff queued.")])

    with sales_agent.override(model=FunctionModel(model_fn)):
        await sales_agent.run(
            "I need 200 chairs delivered to Dubai Marina by next week",
            deps=deps,
        )

    assert seen_tool_names == [{"escalate_to_manager", "update_language"}]


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_high_confidence_candidate_uses_guarded_path(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "I need 200 chairs delivered to Dubai Marina by next week"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share your budget?"),
        _FakeAgentResult("Our manager will confirm the order shortly."),
    ]

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Our manager will confirm the order shortly."
    assert mock_run.await_count == 2
    first_call = mock_run.await_args_list[0].kwargs
    second_call = mock_run.await_args_list[1].kwargs
    assert first_call["model_settings"]["max_tokens"] == 2200
    assert second_call["model_settings"]["max_tokens"] == 2200
    assert "usage_limits" not in first_call
    assert "usage_limits" not in second_call
    assert first_call["deps"].tool_mode == "order_handoff"
    assert second_call["deps"].tool_mode == "order_handoff"
    assert any(
        "likely a concrete order handoff case" in directive
        for directive in first_call["deps"].runtime_directives
    )
    assert any(
        "previous pass missed likely order handoff" in directive
        for directive in second_call["deps"].runtime_directives
    )


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_split_first_turn_still_uses_guarded_path(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "We need 200 chairs delivered to Dubai Marina by next week"
    mock_build_history.return_value = _split_first_turn_history(
        "We need 200 chairs",
        "delivered to Dubai Marina by next week",
    )
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Thanks, let me route this to our manager."),
        _FakeAgentResult("Our manager will confirm the order shortly."),
    ]

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Our manager will confirm the order shortly."
    assert mock_run.await_count == 2
    assert mock_run.await_args_list[0].kwargs["deps"].tool_mode == "order_handoff"
    assert mock_run.await_args_list[1].kwargs["deps"].tool_mode == "order_handoff"


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_resolved_status_does_not_short_circuit_guarded_path(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    conv.escalation_status = "resolved"
    text = "I need 200 chairs delivered to Dubai Marina by next week"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share the exact floor?"),
        _FakeAgentResult("Please share the exact floor."),
    ]

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 2
    assert response.text == "Please share the exact floor."


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_retries_guarded_path_once_without_hard_escalation(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "I need 200 chairs delivered to Dubai Marina by next week"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share the exact floor?"),
        _FakeAgentResult("Please share the exact floor."),
    ]

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 2
    assert conv.escalation_status == "none"
    assert response.text == "Please share the exact floor."


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_second_guarded_pass_can_succeed_with_escalation(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "I need 200 chairs delivered to Dubai Marina by next week"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def run_side_effect(*args: object, **kwargs: object) -> _FakeAgentResult:
        deps = kwargs["deps"]
        if mock_run.await_count == 1:
            return _FakeAgentResult("Could you confirm the tower name?")
        deps.conversation.escalation_status = "pending"
        return _FakeAgentResult("Our manager will confirm your order now.")

    mock_run.side_effect = run_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 2
    assert conv.escalation_status == "pending"
    assert response.text == "Our manager will confirm your order now."


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_non_candidate_uses_full_tool_mode(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "We need 20 chairs for next week, what options do you have?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Here are a few chair options.")

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Here are a few chair options."
    assert mock_run.await_count == 1
    deps = mock_run.await_args.kwargs["deps"]
    assert deps.tool_mode == "full"
    assert deps.runtime_directives == ()


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_high_risk_partial_bypasses_agent_with_handoff(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Can you install in Abu Dhabi next Tuesday?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = [
        {
            "title": "Installation coverage",
            "content": "Q: Do you offer installation?\nA: We provide delivery and installation across UAE.",
        }
    ]

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 0
    mock_notify.assert_awaited_once()
    assert conv.escalation_status == "pending"
    assert "delivery and installation across UAE" in response.text
    assert "manager" in response.text.lower()
    assert response.model == "mock-model|verified-policy"


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_high_risk_verified_uses_service_policy_mode(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "What are your delivery times in Dubai?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = [
        {
            "title": "Delivery policy",
            "content": "Q: What are your delivery times?\nA: Standard delivery takes 3-5 business days in Dubai and 5-7 business days across UAE.",
        }
    ]
    mock_run.return_value = _FakeAgentResult(
        "Standard delivery takes 3-5 business days in Dubai."
    )

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Standard delivery takes 3-5 business days in Dubai."
    assert mock_run.await_count == 1
    deps = mock_run.await_args.kwargs["deps"]
    assert deps.tool_mode == "service_policy"
    assert any(
        "verified faq support" in directive.lower()
        for directive in deps.runtime_directives
    )


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_missing_low_risk_hands_off_without_agent_run(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Do you have a showroom?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 0
    mock_notify.assert_awaited_once()
    assert conv.escalation_status == "pending"
    assert "manager" in response.text.lower()
    assert "showroom" not in response.text.lower()


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_plain_greeting_bypasses_verified_handoff(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Добрый день"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Добрый день! Я Noor, чем могу помочь?")

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_notify.await_count == 0
    assert mock_run.await_count == 1
    deps = mock_run.await_args.kwargs["deps"]
    assert deps.tool_mode == "full"
    assert "добрый день" in response.text.lower()
    assert conv.escalation_status == "none"


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
async def test_process_message_assist_opener_returns_clarification_without_handoff(
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Добрый день, подскажите"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_notify.await_count == 0
    assert "products" in response.text.lower()
    assert "delivery" in response.text.lower()
    assert conv.metadata_ == {
        "verified_policy_repair": {"kind": "benign_no_match", "count": 1}
    }
    assert conv.escalation_status == "none"


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_second_benign_no_match_escalates_after_clarification(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "I need help"
    conv.metadata_ = {"verified_policy_repair": {"kind": "benign_no_match", "count": 1}}
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 0
    mock_notify.assert_awaited_once()
    assert conv.metadata_ == {}
    assert conv.escalation_status == "pending"
    assert "manager" in response.text.lower()


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_successful_normal_path_clears_repair_state(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Thanks"
    conv.metadata_ = {"verified_policy_repair": {"kind": "benign_no_match", "count": 1}}
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("You're welcome!")

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 1
    assert response.text == "You're welcome!"
    assert conv.metadata_ == {}


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
async def test_process_message_service_handoff_deduplicates_current_user_in_recent_history(
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Do you have a showroom?"
    mock_build_history.return_value = [
        ModelRequest(parts=[SystemPromptPart(content="summary")]),
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="How can I help?")]),
        ModelRequest(parts=[UserPromptPart(content=text)]),
    ]
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    recent_messages = mock_notify.await_args.kwargs["recent_messages"]
    assert recent_messages == [
        "user: Hello",
        "assistant: How can I help?",
        "user: Do you have a showroom?",
    ]
    assert recent_messages.count("user: Do you have a showroom?") == 1


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_greeting_with_real_question_uses_service_policy(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Добрый день, есть доставка в Дубай?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 0
    mock_notify.assert_awaited_once()
    assert conv.escalation_status == "pending"
    assert "manager" in response.text.lower()


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_order_status_bypasses_faq_service_policy(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "Where is my order now?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Let me check your order status.")

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Let me check your order status."
    assert mock_run.await_count == 1
    deps = mock_run.await_args.kwargs["deps"]
    assert deps.tool_mode == "full"


@pytest.mark.asyncio
async def test_tools_search_products_marks_nearby_alternatives_explicitly(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    from datetime import UTC, datetime

    from pydantic_ai.usage import RunUsage

    import src.llm.engine as engine_module
    from src.schemas.product import ProductSearchResult

    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    mock_search = AsyncMock()
    mock_search.return_value = ProductSearchResult(
        products=[
            ProductRead(
                id=uuid.uuid4(),
                sku="POD-1",
                name_en="Meeting Booth",
                price=12000.0,
                currency="AED",
                stock=2,
                is_active=True,
                description_en="Compact acoustic booth for small meetings",
                created_at=datetime.now(UTC),
            )
        ],
        query_interpreted="acoustic pods",
        total_found=1,
    )

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    orig_search = getattr(engine_module, "rag_search_products", None)
    engine_module.rag_search_products = mock_search

    try:
        result = await engine_module.search_products(ctx, "acoustic pods")
        assert isinstance(result, ToolReturn)
        assert "meeting booth" in result.return_value.lower()
        assert "closest alternatives" in result.content.lower()
        assert (
            "do not claim that these are the exact item requested"
            in result.content.lower()
        )
    finally:
        if orig_search is not None:
            engine_module.rag_search_products = orig_search


@pytest.mark.asyncio
async def test_tools_escalate_to_manager(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """escalate_to_manager tool calls notify_manager_escalation with correct args."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: I want to speak to your manager"],
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import escalate_to_manager

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    import src.integrations.notifications.escalation as notifications

    orig_notify = notifications.notify_manager_escalation
    mock_notify = AsyncMock()
    notifications.notify_manager_escalation = mock_notify

    try:
        result = await escalate_to_manager(
            ctx, reason="Customer demanded a human", escalation_type="human_requested"
        )

        assert "Manager has been notified" in result
        mock_notify.assert_awaited_once()

        call_kwargs = mock_notify.call_args
        assert call_kwargs.kwargs["escalation_type"].value == "human_requested"
        assert call_kwargs.kwargs["reason"] == "Customer demanded a human"
        assert call_kwargs.kwargs["recent_messages"] == [
            "user: I want to speak to your manager"
        ]
    finally:
        notifications.notify_manager_escalation = orig_notify


@pytest.mark.asyncio
async def test_tools_search_products(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    from datetime import UTC, datetime

    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    # We mock search_products manually for the tool context
    from src.schemas.product import ProductSearchResult

    mock_search = AsyncMock()
    mock_search.return_value = ProductSearchResult(
        products=[
            ProductRead(
                id=uuid.uuid4(),
                sku="CHAIR-01",
                name_en="Office Chair",
                price=100.0,
                currency="USD",
                stock=5,
                is_active=True,
                description_en="A nice chair",
                created_at=datetime.now(UTC),
            )
        ],
        total_found=1,
    )

    # Patch the real function used inside the module
    import src.llm.engine as engine_module

    # Save the original
    orig_search = getattr(engine_module, "rag_search_products", None)
    engine_module.rag_search_products = mock_search

    try:
        from pydantic_ai import RunContext
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import RunUsage

        # Passing minimal dummy model and usage just to satisfy MyPy
        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="chair",
            model=TestModel(),
            usage=RunUsage(),
        )

        result = await engine_module.search_products(ctx, "chair")
        assert isinstance(result, ToolReturn)
        assert "Office Chair" in result.return_value
        assert "CHAIR-01" in result.return_value
        assert "Customer-facing catalog price: 100.00 USD" in result.return_value
        assert isinstance(result.content, str)
        assert "lead with 2-3 concrete options" in result.content.lower()
        assert "at most one targeted follow-up" in result.content.lower()
    finally:
        if orig_search:
            engine_module.rag_search_products = orig_search


@pytest.mark.asyncio
async def test_tools_search_products_caps_retries_per_run(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from src.schemas.product import ProductSearchResult

    mock_search = AsyncMock()
    mock_search.return_value = ProductSearchResult(products=[], total_found=0)

    import src.llm.engine as engine_module

    orig_search = getattr(engine_module, "rag_search_products", None)
    engine_module.rag_search_products = mock_search

    try:
        from pydantic_ai import RunContext
        from pydantic_ai.usage import RunUsage

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="acoustic pods",
            model=TestModel(),
            usage=RunUsage(),
        )

        first = await engine_module.search_products(ctx, "acoustic pods")
        second = await engine_module.search_products(ctx, "office pod")
        third = await engine_module.search_products(ctx, "phone booth")

        assert first == "No products found matching the query."
        assert isinstance(second, ToolReturn)
        assert "No products found matching the query." in second.return_value
        assert "Search limit reached for this customer message" in second.return_value
        assert isinstance(second.content, str)
        assert "offer nearby alternatives" in second.content.lower()
        assert isinstance(third, ToolReturn)
        assert "Do not call search_products again" in third.return_value
        assert mock_search.await_count == 2
    finally:
        if orig_search:
            engine_module.rag_search_products = orig_search


@pytest.mark.asyncio
async def test_tools_search_products_second_empty_result_exhausts_retry_budget(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from src.schemas.product import ProductSearchResult

    mock_search = AsyncMock()
    mock_search.return_value = ProductSearchResult(products=[], total_found=0)

    import src.llm.engine as engine_module

    orig_search = getattr(engine_module, "rag_search_products", None)
    engine_module.rag_search_products = mock_search

    try:
        from pydantic_ai import RunContext
        from pydantic_ai.usage import RunUsage

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="acoustic pods",
            model=TestModel(),
            usage=RunUsage(),
        )

        first = await engine_module.search_products(ctx, "acoustic pods")
        second = await engine_module.search_products(
            ctx, "phone booth acoustic office pod"
        )

        assert first == "No products found matching the query."
        assert isinstance(second, ToolReturn)
        assert "Search limit reached for this customer message" in second.return_value
        assert "Do not call search_products again" in second.return_value
        assert isinstance(second.content, str)
        assert "one narrow clarifying question" in second.content.lower()
        assert mock_search.await_count == 2
    finally:
        if orig_search:
            engine_module.rag_search_products = orig_search


@pytest.mark.asyncio
async def test_tools_search_products_second_successful_search_adds_catalog_fallback_contract(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    from datetime import UTC, datetime

    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from src.schemas.product import ProductSearchResult

    def _product(*, sku: str, name: str, description: str) -> ProductRead:
        return ProductRead(
            id=uuid.uuid4(),
            sku=sku,
            name_en=name,
            price=1000.0,
            currency="AED",
            stock=3,
            is_active=True,
            description_en=description,
            created_at=datetime.now(UTC),
        )

    mock_search = AsyncMock()
    mock_search.side_effect = [
        ProductSearchResult(
            products=[
                _product(
                    sku="POD-1",
                    name="Solo Privacy Booth",
                    description="Single-person focus pod",
                )
            ],
            total_found=1,
        ),
        ProductSearchResult(
            products=[
                _product(
                    sku="POD-2",
                    name="Meeting Booth",
                    description="Compact acoustic booth for 2-4 people",
                )
            ],
            total_found=1,
        ),
    ]

    import src.llm.engine as engine_module

    orig_search = getattr(engine_module, "rag_search_products", None)
    engine_module.rag_search_products = mock_search

    try:
        from pydantic_ai.usage import RunUsage

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="acoustic pods",
            model=TestModel(),
            usage=RunUsage(),
        )

        first = await engine_module.search_products(ctx, "acoustic pods")
        second = await engine_module.search_products(ctx, "meeting booth")

        assert isinstance(first, ToolReturn)
        assert isinstance(second, ToolReturn)
        assert isinstance(second.content, str)
        assert (
            "search budget for this customer message is exhausted"
            in second.content.lower()
        )
        assert "do not say that you lack catalog access" in second.content.lower()
        assert "closest alternatives" in second.content.lower()
        assert mock_search.await_count == 2
    finally:
        if orig_search:
            engine_module.rag_search_products = orig_search


@pytest.mark.asyncio
async def test_tools_advance_stage(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import advance_stage

    # Valid transition (GREETING -> QUALIFYING)
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )
    result = await advance_stage(ctx, SalesStage.QUALIFYING)

    assert "Successfully advanced" in result
    assert conv.sales_stage == SalesStage.QUALIFYING.value

    # Invalid transition (QUALIFYING -> CLOSING should fail)
    result = await advance_stage(ctx, SalesStage.CLOSING)
    assert "Cannot transition directly" in result
    assert conv.sales_stage == SalesStage.QUALIFYING.value  # Did not change


@pytest.mark.asyncio
async def test_tools_get_stock(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    zoho.get_stock.return_value = {
        "sku": "CHAIR-01",
        "stock_on_hand": 25,
        "rate": 1000.0,
        "currency_code": "AED",
    }
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    deps.product_results_seen = True
    result = await get_stock(ctx, "CHAIR-01")
    assert isinstance(result, ToolReturn)
    assert "25 items available" in result.return_value
    assert isinstance(result.content, str)
    assert (
        "treejar catalog price remains the customer-facing commercial truth"
        in result.content.lower()
    )
    zoho.get_stock.assert_awaited_once_with("CHAIR-01")


@pytest.mark.asyncio
async def test_tools_get_stock_returns_zoho_confirmed_price_and_stock(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    zoho.get_stock.return_value = {
        "sku": "CHAIR-01",
        "stock_on_hand": 7,
        "rate": 1073.0,
        "currency_code": "AED",
    }
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "CHAIR-01")

    assert isinstance(result, str)
    assert "7 items available" in result
    assert "1073.00 AED" in result


@pytest.mark.asyncio
async def test_tools_get_stock_not_found(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    zoho.get_stock.return_value = None
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "NONEXISTENT")
    assert "not found" in result


@pytest.mark.asyncio
async def test_tools_get_stock_malformed_inventory_result_is_unresolved(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    zoho.get_stock.return_value = "malformed payload"
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "CHAIR-01")

    assert "not found" in result.lower()
    assert deps.inventory_confirmed is False


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_tools_get_stock_catalog_mismatch_notifies_and_escalates(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: exact price for CHAIR-01"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    product = SimpleNamespace(
        sku="CHAIR-01",
        name_en="Exact Chair",
        attributes={"treejar_slug": "exact-chair"},
        zoho_item_id=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = product
    db.execute.return_value = execute_result
    zoho.get_stock.return_value = None

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "CHAIR-01")

    assert "couldn't confirm exact price and availability" in result.lower()
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
async def test_tools_get_stock_catalog_price_remains_customer_truth_on_zoho_rate_mismatch(
    mock_notify_mismatch: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: exact price for 00-07024023"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import get_stock

    product = SimpleNamespace(
        sku="00-07024023",
        name_en="Catalog Chair",
        price=264.0,
        currency="AED",
        attributes={"treejar_slug": "catalog-chair"},
        zoho_item_id=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = product
    db.execute.return_value = execute_result
    zoho.get_stock.return_value = {
        "sku": "00-07024023",
        "stock_on_hand": 12,
        "rate": 685.0,
        "currency_code": "AED",
    }

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "00-07024023")

    result_text = result.return_value if isinstance(result, ToolReturn) else result
    assert "12 items available" in result_text
    assert "264.00 AED" in result_text
    assert "685" not in result_text
    assert conv.metadata_["catalog_zoho_mismatches"][0]["sku"] == "00-07024023"
    mock_notify_mismatch.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.pdf.generator.generate_pdf", new_callable=AsyncMock)
@patch("src.services.pdf.generator.render_quotation_html")
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_tools_create_quotation_uses_catalog_line_rate_on_zoho_rate_mismatch(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
    mock_render_html: MagicMock,
    mock_generate_pdf: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: send quotation for 1 00-07024023"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_quotation

    product = SimpleNamespace(
        sku="00-07024023",
        name_en="Catalog Chair",
        price=264.0,
        currency="AED",
        image_url=None,
        attributes={"treejar_slug": "catalog-chair"},
        zoho_item_id=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = product
    db.execute.return_value = execute_result
    zoho.get_stock_bulk.return_value = [
        {
            "sku": "00-07024023",
            "item_id": "zoho-item-1",
            "name": "Zoho Chair",
            "description": "Operational Zoho item",
            "stock_on_hand": 12,
            "rate": 685.0,
            "currency_code": "AED",
        }
    ]
    zoho.find_customer_by_phone.return_value = {"contact_id": "contact-1"}
    zoho.create_sale_order.return_value = {
        "saleorder": {
            "salesorder_id": "so-1",
            "salesorder_number": "SO-1",
            "status": "draft",
        }
    }
    mock_render_html.return_value = "<html>quotation</html>"
    mock_generate_pdf.return_value = b"%PDF catalog rate"

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_quotation(ctx, [QuotationItem(sku="00-07024023", quantity=1)])

    assert "Quotation SO-1 has been prepared" in result
    line_items = zoho.create_sale_order.await_args.kwargs["items"]
    assert line_items[0]["rate"] == 264.0
    assert line_items[0]["rate"] != 685.0
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_tools_create_quotation_blocks_when_catalog_line_rate_override_fails(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: send quotation for 1 00-07024023"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_quotation

    product = SimpleNamespace(
        sku="00-07024023",
        name_en="Catalog Chair",
        price=264.0,
        currency="AED",
        image_url=None,
        attributes={"treejar_slug": "catalog-chair"},
        zoho_item_id=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = product
    db.execute.return_value = execute_result
    zoho.get_stock_bulk.return_value = [
        {
            "sku": "00-07024023",
            "item_id": "zoho-item-1",
            "name": "Zoho Chair",
            "description": "Operational Zoho item",
            "stock_on_hand": 12,
            "rate": 685.0,
            "currency_code": "AED",
        }
    ]
    zoho.find_customer_by_phone.return_value = {"contact_id": "contact-1"}
    zoho.create_sale_order.side_effect = RuntimeError("line rate rejected")

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_quotation(ctx, [QuotationItem(sku="00-07024023", quantity=1)])

    line_items = zoho.create_sale_order.await_args.kwargs["items"]
    assert line_items[0]["rate"] == 264.0
    assert "couldn't finalize the exact quotation automatically" in result.lower()
    redis.setex.assert_not_awaited()
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_tools_create_quotation_mixed_price_mismatch_then_catalog_only_escalates(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: send quotation for 1 00-07024023 and 1 CATALOG-ONLY"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_quotation

    price_mismatch_product = SimpleNamespace(
        sku="00-07024023",
        name_en="Catalog Chair",
        price=264.0,
        currency="AED",
        image_url=None,
        attributes={"treejar_slug": "catalog-chair"},
        zoho_item_id=None,
    )
    catalog_only_product = SimpleNamespace(
        sku="CATALOG-ONLY",
        name_en="Catalog Only Chair",
        price=199.0,
        currency="AED",
        image_url=None,
        attributes={"treejar_slug": "catalog-only-chair"},
        zoho_item_id=None,
    )

    result_a = MagicMock()
    result_a.scalar_one_or_none.return_value = price_mismatch_product
    result_b = MagicMock()
    result_b.scalar_one_or_none.return_value = catalog_only_product
    db.execute.side_effect = [result_a, result_b, result_b]
    zoho.get_stock_bulk.return_value = [
        {
            "sku": "00-07024023",
            "item_id": "zoho-item-1",
            "name": "Zoho Chair",
            "description": "Operational Zoho item",
            "stock_on_hand": 12,
            "rate": 685.0,
            "currency_code": "AED",
        }
    ]
    zoho.get_stock.return_value = None

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_quotation(
        ctx,
        [
            QuotationItem(sku="00-07024023", quantity=1),
            QuotationItem(sku="CATALOG-ONLY", quantity=1),
        ],
    )

    assert "couldn't confirm exact price and availability" in result.lower()
    zoho.create_sale_order.assert_not_awaited()
    mismatch_events = conv.metadata_["catalog_zoho_mismatches"]
    assert [event["sku"] for event in mismatch_events] == [
        "00-07024023",
        "CATALOG-ONLY",
    ]
    assert 1 <= mock_notify_mismatch.await_count <= 2
    mock_notify_manager.assert_awaited_once()
    assert (
        "could not confirm exact price/availability"
        in (mock_notify_manager.await_args.kwargs["reason"])
    )


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_tools_create_quotation_blocks_catalog_only_item_and_escalates(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
        recent_history=["user: send quotation for 1 CATALOG-ONLY"],
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_quotation

    product = SimpleNamespace(
        sku="CATALOG-ONLY",
        name_en="Catalog Only Chair",
        price=264.0,
        currency="AED",
        attributes={"treejar_slug": "catalog-only-chair"},
        zoho_item_id=None,
    )
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = product
    db.execute.return_value = execute_result
    zoho.get_stock_bulk.return_value = []
    zoho.get_stock.return_value = None

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_quotation(
        ctx, [QuotationItem(sku="CATALOG-ONLY", quantity=1)]
    )

    assert "couldn't confirm exact price and availability" in result.lower()
    zoho.create_sale_order.assert_not_awaited()
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_exact_price_request_without_quote_terms_uses_guarded_path(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "What is the exact price and availability for 1 CHAIR-01?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def run_side_effect(*args: object, **kwargs: object) -> _FakeAgentResult:
        deps = kwargs["deps"]
        if mock_run.await_count == 1:
            return _FakeAgentResult("Please share your company email.")
        deps.quotation_created = True
        return _FakeAgentResult(
            "Quotation SA-001 has been prepared and sent to the manager for review."
        )

    mock_run.side_effect = run_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert (
        response.text
        == "Quotation SA-001 has been prepared and sent to the manager for review."
    )
    assert mock_run.await_count == 2
    first_call = mock_run.await_args_list[0].kwargs
    second_call = mock_run.await_args_list[1].kwargs
    assert first_call["deps"].tool_mode == "exact_quote"
    assert second_call["deps"].tool_mode == "exact_quote"


def test_extract_exact_quote_candidate_accepts_exact_named_item_without_quote_terms() -> (
    None
):
    candidate = extract_exact_quote_candidate(
        "I need the exact price and current availability for 1 Reception desk 1600 SKYLAND LUMA 9788-8."
    )

    assert candidate is not None
    assert candidate.quantity == 1
    assert "skyland luma" in candidate.item_candidate.casefold()


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.create_quotation", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_exact_quote_second_consultative_pass_falls_back_to_direct_quotation(
    mock_run: AsyncMock,
    mock_create_quotation: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "What is the exact price and availability for 1 CHAIR-01?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share your company name?"),
        _FakeAgentResult("Please also share your company email."),
    ]

    async def create_quotation_side_effect(ctx: object, items: object) -> str:
        ctx.deps.quotation_created = True
        return "Quotation SA-001 has been prepared and sent to the manager for review."

    mock_create_quotation.side_effect = create_quotation_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert (
        response.text
        == "Quotation SA-001 has been prepared and sent to the manager for review."
    )
    assert mock_run.await_count == 2
    mock_create_quotation.assert_awaited_once()
    _, items = mock_create_quotation.await_args.args
    assert items == [QuotationItem(sku="CHAIR-01", quantity=1)]


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.create_quotation", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_exact_named_item_second_consultative_pass_resolves_to_catalog_sku(
    mock_run: AsyncMock,
    mock_create_quotation: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = (
        "I need the exact price and current availability for "
        "1 Reception desk 1600 SKYLAND LUMA 9788-8."
    )
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share your company name?"),
        _FakeAgentResult("Please also share your company email."),
    ]

    product = SimpleNamespace(
        sku="OF-HAI-Luma-Reception-RJ 9788-8-1600-Walnut",
        name_en="Reception desk 1600 SKYLAND LUMA 9788-8",
        description_en="Reception desk 1600 SKYLAND LUMA 9788-8 Walnut",
        attributes={"treejar_slug": "reception-desk-1600-skyland-luma-9788-8"},
        is_active=True,
    )
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [product]
    db.execute.return_value = execute_result

    async def create_quotation_side_effect(ctx: object, items: object) -> str:
        ctx.deps.quotation_created = True
        return "Quotation SA-009 has been prepared and sent to the manager for review."

    mock_create_quotation.side_effect = create_quotation_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert (
        response.text
        == "Quotation SA-009 has been prepared and sent to the manager for review."
    )
    assert mock_run.await_count == 2
    mock_create_quotation.assert_awaited_once()
    _, items = mock_create_quotation.await_args.args
    assert items == [
        QuotationItem(
            sku="OF-HAI-Luma-Reception-RJ 9788-8-1600-Walnut",
            quantity=1,
        )
    ]


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_exact_quote_second_consultative_pass_fails_closed_without_exact_sku(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_notify: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "I need the exact price and current availability for 1 Reception desk SKYLAND LUMA."
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.side_effect = [
        _FakeAgentResult("Could you share your company name?"),
        _FakeAgentResult("Please also share your email address."),
    ]

    async def notify_side_effect(**kwargs: object) -> None:
        kwargs["conversation"].escalation_status = "pending"

    mock_notify.side_effect = notify_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert mock_run.await_count == 2
    mock_notify.assert_awaited_once()
    assert conv.escalation_status == "pending"
    assert response.text != "Please also share your email address."
    assert "manager" in response.text.lower()


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_exact_quote_request_retries_in_exact_quote_mode(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = (
        "Please send a quotation for 1 CHAIR-01. "
        "I need the exact price and current availability."
    )
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []

    async def run_side_effect(*args: object, **kwargs: object) -> _FakeAgentResult:
        deps = kwargs["deps"]
        if mock_run.await_count == 1:
            return _FakeAgentResult("Please share your full name, company, and email.")
        deps.quotation_created = True
        return _FakeAgentResult(
            "Quotation SA-001 has been prepared and sent to the manager for review."
        )

    mock_run.side_effect = run_side_effect

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert (
        response.text
        == "Quotation SA-001 has been prepared and sent to the manager for review."
    )
    assert mock_run.await_count == 2
    first_call = mock_run.await_args_list[0].kwargs
    second_call = mock_run.await_args_list[1].kwargs
    assert first_call["deps"].tool_mode == "exact_quote"
    assert second_call["deps"].tool_mode == "exact_quote"


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_process_message_consultative_query_stays_in_full_mode(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    text = "We need 20 chairs for next week, what options do you have?"
    mock_build_history.return_value = _first_turn_history(text)
    mock_get_system_config.return_value = "mock-model"
    mock_search_knowledge.return_value = []
    mock_run.return_value = _FakeAgentResult("Here are some chair options for you.")

    response = await process_message(
        conversation_id=conv.id,
        combined_text=text,
        db=db,
        redis=redis,
        embedding_engine=engine,
        zoho_client=zoho,
        messaging_client=messaging,
    )

    assert response.text == "Here are some chair options for you."
    assert mock_run.await_count == 1
    call = mock_run.await_args_list[0].kwargs
    assert call["deps"].tool_mode == "full"


@pytest.mark.asyncio
async def test_tools_lookup_customer(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import lookup_customer

    zoho_crm.find_contact_by_phone.return_value = {
        "First_Name": "Jane",
        "Last_Name": "Doe",
        "Email": "jane@example.com",
        "Segment": "VIP",
    }
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await lookup_customer(ctx, "+971501234567")
    assert "FOUND in CRM" in result
    assert "Jane Doe" in result
    assert "jane@example.com" in result
    assert "VIP" in result
    zoho_crm.find_contact_by_phone.assert_awaited_once_with("+971501234567")


@pytest.mark.asyncio
async def test_tools_lookup_customer_not_found(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import lookup_customer

    zoho_crm.find_contact_by_phone.return_value = None
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await lookup_customer(ctx, "+971999999999")
    assert "NOT found" in result


@pytest.mark.asyncio
async def test_tools_create_deal_no_crm(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=None,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_deal

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_deal(ctx, "Test Deal", 500.0)
    assert "not available" in result


@pytest.mark.asyncio
async def test_tools_create_deal(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )
    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import create_deal

    # Mocking contact exists
    zoho_crm.find_contact_by_phone.return_value = {"id": "CONTACT123"}
    zoho_crm.create_deal.return_value = {"details": {"id": "DEAL123"}}

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await create_deal(ctx, "Test Deal", 1000.0)
    assert "DEAL123" in result
    zoho_crm.find_contact_by_phone.assert_awaited_once_with("12345")
    zoho_crm.create_deal.assert_awaited_once_with(
        {
            "Deal_Name": "Test Deal",
            "Contact_Name": {"id": "CONTACT123"},
            "Stage": "New Lead",
            "Pipeline": "Standard (Standard)",
            "Amount": 1000.0,
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_with_deal(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """check_order_status returns human-readable status when deal is linked."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = "DEAL_123"

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    # Mock CRM response
    zoho_crm.get_deal_status.return_value = {
        "id": "DEAL_123",
        "Deal_Name": "Office Chairs",
        "Stage": "Order Confirmed",
    }

    # Mock Inventory response (no sale order linked)
    zoho.get_sale_order_status = AsyncMock(return_value=None)

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)
    assert "Confirmed" in result
    zoho_crm.get_deal_status.assert_awaited_once_with("DEAL_123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_no_deal(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """check_order_status returns error when no deal is linked to conversation."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = None  # No deal linked

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)
    assert "no order" in result.lower() or "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_uses_active_metadata_sale_order_without_deal(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """check_order_status should use sale-order metadata even without a CRM deal."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = None
    conv.metadata_ = {
        "zoho_sale_order_id": "so-meta-123",
        "zoho_sale_order_number": "SO-META-123",
        "zoho_sale_order_active": True,
    }
    zoho.get_sale_order_status = AsyncMock(
        return_value={
            "salesorder_number": "SO-META-123",
            "status": "confirmed",
        }
    )
    zoho_crm.get_deal_status = AsyncMock()

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)

    assert "SO-META-123" in result
    assert "Confirmed" in result
    zoho.get_sale_order_status.assert_awaited_once_with("so-meta-123")
    zoho_crm.get_deal_status.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_approved_draft_metadata_copy(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """Approved quotation metadata should not be described as pending review."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = None
    conv.metadata_ = {
        "zoho_sale_order_id": "so-meta-123",
        "zoho_sale_order_number": "SO-META-123",
        "zoho_sale_order_active": True,
        "quotation_decision_status": "approved",
        "quotation_quote_number": "Fr3141",
    }
    zoho.get_sale_order_status = AsyncMock(
        return_value={
            "salesorder_number": "SO-META-123",
            "status": "draft",
        }
    )
    zoho_crm.get_deal_status = AsyncMock()

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)

    assert "Fr3141 approved" in result
    assert "Approved, order is being processed" in result
    assert "pending" not in result.lower()
    assert "manager review" not in result.lower()
    assert "Quotation stage" not in result
    zoho.get_sale_order_status.assert_awaited_once_with("so-meta-123")
    zoho_crm.get_deal_status.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_ignores_rejected_metadata_sale_order(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """Rejected quotation metadata should not be treated as an active order."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = None
    conv.metadata_ = {
        "zoho_sale_order_id": "so-rejected-123",
        "quotation_quote_number": "Fr3142",
        "quotation_decision": {
            "status": "rejected",
            "active": False,
            "quote_number": "Fr3142",
        },
    }
    zoho.get_sale_order_status = AsyncMock()
    zoho_crm.get_deal_status = AsyncMock()

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)

    assert "Fr3142" in result
    assert "rejected" in result.lower()
    assert "no active order" in result.lower()
    assert "pending" not in result.lower()
    assert "manager review" not in result.lower()
    zoho.get_sale_order_status.assert_not_awaited()
    zoho_crm.get_deal_status.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_no_crm(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """check_order_status works even when CRM client is unavailable."""
    db, conv, engine, zoho, _zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = "DEAL_789"

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=None,  # No CRM client
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)
    # Should still work but without CRM data
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tools_check_order_status_crm_exception(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    """check_order_status handles CRM exception gracefully and returns partial status."""
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    conv.zoho_deal_id = "DEAL_ERR"

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=redis,
    )

    # CRM throws an exception
    zoho_crm.get_deal_status.side_effect = ConnectionError("Zoho CRM unreachable")

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import check_order_status

    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await check_order_status(ctx)
    # Should not raise, should return something (may be "no order found" if no inventory data either)
    assert isinstance(result, str)
    zoho_crm.get_deal_status.assert_awaited_once_with("DEAL_ERR")
