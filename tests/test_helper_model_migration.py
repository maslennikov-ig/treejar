"""Exercise the real SDK payload and preserved controls without provider calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.llm.fact_extractor import FastCustomerFactExtractionOutput
from src.llm.repair_judge import RepairJudgeDecision
from src.llm.safety import (
    OpenRouterTelemetryChatModel,
    model_settings_for_path,
    policy_for_path,
    run_agent_with_safety,
)
from src.quality.config import AIQualityControlsConfig, parse_ai_quality_controls
from src.quality.schemas import RedFlagEvaluationResult


@pytest.mark.parametrize(
    ("path", "model", "output_type", "answer"),
    [
        (
            "fact_extraction",
            "openai/gpt-6-luna",
            FastCustomerFactExtractionOutput,
            {"facts": [], "trace_note": "No facts in synthetic input."},
        ),
        (
            "response_repair_judge",
            "openai/gpt-6.1-terra",
            RepairJudgeDecision,
            {"answer": "approve", "rationale": "Synthetic reply is supported."},
        ),
        (
            "quality_red_flags",
            "openai/gpt-6.1-terra",
            RedFlagEvaluationResult,
            {"flags": [], "recommended_action": ""},
        ),
    ],
)
@pytest.mark.asyncio
async def test_bounded_helper_sdk_structured_output_without_network(
    path: str,
    model: str,
    output_type: type,
    answer: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.llm.safety.notify_llm_safety_event", AsyncMock())
    payloads: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        function = payload["tools"][0]["function"]
        assert function["parameters"]["properties"]
        return httpx.Response(
            200,
            json={
                "id": "synthetic-helper-generation",
                "created": 1,
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "synthetic-result",
                                    "type": "function",
                                    "function": {
                                        "name": function["name"],
                                        "arguments": json.dumps(answer),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(
            openai_client=AsyncOpenAI(
                api_key="fake-test-key",
                base_url="https://openrouter.invalid/api/v1",
                http_client=client,
                max_retries=0,
            )
        )
        agent = Agent(
            OpenRouterTelemetryChatModel(
                model,
                provider=provider,
                settings=model_settings_for_path(path, model_name=model),
            ),
            output_type=output_type,
            retries=0,
        )
        result = await run_agent_with_safety(
            agent, path, "Synthetic input.", model_name=model
        )

    assert result.output == output_type.model_validate(answer)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["model"] == model
    assert payload["reasoning"] == {"effort": "none"}
    assert "temperature" not in payload
    assert payload.get("max_tokens", payload.get("max_completion_tokens")) == (
        policy_for_path(path).max_tokens
    )


def test_quality_models_change_without_enabling_any_scope() -> None:
    default = AIQualityControlsConfig()
    for scope in (default.bot_qa, default.manager_qa, default.red_flags):
        assert scope.model == "openai/gpt-6.1-terra"
        assert scope.mode == "disabled"
    stored = parse_ai_quality_controls(
        {
            "bot_qa": {
                "mode": "disabled",
                "model": "custom/model",
                "max_calls_per_day": 0,
            }
        }
    )
    assert stored.bot_qa.model == "custom/model"
    assert stored.bot_qa.mode == "disabled"
    assert stored.bot_qa.max_calls_per_day == 0
