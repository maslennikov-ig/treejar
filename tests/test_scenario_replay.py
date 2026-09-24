"""Dry-mode coverage for the scenario replay harness (no network, no cost).

The harness drives the real `process_message` with a stub model at the
completions seam, so these tests also pin that the seam, the in-memory state and
the budget stop are wired: a regression there would make a paid live run either
unsafe or meaningless.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scenario_replay.harness import Replay, ReplayConfig  # noqa: E402

SCENARIO_B = ROOT / "tests" / "fixtures" / "scenarios" / "b_d24c5360_ch616_ch460.json"


@pytest.mark.asyncio
async def test_dry_replay_runs_every_turn_through_the_pipeline() -> None:
    receipt = await Replay(
        ReplayConfig(scenario_paths=[SCENARIO_B], mode="stub", echo=False)
    ).run()

    run = receipt["run"]
    assert run["total_cost_usd"] == 0.0
    assert run["cost_sources"] == ["stub"]
    assert run["network_blocked"] == []
    assert run["stopped_by_budget"] is None
    # The runtime's own resolution reached the seam: model and reasoning effort.
    assert run["models_called"] == ["openai/gpt-6-luna"]
    assert run["reasoning_sent"] == ['{"effort": "medium"}']

    turns = receipt["scenarios"][0]["turns"]
    assert [t["status"] for t in turns] == ["ok", "ok"]
    assert all(t["reply"] for t in turns)
    first, second = turns
    assert first["tools_called"][0]["name"] == "search_products"
    # Named SKU with local stock 0 is still found, and live Zoho stock applies.
    stock_answer = first["model_calls"][1]["tool_results"][0]["content"]
    assert "SKU: CH 616 NEW black" in stock_answer
    assert "Current stock: 1 (Zoho-confirmed)" in stock_answer
    # Deferred media selected from the final reply and sent through the audit;
    # an image already sent in turn one is not sent again in turn two.
    assert {m["sku"] for m in first["media"]} == {"CH 616 NEW black"}
    assert {m["sku"] for m in second["media"]} == {"CH 460 black"}
    assert first["media_sends"] and second["media_sends"]
    # History persists: the second turn is not an opening turn.
    assert "Noor from Treejar" in first["reply"]
    assert "Noor from Treejar" not in second["reply"]
    assert second["db"]["errors"] == []
    assert {c["type"] for c in receipt["scenarios"][0]["checks"]} == {
        "no_structured_leak",
        "no_unconfirmed_claim",
        "records_items_without_alternative",
    }
    json.dumps(receipt)


@pytest.mark.asyncio
async def test_budget_stop_happens_before_the_call() -> None:
    receipt = await Replay(
        ReplayConfig(
            scenario_paths=[SCENARIO_B],
            mode="stub",
            max_cost_usd=0.001,
            min_reserve_usd=0.002,
            echo=False,
        )
    ).run()

    run = receipt["run"]
    assert run["model_calls"] == 0
    assert run["stopped_by_budget"]
    turns = receipt["scenarios"][0]["turns"]
    assert len(turns) == 1
    assert turns[0]["status"] == "budget_stopped"
    assert turns[0]["reply"] is None
