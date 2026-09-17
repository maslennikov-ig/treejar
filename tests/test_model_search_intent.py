"""Model-selected search constraints survive conflicting customer keywords."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm import engine
from src.models.conversation import Conversation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_text",
    [
        "No privacy panels, only open desks",
        "Do not show 10 options. I only need one desk, not 4 seats.",
        "Not interested in assembly. Compare open desks.",
    ],
)
async def test_search_does_not_reinterpret_the_model_query(user_text):
    deps = engine.SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=Conversation(
            id=uuid4(), phone="test", language="en", metadata_={}
        ),
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=None,
        messaging_client=AsyncMock(),
        pii_map={},
        user_query=user_text,
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage(), prompt=user_text)
    with patch.object(
        engine,
        "rag_search_products",
        AsyncMock(return_value=SimpleNamespace(products=[])),
    ) as search:
        await engine.search_products(ctx, query="open desks", max_results=2)
    selected = search.await_args.kwargs["query"]
    assert selected.query == "open desks"
    assert selected.limit == 2
    assert deps.catalog_planning.requested_seats is None
    assert not deps.catalog_planning.complete_coverage
    deps.zoho_inventory.get_stock_bulk.assert_not_awaited()
