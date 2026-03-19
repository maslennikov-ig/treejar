import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel

from src.core.escalation import escalation_agent
from src.llm.engine import SalesDeps, process_message, sales_agent
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


@pytest.mark.asyncio
async def test_engine_process_message_success(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps

    # We use `test_model` from pydantic-ai to mock responses without hitting an API
    test_model = TestModel()

    # We inject the test model via the `override` context manager
    with (
        sales_agent.override(model=test_model),
        escalation_agent.override(
            model=TestModel(
                custom_output_args={"should_escalate": False, "reason": None}
            )
        ),
    ):
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
async def test_engine_process_message_with_escalation(
    mock_deps: tuple[
        AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
    ],
) -> None:
    db, conv, engine, zoho, zoho_crm, redis, messaging = mock_deps
    from src.schemas.common import EscalationStatus

    assert conv.escalation_status == EscalationStatus.NONE.value

    test_model = TestModel()

    # We patch the escalation_agent to force a positive hit
    import src.core.escalation as core_escalation
    import src.integrations.notifications.escalation as notifications

    # Save original functions
    orig_eval = core_escalation.evaluate_escalation_triggers
    orig_notify = notifications.notify_manager_escalation

    # Mock them
    mock_eval = AsyncMock(
        return_value=core_escalation.EscalationEvaluation(
            should_escalate=True, reason="Test Escalation"
        )
    )

    from typing import Any

    async def side_effect(
        conv_obj: Any, reason: Any, context: Any, session: Any
    ) -> None:
        conv_obj.escalation_status = EscalationStatus.PENDING.value

    mock_notify = AsyncMock(side_effect=side_effect)

    core_escalation.evaluate_escalation_triggers = mock_eval
    notifications.notify_manager_escalation = mock_notify

    try:
        with sales_agent.override(model=test_model):
            _response = await process_message(
                conversation_id=conv.id,
                combined_text="I want to speak to your manager right now!",
                db=db,
                redis=redis,
                embedding_engine=engine,
                zoho_client=zoho,
                crm_client=zoho_crm,
                messaging_client=messaging,
            )

        # Verify internal flow
        mock_eval.assert_awaited_once()
        mock_notify.assert_awaited_once()

        # Verify the dependency injection correctly updated DB object
        assert conv.escalation_status == EscalationStatus.PENDING.value

    finally:
        # Restore
        core_escalation.evaluate_escalation_triggers = orig_eval
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

        result_text = await engine_module.search_products(ctx, "chair")
        assert "Office Chair" in result_text
        assert "CHAIR-01" in result_text
        assert "100.00 USD (Your segment price)" in result_text
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

    zoho.get_stock.return_value = {"stock_on_hand": 25}
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    result = await get_stock(ctx, "CHAIR-01")
    assert "25 items available" in result
    zoho.get_stock.assert_awaited_once_with("CHAIR-01")


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
