import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel

from src.llm.engine import SalesDeps, process_message, sales_agent
from src.models.conversation import Conversation
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead


@pytest.fixture
def mock_deps() -> tuple[AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        sales_stage=SalesStage.GREETING.value,
        language="Russian",
    )
    db.get.return_value = conv
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result  # Empty history

    engine = AsyncMock()
    zoho = AsyncMock()
    zoho_crm = AsyncMock()
    redis = AsyncMock()

    return db, conv, engine, zoho, zoho_crm, redis


@pytest.mark.asyncio
async def test_engine_process_message_success(mock_deps: tuple[AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock]) -> None:
    db, conv, engine, zoho, zoho_crm, redis = mock_deps

    # We use `test_model` from pydantic-ai to mock responses without hitting an API
    test_model = TestModel()

    # We inject the test model via the `override` context manager
    with sales_agent.override(model=test_model):
        response = await process_message(
            conversation_id=conv.id,
            combined_text="Hello, what do you sell?",
            db=db,
            redis=redis,
            embedding_engine=engine,
            zoho_client=zoho,
            crm_client=zoho_crm,
        )

    assert isinstance(response.text, str)
    assert response.tokens_in is not None
    assert response.tokens_out is not None
    from src.core.config import settings
    assert response.model == settings.openrouter_model_main


@pytest.mark.asyncio
async def test_engine_process_message_db_error(mock_deps: tuple[AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock]) -> None:
    db, conv, engine, zoho, zoho_crm, redis = mock_deps
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
        )


@pytest.mark.asyncio
async def test_tools_search_products(mock_deps: tuple[AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock]) -> None:
    from datetime import UTC, datetime
    db, conv, engine, zoho, zoho_crm, redis = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        pii_map={},
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
                created_at=datetime.now(UTC)
            )
        ],
        total_found=1
    )

    # Patch the real function used inside the module
    import src.llm.engine as engine_module

    # Save the original
    orig_search = getattr(engine_module, "search_products", None)
    engine_module.search_products = mock_search  # type: ignore

    try:
        from pydantic_ai import RunContext
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import RunUsage

        # Passing minimal dummy model and usage just to satisfy MyPy
        ctx = RunContext(deps=deps, retry=0, messages=[], prompt="chair", model=TestModel(), usage=RunUsage())

        result_text = await engine_module.perform_search_products(ctx, "chair")
        assert "Office Chair" in result_text
        assert "CHAIR-01" in result_text
        assert "100.0 USD" in result_text
    finally:
        if orig_search:
            engine_module.search_products = orig_search  # type: ignore


@pytest.mark.asyncio
async def test_tools_advance_stage(mock_deps: tuple[AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock]) -> None:
    db, conv, engine, zoho, zoho_crm, redis = mock_deps
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        pii_map={},
    )

    from pydantic_ai import RunContext
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import advance_stage

    # Valid transition (GREETING -> QUALIFYING)
    ctx = RunContext(deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage())
    result = await advance_stage(ctx, SalesStage.QUALIFYING)

    assert "Successfully advanced" in result
    assert conv.sales_stage == SalesStage.QUALIFYING.value

    # Invalid transition
    result = await advance_stage(ctx, SalesStage.CLOSING)
    assert "Cannot transition directly" in result
    assert conv.sales_stage == SalesStage.QUALIFYING.value  # Did not change
