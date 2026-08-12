"""A removal flag is resolved by a second-vendor answer, not a deletion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import httpx
import pytest
from pydantic_ai import UnexpectedModelBehavior

from src.core.config import settings
from src.llm.message_processor import _finalize_turn_response
from src.llm.repair_judge import (
    REPAIR_JUDGE_ATTEMPTS,
    REPAIR_JUDGE_MODEL,
    REPAIR_JUDGE_PROMPT,
    RepairJudgeDecision,
    RepairJudgeEvidence,
    RepairJudgeProviderResult,
    RepairJudgeRequest,
    classify_repair_failure,
    review_flagged_reply,
)
from src.llm.response_policy import ReplyGuardFlag, ReplyPolicyState, render_reply
from src.llm.response_runtime import LLMResponse, ProductMediaPayload
from src.llm.safety import (
    PATH_CORE_CHAT,
    PATH_RESPONSE_REPAIR_JUDGE,
    model_settings_for_path,
    policy_for_path,
)

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

    assert REPAIR_JUDGE_MODEL == "deepseek/deepseek-v4-flash"
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
    assert finalized.repair_trace.counts.fallbacks == 1
    assert finalized.repair_trace.requires_handoff is True
    assert recorded == [("openai/gpt-5.6-luna", finalized.text)]
    if outcome == "provider_unavailable":
        # A failing call is retried once before the customer loses the reply,
        # and both attempts are counted because both are paid.
        assert finalized.repair_trace.answer == "unavailable"
        assert finalized.repair_trace.counts.calls == 2
        assert finalized.repair_trace.counts.retries == 1
        assert finalized.repair_trace.counts.provider_failures == 2
        assert finalized.repair_trace.rejection_reason == "provider_unavailable"
        assert finalized.repair_trace.error_type == "TimeoutError"
    else:
        # An answered call is not retried, whatever the answer was.
        assert finalized.repair_trace.counts.calls == 1
        assert finalized.repair_trace.counts.retries == 0


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


# --- what failed, and whether it was worth asking twice --------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("slow"), "provider_unavailable"),
        (httpx.ConnectError("refused"), "provider_unavailable"),
        (UnexpectedModelBehavior("no tool call"), "judge_output_invalid"),
        (ValueError("ours"), "judge_call_failed"),
        (None, "judge_call_failed"),
    ],
)
def test_a_failed_repair_names_whose_fault_it_was(
    error: BaseException | None, expected: str
) -> None:
    """The round of 2026-08-11 recorded `provider_unavailable` for an exception
    nobody had classified, so it could not say whether GLM was down or our own
    schema had rejected a good reply. Those need different fixes."""

    assert classify_repair_failure(error) == expected


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_once_and_then_answered() -> None:
    """One hiccup should not cost the customer their reply."""

    attempts = 0

    async def flaky(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("first attempt")
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="approve", rationale="Supported by the evidence."
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    judged = await review_flagged_reply(
        "A supported reply.",
        state=ReplyPolicyState(language="en"),
        flags=(_flag(),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=flaky,
    )

    assert attempts == 2
    assert judged.text == "A supported reply."
    assert judged.remaining_flags == ()
    assert judged.trace is not None
    assert judged.trace.answer == "approve"
    assert judged.trace.counts.calls == 2
    assert judged.trace.counts.retries == 1
    assert judged.trace.requires_handoff is False


@pytest.mark.asyncio
async def test_the_retry_is_bounded_so_a_dead_provider_cannot_hold_the_turn() -> None:
    """Two attempts, not a loop. The customer is waiting on this call."""

    attempts = 0

    async def dead(_request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("refused")

    judged = await review_flagged_reply(
        "A flagged reply.",
        state=ReplyPolicyState(language="en"),
        flags=(_flag(),),
        evidence=RepairJudgeEvidence(language="en"),
        runner=dead,
    )

    assert attempts == REPAIR_JUDGE_ATTEMPTS == 2
    assert judged.trace is not None
    assert judged.trace.counts.calls == 2
    assert judged.trace.counts.provider_failures == 2
    assert judged.trace.rejection_reason == "provider_unavailable"
    assert judged.trace.error_type == "ConnectError"
    assert judged.trace.requires_handoff is True


def test_the_repair_budget_belongs_to_the_whole_repair_not_one_call() -> None:
    """Two attempts must not double what the customer waits.

    The path timeout is the per-call budget, so it was halved in the same
    change that added the second attempt. The safety layer keeps
    `max_attempts=1` because the retry lives where the paid-call cap can see
    each try.
    """

    policy = policy_for_path(PATH_RESPONSE_REPAIR_JUDGE)

    assert policy.max_attempts == 1
    assert policy.timeout_seconds * REPAIR_JUDGE_ATTEMPTS <= 45.0


def test_the_repair_judge_can_afford_the_answer_it_asks_for() -> None:
    """The budget is measured against the request that actually failed.

    Dialog 819's repair call was replayed twelve times on 2026-08-12. A
    complete answer costs 720-1494 completion tokens: roughly 300 are the JSON
    the schema wants, and the rest is reasoning GLM 5.2 bills for and never
    returns. 800 could not hold it once, 1200 held it twice in four, and every
    failure was the output schema rejecting a truncated answer -- the provider
    was up the whole time.

    `reasoning_enabled` stays declared because the intent is right and the
    vendor may honour it later, but it did not fix this and must not be
    mistaken for the fix: `enabled: false`, `effort: low` and
    `max_tokens: 256` all left completion around 1430 tokens on GLM. Thinking
    that cannot be declined has to be afforded. The path now runs DeepSeek
    Flash at roughly 270 tokens, and the ceiling stays where a reasoning model
    would still fit, because starving this call is a failure we already paid
    for once.
    """

    policy = policy_for_path(PATH_RESPONSE_REPAIR_JUDGE)
    body = model_settings_for_path(
        PATH_RESPONSE_REPAIR_JUDGE, model_name=REPAIR_JUDGE_MODEL
    )["extra_body"]

    assert policy.reasoning_enabled is False
    assert body["reasoning"] == {"enabled": False}
    assert policy.max_tokens >= 2000
    assert policy.output_tokens_limit is not None
    assert policy.output_tokens_limit >= 2000
    # The observed worst case must still fit under the per-call timeout, and
    # 1494 tokens took 15.3s of the 20s allowed.
    assert policy.timeout_seconds >= 20.0


def test_the_repair_prompt_states_the_rule_we_actually_enforce() -> None:
    """The judge was graded on a criterion the prompt never gave it.

    `review_flagged_reply` re-renders every correction and discards it whole if
    a flag survives. The old prompt asked for "every flag resolved" and stopped
    there, so a judge that reworded the flagged promise lost the customer the
    entire reply and was never told why -- and `cannot_fix` read like the
    cautious choice when it is the one that sends nothing. Replaying dialog 819
    on 2026-08-12, one reply in four reached the customer on either vendor.
    With the re-check stated and `cannot_fix` priced, four in four on both.

    Asserting on prose is brittle by nature. It is pinned anyway because these
    two sentences are worth three quarters of the deliveries, and losing them
    to a tidy-up would look exactly like nothing.
    """

    prompt = REPAIR_JUDGE_PROMPT.lower()

    assert "reads your answer again" in prompt
    assert "discarded" in prompt
    assert "last resort" in prompt


def test_the_repair_judge_is_not_the_model_that_wrote_the_reply() -> None:
    """A judge sharing a model with the writer is grading itself.

    The path moved to the fast model on 2026-08-12, which is also what polishes
    manager drafts from Telegram -- a different flow this path never sees. The
    thing that must stay true is that it is not the customer-facing model.
    """

    assert settings.openrouter_model_main != REPAIR_JUDGE_MODEL


def test_a_path_that_says_nothing_about_reasoning_leaves_the_provider_alone() -> None:
    body = model_settings_for_path(PATH_CORE_CHAT, model_name="openai/gpt-5.6-luna")

    assert policy_for_path(PATH_CORE_CHAT).reasoning_enabled is None
    assert "reasoning" not in dict(body.get("extra_body") or {})
