"""Native tool scheduling serializes access to the shared sales session."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from src.dialogue.state import DialogueState
from src.llm import engine
from tests.test_model_search_intent import _context


def test_all_registered_sales_tools_require_sequential_execution():
    tools = engine.sales_agent._function_toolset.tools
    assert tools
    assert all(tool.sequential for tool in tools.values())


@pytest.mark.asyncio
async def test_parallel_model_requests_do_not_overlap_shared_database_work():
    ctx = _context("Check NOVO and record my budget")
    active = 0
    peak = 0
    events = []

    async def database_work(label):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        events.append(f"start:{label}")
        await asyncio.sleep(0)
        events.append(f"end:{label}")
        active -= 1

    async def lookup(db, sku):
        await database_work("read")
        return None

    async def flush():
        await database_work("write")

    ctx.deps.db = SimpleNamespace(flush=flush)
    ctx.deps.zoho_inventory.get_stock.return_value = {
        "sku": "NOVO",
        "stock_on_hand": 3,
        "rate": 250,
        "currency_code": "AED",
    }

    def model(messages, info):
        completed = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not completed:
            # The model chooses both calls in one response; their arguments and
            # requested actions are preserved while native scheduling serializes IO.
            return ModelResponse(
                parts=[
                    ToolCallPart("get_stock", {"sku": "NOVO"}),
                    ToolCallPart(
                        "record_customer_requirements", {"budget_cap_aed": 7000}
                    ),
                ]
            )
        assert {part.tool_name for part in completed} == {
            "get_stock",
            "record_customer_requirements",
        }
        return ModelResponse(parts=[TextPart("Checked and recorded.")])

    registered = engine.sales_agent._function_toolset.tools
    agent = Agent(
        FunctionModel(model),
        deps_type=engine.SalesDeps,
        tools=[registered["get_stock"], registered["record_customer_requirements"]],
    )
    with patch.object(engine, "_find_catalog_product_by_sku", lookup):
        result = await agent.run(ctx.deps.user_query, deps=ctx.deps)
    assert result.output == "Checked and recorded."
    assert peak == 1
    assert events == ["start:read", "end:read", "start:write", "end:write"]
    assert (
        DialogueState.from_conversation(ctx.deps.conversation).slots.budget_cap_aed
        == 7000
    )
