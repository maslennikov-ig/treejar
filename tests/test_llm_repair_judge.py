"""A removal flag is resolved by a second-vendor answer, not a deletion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest

from src.core.config import settings
from src.llm.message_processor import _finalize_turn_response
from src.llm.repair_judge import (
    REPAIR_JUDGE_MODEL,
    RepairJudgeDecision,
    RepairJudgeEvidence,
    RepairJudgeProviderResult,
    RepairJudgeRequest,
    review_flagged_reply,
)
from src.llm.response_policy import ReplyGuardFlag, ReplyPolicyState, render_reply
from src.llm.response_runtime import LLMResponse, ProductMediaPayload
from src.llm.safety import PATH_RESPONSE_REPAIR_JUDGE, policy_for_path

Runner = Callable[[RepairJudgeRequest], Awaitable[RepairJudgeProviderResult]]


def _flag(*details: str) -> ReplyGuardFlag:
    return ReplyGuardFlag(
        guard_name="grounding_output",
        reason="removing_guard_triggered",
        details=details or ("unverified_customer_owned_furniture_service",),
        candidate="Buying customer-owned furniture is not a confirmed service.",
    )


def _runner(
    decision: RepairJudgeDecision,
    requests: list[RepairJudgeRequest],
) -> Runner:
    async def run(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        requests.append(request)
        return RepairJudgeProviderResult(
            decision=decision,
            model="z-ai/glm-5.2",
            prompt_tokens=120,
            completion_tokens=30,
            cost_usd=0.0012,
        )

    return run


@pytest.mark.asyncio
async def test_an_approval_sends_the_flagged_reply_unchanged_and_counts_it() -> None:
    requests: list[RepairJudgeRequest] = []
    original = "This catalog chair is model CH 140."

    result = await review_flagged_reply(
        original,
        state=ReplyPolicyState(language="en"),
        flags=(_flag("unverified_price"),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=_runner(
            RepairJudgeDecision(
                answer="approve",
                rationale="The product code is not a price.",
            ),
            requests,
        ),
    )

    assert result.text == original
    assert result.provenance == "model"
    assert result.remaining_flags == ()
    assert result.trace is not None
    assert result.trace.model == "z-ai/glm-5.2"
    assert result.trace.counts.flags == 1
    assert result.trace.counts.calls == 1
    assert result.trace.counts.approvals == 1
    assert result.trace.counts.corrections == 0
    assert result.trace.counts.cannot_fix == 0
    assert result.trace.cost_usd == 0.0012
    assert requests[0].reply == original
    assert requests[0].flags[0].candidate is not None


@pytest.mark.asyncio
async def test_an_approval_preserves_the_original_text_provenance() -> None:
    result = await review_flagged_reply(
        "A supported deterministic reply.",
        state=ReplyPolicyState(language="en"),
        flags=(_flag("false_positive"),),
        evidence=RepairJudgeEvidence(language="en"),
        provenance="deterministic_static",
        runner=_runner(
            RepairJudgeDecision(
                answer="approve",
                rationale="The flag is a false positive.",
            ),
            [],
        ),
    )

    assert result.provenance == "deterministic_static"


@pytest.mark.asyncio
async def test_a_valid_correction_is_reclassified_and_sent_as_model_written() -> None:
    requests: list[RepairJudgeRequest] = []
    original = "We can assess your used desks."
    corrected = "I can help you choose replacement desks from our catalog."

    result = await review_flagged_reply(
        original,
        state=ReplyPolicyState(language="en"),
        flags=(_flag(),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=_runner(
            RepairJudgeDecision(
                answer="correct",
                corrected_text=corrected,
                rationale="The rewrite offers a supported catalog action.",
            ),
            requests,
        ),
    )

    assert result.text == corrected
    assert result.provenance == "model_repaired"
    assert result.remaining_flags == ()
    assert result.trace is not None
    assert result.trace.counts.corrections == 1
    assert result.trace.counts.rejected_corrections == 0
    assert result.trace.requires_handoff is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("corrected_text", "rejection"),
    [
        ("   ", "empty_correction"),
        (
            "We can assess your used desks and buy them from you.",
            "correction_still_flagged",
        ),
    ],
)
async def test_an_invalid_correction_is_rejected_before_send(
    corrected_text: str,
    rejection: str,
) -> None:
    result = await review_flagged_reply(
        "We can assess your used desks.",
        state=ReplyPolicyState(language="en"),
        flags=(_flag(),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=_runner(
            RepairJudgeDecision(
                answer="correct",
                corrected_text=corrected_text,
                rationale="Attempted rewrite.",
            ),
            [],
        ),
    )

    assert result.text == "We can assess your used desks."
    assert result.provenance == "model"
    assert result.trace is not None
    assert result.trace.counts.corrections == 1
    assert result.trace.counts.rejected_corrections == 1
    assert result.trace.rejection_reason == rejection
    assert result.trace.requires_handoff is True
    assert result.remaining_flags


@pytest.mark.asyncio
async def test_cannot_fix_is_counted_and_requests_the_next_handoff_stage() -> None:
    result = await review_flagged_reply(
        "We can assess your used desks.",
        state=ReplyPolicyState(language="en"),
        flags=(_flag(),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=_runner(
            RepairJudgeDecision(
                answer="cannot_fix",
                rationale="The evidence cannot support a safe answer.",
            ),
            [],
        ),
    )

    assert result.text == "We can assess your used desks."
    assert result.trace is not None
    assert result.trace.counts.cannot_fix == 1
    assert result.trace.requires_handoff is True
    assert result.remaining_flags == (_flag(),)


@pytest.mark.asyncio
async def test_no_flag_makes_no_paid_call() -> None:
    calls = 0

    async def fail_if_called(_request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        nonlocal calls
        calls += 1
        raise AssertionError("no flag must not call the repair judge")

    result = await review_flagged_reply(
        "A safe reply.",
        state=ReplyPolicyState(language="en"),
        flags=(),
        evidence=RepairJudgeEvidence(language="en"),
        runner=fail_if_called,
    )

    assert result.text == "A safe reply."
    assert result.trace is None
    assert calls == 0


def test_response_policy_exposes_the_original_and_a_non_visible_candidate() -> None:
    original = "We can assess your used desks."

    rendered = render_reply(
        original,
        state=ReplyPolicyState(language="en"),
        provenance="model",
    )

    assert rendered.text == original
    assert [flag.guard_name for flag in rendered.flags] == ["grounding_output"]
    assert rendered.flags[0].candidate is not None
    assert rendered.flags[0].candidate != original


@pytest.mark.asyncio
async def test_turn_finalizer_is_the_single_async_customer_boundary() -> None:
    requests: list[RepairJudgeRequest] = []
    recorded: list[tuple[str, str]] = []
    state = ReplyPolicyState(language="en")
    response = LLMResponse(
        text="We can assess your used desks.",
        tokens_in=100,
        tokens_out=20,
        cost=0.002,
        model="openai/gpt-5.6-luna",
        deferred_product_media=(
            ProductMediaPayload(
                url="https://example.invalid/used-desk.jpg",
                caption="Used desk",
                product_key="used-desk",
                reference_tokens=("used desk",),
            ),
        ),
        repair_flags=(_flag(),),
        repair_policy_state=state,
    )
    turn = SimpleNamespace(
        masked_text="Can you buy my used desks?",
        pii_map={},
        deps=SimpleNamespace(executed_tool_names=()),
        _record_reply_on_conversation=lambda model, text: recorded.append(
            (model, text)
        ),
    )

    finalized = await _finalize_turn_response(
        turn,
        response,
        runner=_runner(
            RepairJudgeDecision(
                answer="correct",
                corrected_text="I can help you choose replacement desks.",
                rationale="Offer only the supported catalog path.",
            ),
            requests,
        ),
    )

    assert finalized.text == "I can help you choose replacement desks."
    assert finalized.text_provenance == "model_repaired"
    assert finalized.repair_trace is not None
    assert finalized.repair_trace.model == "z-ai/glm-5.2"
    assert finalized.repair_flags == ()
    assert finalized.deferred_product_media == ()
    assert requests[0].evidence.customer_message == "Can you buy my used desks?"
    assert recorded == [
        ("openai/gpt-5.6-luna", "I can help you choose replacement desks.")
    ]


@pytest.mark.asyncio
async def test_turn_finalizer_masks_reply_and_candidate_pii_from_the_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "pii_masking_enabled", True)
    email = "owner@example.com"
    requests: list[RepairJudgeRequest] = []

    async def correct_masked(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        requests.append(request)
        assert email not in request.reply
        assert request.flags[0].candidate is not None
        assert email not in request.flags[0].candidate
        corrected = request.reply.replace(
            "We can assess your used desks.",
            "I can help you choose replacement desks.",
        )
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text=corrected,
                rationale="Keep the supported path and the customer's contact detail.",
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    original = f"We can assess your used desks. Contact: {email}"
    response = LLMResponse(
        text=original,
        tokens_in=10,
        tokens_out=10,
        cost=0.001,
        model="openai/gpt-5.6-luna",
        repair_flags=(
            ReplyGuardFlag(
                guard_name="grounding_output",
                reason="removing_guard_triggered",
                details=("unverified_customer_owned_furniture_service",),
                candidate=f"We do not offer that service. Contact: {email}",
            ),
        ),
        repair_policy_state=ReplyPolicyState(language="en"),
    )
    recorded: list[tuple[str, str]] = []
    turn = SimpleNamespace(
        masked_text="Can you buy my used desks?",
        pii_map={},
        deps=SimpleNamespace(executed_tool_names=()),
        _record_reply_on_conversation=lambda model, text: recorded.append(
            (model, text)
        ),
    )

    finalized = await _finalize_turn_response(turn, response, runner=correct_masked)

    assert (
        finalized.text == f"I can help you choose replacement desks. Contact: {email}"
    )
    assert recorded == [("openai/gpt-5.6-luna", finalized.text)]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_unflagged_turn_records_once_without_calling_the_judge() -> None:
    calls = 0
    recorded: list[tuple[str, str]] = []

    async def fail_if_called(_request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        nonlocal calls
        calls += 1
        raise AssertionError("an unflagged turn must not call the repair judge")

    response = LLMResponse(
        text="A safe reply.",
        tokens_in=10,
        tokens_out=10,
        cost=0.001,
        model="openai/gpt-5.6-luna",
    )
    turn = SimpleNamespace(
        pii_map={},
        masked_text="Hello",
        deps=SimpleNamespace(executed_tool_names=()),
        _record_reply_on_conversation=lambda model, text: recorded.append(
            (model, text)
        ),
    )

    finalized = await _finalize_turn_response(
        turn,
        response,
        runner=fail_if_called,
    )

    assert finalized is response
    assert calls == 0
    assert recorded == [("openai/gpt-5.6-luna", "A safe reply.")]


def test_repair_judge_uses_one_bounded_second_vendor_call() -> None:
    policy = policy_for_path(PATH_RESPONSE_REPAIR_JUDGE)

    assert REPAIR_JUDGE_MODEL == "z-ai/glm-5.2"
    assert policy.scope == "non_core"
    assert policy.request_limit == 1
    assert policy.max_attempts == 1
    assert policy.temperature == 0.0


def _flagged_response_for_fallback() -> LLMResponse:
    return LLMResponse(
        text="We can assess your used desks.",
        tokens_in=10,
        tokens_out=10,
        cost=0.001,
        model="openai/gpt-5.6-luna",
        deferred_product_media=(
            ProductMediaPayload(
                url="https://example.invalid/used-desk.jpg",
                caption="Used desk",
                product_key="used-desk",
                reference_tokens=("used desk",),
            ),
        ),
        repair_flags=(_flag(),),
        repair_policy_state=ReplyPolicyState(language="en"),
    )


def _turn_for_fallback(
    recorded: list[tuple[str, str]],
    *,
    language: str = "en",
    escalation_status: str = "none",
) -> SimpleNamespace:
    return SimpleNamespace(
        masked_text="Can you buy my used desks?",
        pii_map={},
        db=object(),
        deps=SimpleNamespace(
            conversation=SimpleNamespace(
                language=language,
                escalation_status=escalation_status,
            ),
            executed_tool_names=(),
            recent_history=[],
        ),
        _record_reply_on_conversation=lambda model, text: recorded.append(
            (model, text)
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    ["cannot_fix", "rejected_correction", "provider_unavailable"],
)
async def test_repair_fallback_notifies_manager_replaces_unsafe_text_and_counts(
    outcome: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifications: list[dict[str, object]] = []

    async def notify_manager(**kwargs: object) -> None:
        notifications.append(kwargs)

    monkeypatch.setattr(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        notify_manager,
    )
    if outcome == "cannot_fix":
        runner = _runner(
            RepairJudgeDecision(
                answer="cannot_fix",
                rationale="The evidence cannot support a safe reply.",
            ),
            [],
        )
    elif outcome == "rejected_correction":
        runner = _runner(
            RepairJudgeDecision(
                answer="correct",
                corrected_text="We can assess and buy your used desks.",
                rationale="Attempted rewrite.",
            ),
            [],
        )
    else:

        async def unavailable(
            _request: RepairJudgeRequest,
        ) -> RepairJudgeProviderResult:
            raise TimeoutError("provider unavailable")

        runner = unavailable

    recorded: list[tuple[str, str]] = []
    response = _flagged_response_for_fallback()
    candidate = response.repair_flags[0].candidate

    finalized = await _finalize_turn_response(
        _turn_for_fallback(recorded),
        response,
        runner=runner,
    )

    assert len(notifications) == 1
    assert "Repair judge fallback" in str(notifications[0]["reason"])
    assert "manager" in finalized.text.lower()
    assert "We can assess your used desks." not in finalized.text
    assert candidate not in finalized.text
    assert finalized.text_provenance == "deterministic_static"
    assert finalized.repair_flags == ()
    assert finalized.deferred_product_media == ()
    assert finalized.repair_trace is not None
    assert finalized.repair_trace.counts.calls == 1
    assert finalized.repair_trace.counts.fallbacks == 1
    assert finalized.repair_trace.requires_handoff is True
    assert recorded == [("openai/gpt-5.6-luna", finalized.text)]
    if outcome == "provider_unavailable":
        assert finalized.repair_trace.answer == "unavailable"
        assert finalized.repair_trace.counts.provider_failures == 1


@pytest.mark.asyncio
async def test_repair_fallback_tells_an_arabic_customer_in_arabic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def notify_manager(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        notify_manager,
    )
    response = _flagged_response_for_fallback()
    response.repair_policy_state = ReplyPolicyState(language="ar")

    finalized = await _finalize_turn_response(
        _turn_for_fallback([], language="ar"),
        response,
        runner=_runner(
            RepairJudgeDecision(
                answer="cannot_fix",
                rationale="The evidence cannot support a safe reply.",
            ),
            [],
        ),
    )

    assert "مديرنا" in finalized.text
    assert "manager" not in finalized.text.lower()


@pytest.mark.asyncio
async def test_repair_fallback_reuses_an_active_manager_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_if_notified(**_kwargs: object) -> None:
        raise AssertionError("an active manager handoff must not be duplicated")

    monkeypatch.setattr(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        fail_if_notified,
    )

    finalized = await _finalize_turn_response(
        _turn_for_fallback([], escalation_status="pending"),
        _flagged_response_for_fallback(),
        runner=_runner(
            RepairJudgeDecision(
                answer="cannot_fix",
                rationale="The evidence cannot support a safe reply.",
            ),
            [],
        ),
    )

    assert "manager" in finalized.text.lower()
    assert finalized.repair_trace is not None
    assert finalized.repair_trace.counts.fallbacks == 1
