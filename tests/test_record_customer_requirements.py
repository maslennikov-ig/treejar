"""Model-selected replacements/removals preserve validated state atomically."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dialogue.state import DialogueState
from src.llm import engine
from tests.test_customer_intent_tools import context


def selected_context():
    ctx = context("Replace LUMA with NOVO")
    state = DialogueState.from_conversation(ctx.deps.conversation)
    state.slots.selected_items = [{"sku": "LUMA", "quantity": 2}]
    state.slots.budget_cap_aed = 7000.0
    ctx.deps.conversation.metadata_ = state.to_metadata({"unrelated": "preserved"})
    return ctx


@pytest.mark.asyncio
async def test_replacement_removes_previous_choice_and_preserves_other_requirements(
    monkeypatch,
):
    ctx = selected_context()
    monkeypatch.setattr(
        engine,
        "_find_catalog_product_by_sku",
        AsyncMock(return_value=SimpleNamespace(sku="NOVO")),
    )
    result = await engine.record_customer_requirements(
        ctx, items=[engine.RecordedItem(sku="NOVO", quantity=3)], replace_items=True
    )
    slots = DialogueState.from_conversation(ctx.deps.conversation).slots
    assert slots.selected_items == [{"sku": "NOVO", "quantity": 3}]
    assert slots.budget_cap_aed == 7000.0
    assert ctx.deps.conversation.metadata_["unrelated"] == "preserved"
    assert "Recorded:" in result


@pytest.mark.asyncio
async def test_invalid_replacement_does_not_clear_or_partially_replace_selection(
    monkeypatch,
):
    ctx = selected_context()
    before = deepcopy(ctx.deps.conversation.metadata_)
    monkeypatch.setattr(
        engine,
        "_find_catalog_product_by_sku",
        AsyncMock(side_effect=[SimpleNamespace(sku="NOVO"), None]),
    )
    result = await engine.record_customer_requirements(
        ctx,
        items=[
            engine.RecordedItem(sku="NOVO", quantity=3),
            engine.RecordedItem(sku="INVENTED", quantity=1),
        ],
        replace_items=True,
        budget_cap_aed=9000,
    )
    assert result.startswith("Not recorded")
    assert ctx.deps.conversation.metadata_ == before
    ctx.deps.db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_removal_rejects_unknown_sku_then_clears_selected_line():
    ctx = selected_context()
    before = deepcopy(ctx.deps.conversation.metadata_)
    result = await engine.record_customer_requirements(ctx, remove_skus=["UNKNOWN"])
    assert result.startswith("Not recorded")
    assert ctx.deps.conversation.metadata_ == before
    result = await engine.record_customer_requirements(ctx, remove_skus=["LUMA"])
    assert "Recorded:" in result
    assert (
        DialogueState.from_conversation(ctx.deps.conversation).slots.selected_items
        == []
    )


@pytest.mark.asyncio
async def test_failed_flush_rolls_back_metadata_and_does_not_report_success():
    ctx = selected_context()
    before = deepcopy(ctx.deps.conversation.metadata_)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=False)
    ctx.deps.db.begin_nested = MagicMock(return_value=transaction)
    ctx.deps.db.flush.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await engine.record_customer_requirements(ctx, replace_items=True)
    assert ctx.deps.conversation.metadata_ == before
    assert transaction.__aexit__.await_args.args[0] is RuntimeError
