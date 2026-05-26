from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LOAD_TEST_MODULE_PATH = REPO_ROOT / "scripts" / "load_test_conversations.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "scripts.load_test_conversations",
        LOAD_TEST_MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_harness_refuses_unbounded_conversation_counts() -> None:
    harness = _load_module()

    config = harness.HarnessConfig(
        conversations=harness.MAX_CONVERSATIONS + 1,
        messages_per_conversation=1,
        concurrency=1,
        processing_delay_ms=1,
    )

    with pytest.raises(ValueError, match="conversations"):
        harness.validate_limits(config)


@pytest.mark.asyncio
async def test_load_harness_reports_bounded_mocked_batch_metrics() -> None:
    harness = _load_module()

    config = harness.HarnessConfig(
        conversations=6,
        messages_per_conversation=2,
        concurrency=3,
        processing_delay_ms=1,
        ack_budget_ms=100,
        p95_budget_ms=1_000,
    )

    result = await harness.run_harness(config)

    assert result["mode"] == "local-mocked"
    assert result["conversations"] == 6
    assert result["messages"] == 12
    assert result["failed"] == 0
    assert result["max_in_flight"] <= 3
    assert result["p95_ack_ms"] <= 100
    assert result["p95_total_ms"] <= 1_000
