from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest


class _FakeRunResult:
    output = "ok"

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=10, output_tokens=5)


@pytest.mark.parametrize(
    ("path", "expected_max_tokens"),
    [
        ("core_chat", 2200),
        ("core_followup", 500),
        ("quality_final", 2500),
        ("quality_red_flags", 900),
        ("quality_manager", 2000),
        ("conversation_summary", 900),
        ("response_adapter", 700),
        ("auto_faq_translate", 700),
    ],
)
def test_llm_path_policy_sets_expected_provider_max_tokens(
    path: str,
    expected_max_tokens: int,
) -> None:
    from src.llm.safety import model_settings_for_path

    assert model_settings_for_path(path)["max_tokens"] == expected_max_tokens


@pytest.mark.asyncio
async def test_run_agent_with_safety_passes_non_core_settings_and_limits() -> None:
    from src.llm.safety import run_agent_with_safety

    agent = SimpleNamespace(run=AsyncMock(return_value=_FakeRunResult()))

    await run_agent_with_safety(
        agent,
        "quality_red_flags",
        "prompt",
        model_name="fast-model",
    )

    kwargs = agent.run.await_args.kwargs
    assert kwargs["model_settings"]["max_tokens"] == 900
    assert kwargs["usage_limits"].request_limit == 1
    assert kwargs["usage_limits"].output_tokens_limit == 900
    assert kwargs["usage_limits"].total_tokens_limit == 4000


@pytest.mark.asyncio
async def test_run_agent_with_safety_retries_non_core_once_total() -> None:
    from src.llm.safety import run_agent_with_safety

    agent = SimpleNamespace(
        run=AsyncMock(
            side_effect=[
                httpx.ConnectError("temporary provider failure"),
                _FakeRunResult(),
            ]
        )
    )

    result = await run_agent_with_safety(
        agent,
        "response_adapter",
        "prompt",
        model_name="fast-model",
    )

    assert result.output == "ok"
    assert agent.run.await_count == 2


@pytest.mark.asyncio
async def test_run_agent_with_safety_final_failure_notifies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.llm import safety

    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(
        run=AsyncMock(side_effect=httpx.ConnectError("provider unavailable"))
    )

    with pytest.raises(httpx.ConnectError):
        await safety.run_agent_with_safety(
            agent,
            "conversation_summary",
            "prompt",
            model_name="fast-model",
        )

    assert agent.run.await_count == 2
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event"] == "final_failure"


@pytest.mark.asyncio
async def test_budget_block_prevents_non_core_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm import safety

    monkeypatch.setattr(settings, "llm_non_core_budget_blocked", True)
    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(run=AsyncMock(return_value=_FakeRunResult()))

    with pytest.raises(safety.LLMBudgetBlocked):
        await safety.run_agent_with_safety(
            agent,
            "quality_final",
            "prompt",
            model_name="main-model",
        )

    agent.run.assert_not_awaited()
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["event"] == "budget_blocked"


@pytest.mark.asyncio
async def test_core_path_does_not_get_outer_retry_or_budget_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.config import settings
    from src.llm import safety

    monkeypatch.setattr(settings, "llm_non_core_budget_blocked", True)
    notify = AsyncMock()
    monkeypatch.setattr(safety, "notify_llm_safety_event", notify)
    agent = SimpleNamespace(run=AsyncMock(side_effect=RuntimeError("core failure")))

    with pytest.raises(RuntimeError, match="core failure"):
        await safety.run_agent_with_safety(
            agent,
            "core_chat",
            "prompt",
            model_name="main-model",
        )

    assert agent.run.await_count == 1
    kwargs = agent.run.await_args.kwargs
    assert kwargs["model_settings"]["max_tokens"] == 2200
    assert "usage_limits" not in kwargs
    notify.assert_awaited_once()
