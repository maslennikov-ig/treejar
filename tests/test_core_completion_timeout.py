"""A stalled completion is retried locally without replaying the agent/tools."""

import asyncio
from dataclasses import replace

import pytest
from openai.types.chat import ChatCompletion
from pydantic_ai import Agent
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.llm import safety


def completion(*, tool=False, error=False):
    choice = {
        "index": 0,
        "finish_reason": "tool_calls" if tool else "stop",
        "message": {"role": "assistant", "content": None if tool else "Done"},
    }
    if tool:
        choice["message"]["tool_calls"] = [
            {
                "id": "tool-once",
                "type": "function",
                "function": {"name": "record_once", "arguments": "{}"},
            }
        ]
    response = ChatCompletion.model_validate(
        {
            "id": "test-response",
            "created": 1,
            "model": "test/model",
            "object": "chat.completion",
            "choices": [choice],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
                "cost": 0.002,
            },
        }
    )
    if error:
        response.choices[0].finish_reason = "error"
        response.choices[0].__pydantic_extra__ = {
            "error": {"metadata": {"error_type": "provider_overloaded"}}
        }
    return response


def model():
    return safety.OpenRouterTelemetryChatModel(
        "test/model", provider=OpenRouterProvider(api_key="offline-test")
    )


async def run(agent, path=safety.PATH_CORE_CHAT, **kwargs):
    return await safety.run_agent_with_safety(
        agent,
        path,
        "Continue",
        model_name="test/model",
        notify_on_failure_override=False,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_hanging_completion_retries_same_transcript_without_replaying_tool(
    monkeypatch,
):
    monkeypatch.setattr(safety, "_CORE_CHAT_COMPLETION_TIMEOUT_SECONDS", 0.01)
    calls = []
    cancelled = []
    tool_calls = []

    async def create(self, messages, stream, settings, parameters):
        calls.append((messages, settings, parameters))
        assert self.client.max_retries == 0
        if len(calls) == 1:
            return completion(tool=True)
        if len(calls) == 2:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
        return completion()

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", create)
    original = model()
    original_sdk_retries = original.client.max_retries
    agent = Agent(original)

    @agent.tool_plain
    async def record_once():
        tool_calls.append("executed")
        return "Persisted receipt"

    result = await run(agent)
    assert result.output == "Done"
    assert tool_calls == ["executed"]
    assert cancelled == [True]
    assert len(calls) == 3
    assert calls[1][0] is calls[2][0]
    assert calls[1][1] is calls[2][1]
    assert calls[1][2] is calls[2][2]
    assert any(
        isinstance(p, ToolReturnPart) and p.content == "Persisted receipt"
        for m in calls[2][0]
        for p in m.parts
    )
    assert original.client.max_retries == original_sdk_retries
    details = result.all_messages()[-1].provider_details
    assert details["openrouter_error_retries"] == 1
    assert details["openrouter_error_type"] == "timeout"
    assert details["openrouter_retry_cost_unknown"] is True
    assert details["usage_cost_usd"] == pytest.approx(0.002)
    assert safety._CORE_CHAT_COMPLETION_DEADLINE.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failures", [("hang", "hang"), ("finish_error", "hang"), ("hang", "finish_error")]
)
async def test_timeout_and_finish_error_share_one_retry_budget(monkeypatch, failures):
    monkeypatch.setattr(safety, "_CORE_CHAT_COMPLETION_TIMEOUT_SECONDS", 0.01)
    calls = []

    async def create(*args):
        failure = failures[len(calls)]
        calls.append(failure)
        if failure == "hang":
            await asyncio.Event().wait()
        return completion(error=True)

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", create)
    with pytest.raises(safety.OpenRouterCompletionError):
        await run(Agent(model()), max_attempts_override=3)
    assert calls == list(failures)


@pytest.mark.asyncio
async def test_outer_deadline_cancels_provider_without_starting_retry(monkeypatch):
    monkeypatch.setitem(
        safety._POLICIES,
        safety.PATH_CORE_CHAT,
        replace(safety.policy_for_path(safety.PATH_CORE_CHAT), timeout_seconds=0.02),
    )
    monkeypatch.setattr(safety, "_CORE_CHAT_COMPLETION_TIMEOUT_SECONDS", 1.0)
    calls = 0
    cancellations = 0

    async def create(*args):
        nonlocal calls, cancellations
        calls += 1
        try:
            await asyncio.Event().wait()
        finally:
            cancellations += 1

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", create)
    with pytest.raises(TimeoutError):
        await run(Agent(model()))
    assert calls == cancellations == 1
    assert safety._CORE_CHAT_COMPLETION_DEADLINE.get() is None


@pytest.mark.asyncio
async def test_external_cancellation_propagates_without_retry(monkeypatch):
    entered = asyncio.Event()
    calls = 0

    async def create(*args):
        nonlocal calls
        calls += 1
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", create)
    task = asyncio.create_task(run(Agent(model())))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == 1


@pytest.mark.asyncio
async def test_other_path_keeps_existing_completion_timeout_policy(monkeypatch):
    monkeypatch.setattr(safety, "_CORE_CHAT_COMPLETION_TIMEOUT_SECONDS", 0.001)
    calls = 0

    async def create(*args):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return completion()

    monkeypatch.setattr(OpenAIChatModel, "_completions_create", create)
    assert (await run(Agent(model()), safety.PATH_CORE_FOLLOWUP)).output == "Done"
    assert calls == 1
