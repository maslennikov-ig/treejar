"""The real-opening acceptance round is complete, bounded, and text-safe."""

from __future__ import annotations

import inspect
import json
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from scripts.corpus_bridge.real_opening_acceptance import (
    GENERATOR_MODEL,
    REPAIR_JUDGE_CALL_CAP,
    REPAIR_JUDGE_MODEL,
    ROOT_JUDGE,
    _load_frozen_scenarios,
    _parse_args,
    apply_shipped_output_guards,
    build_generation_messages,
    build_public_summary,
    catalog_matches,
    critical_failure_codes,
    ensure_protected_output,
    estimate_cost_usd,
    expected_language,
    find_ungrounded_numbers,
    preflight,
    run_paid_round,
    validate_complete_results,
)

from src.llm.message_processor import _finalize_turn_response
from src.llm.repair_judge import (
    RepairJudgeDecision,
    RepairJudgeProviderResult,
    RepairJudgeRequest,
)
from src.llm.response_policy import (
    ReplyPolicyState,
    format_permitted_asks_prompt,
    permitted_asks_for_turn,
    render_reply,
)
from src.llm.response_runtime import LLMResponse


def _result(
    dialog_id: int, *, score: float = 20.0, attainable: float = 30.0
) -> dict[str, object]:
    return {
        "dialog_id": dialog_id,
        "length_stratum": (dialog_id - 1) // 5 + 1,
        "opening": f"private opener {dialog_id}",
        "response": f"private response {dialog_id}",
        "generator_model": "openai/gpt-5.6-luna",
        "judge_model": "z-ai/glm-5.2",
        "latency_ms": 1000 + dialog_id,
        "luna_latency_ms": 700 + dialog_id,
        "glm_latency_ms": 300,
        "prompt_tokens": 100 + dialog_id,
        "completion_tokens": 20 + dialog_id,
        "cost_micro_usd": 10 + dialog_id,
        "weighted_score": score,
        "attainable_score": attainable,
        "raw_total": 8,
        "language_ok": True,
        "critical_failures": [],
    }


def test_protected_output_refuses_the_working_tree(tmp_path: pathlib.Path) -> None:
    """Catch a future caller placing transcript-bearing output below Git."""
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="outside the repository"):
        ensure_protected_output(repo / "evidence", repo_root=repo)

    protected = ensure_protected_output(
        repo / ".git" / "codex-orchestration" / "evidence",
        repo_root=repo,
    )
    assert protected.is_dir()
    assert protected.stat().st_mode & 0o777 == 0o700


def test_frozen_scenarios_require_the_recorded_seed_and_balanced_strata(
    tmp_path: pathlib.Path,
) -> None:
    """Catch a different convenience sample being substituted at run time."""
    path = tmp_path / "scenarios.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 9,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="selection seed"):
        _load_frozen_scenarios(path)


def test_complete_results_require_each_frozen_dialog_once() -> None:
    """Catch a missing or duplicated paid arm being reported as 20/20."""
    results = [_result(dialog_id) for dialog_id in range(1, 20)]

    with pytest.raises(ValueError, match="exactly the frozen dialog ids"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))


def test_public_summary_contains_no_opening_or_response_text() -> None:
    """Catch private corpus text leaking through the tracked summary."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]

    public = build_public_summary(results, bootstrap_samples=200, seed=17)

    assert public["coverage"] == {
        "frozen_openings": 20,
        "luna_responses": 20,
        "glm_evaluations": 20,
        "critical_failures": 0,
    }
    assert public["weighted_score_tenths"] == {
        "mean": 200,
        "ci95_low": 200,
        "ci95_high": 200,
    }
    assert public["raw_total_tenths"] == {
        "openings": 20,
        "mean": 80,
        "ci95_low": 80,
        "ci95_high": 80,
    }
    assert public["acceptance"]["accepted"] is True
    assert public["acceptance"]["score_verdict"] == "paired_comparison_required"
    assert public["luna_time_to_first_reply_ms"] == {
        "responses": 20,
        "median": 710,
        "ci95_low": 710,
        "ci95_high": 712,
    }
    assert all(
        set(row)
        == {
            "dialog_id",
            "length_stratum",
            "weighted_score_tenths",
            "raw_total",
            "critical_failure_count",
            "critical_failure_codes",
            "language_ok",
            "latency_ms",
            "luna_latency_ms",
            "glm_latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "cost_micro_usd",
        }
        for row in public["scenarios"]
    )
    rendered = str(public)
    assert "private opener" not in rendered
    assert "private response" not in rendered


def test_critical_failure_blocks_completion() -> None:
    """Catch an unsafe response being averaged away by a good mean score."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]
    results[4]["critical_failures"] = ["unsafe_commitment"]

    with pytest.raises(ValueError, match="critical failures"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))


def test_failed_quality_round_still_produces_a_text_safe_summary() -> None:
    """Catch a failed measured round disappearing instead of being reported."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]
    results[4]["critical_failures"] = ["unsafe_commitment"]

    public = build_public_summary(results, bootstrap_samples=200, seed=17)

    assert public["coverage"]["critical_failures"] == 1
    assert public["acceptance"]["accepted"] is False


def test_no_absolute_score_threshold_can_come_back() -> None:
    """`tj-vz7o.10.2`. The retired gate and why it may not return.

    The round of 2026-08-10 pre-registered "the lower bound reaches 20.0/30",
    then the applicability maps showed eleven of the twenty openings with a
    deterministic ceiling of 9.6/30. Those eleven could not have passed with
    every applicable rule perfect: the gate was unreachable by arithmetic, not
    by quality. Restoring any absolute level over this set restores that.
    """

    results = [_result(dialog_id, score=19.9) for dialog_id in range(1, 21)]

    public = build_public_summary(results, bootstrap_samples=200, seed=17)

    assert public["weighted_score_tenths"]["mean"] == 199
    assert "minimum_ci95_low_tenths" not in public["acceptance"]
    assert public["acceptance"]["score_verdict"] == "paired_comparison_required"
    assert public["acceptance"]["accepted"] is True


def test_the_score_is_reported_against_the_ceiling_it_could_reach() -> None:
    """Averaging a 9.6 ceiling with a 30.0 one produces a number no opening
    could have scored. The bands keep them apart."""

    results = [
        _result(dialog_id, score=7.2, attainable=9.6) for dialog_id in range(1, 12)
    ] + [_result(dialog_id, score=21.0, attainable=30.0) for dialog_id in range(12, 21)]

    public = build_public_summary(results, bootstrap_samples=200, seed=17)

    assert public["ceiling_bands"] == [
        {
            "attainable_tenths": 96,
            "openings": 11,
            "mean_tenths": 72,
            "share_of_ceiling_percent": 75,
        },
        {
            "attainable_tenths": 300,
            "openings": 9,
            "mean_tenths": 210,
            "share_of_ceiling_percent": 70,
        },
    ]


def test_a_critical_failure_still_blocks_acceptance_at_any_score() -> None:
    """The one absolute left in the contract. A fabricated figure is a defect
    whatever the mean says, so it is not a threshold that can be tuned."""

    results = [_result(dialog_id, score=29.0) for dialog_id in range(1, 21)]
    results[3]["critical_failures"] = ["hallucination"]

    public = build_public_summary(results, bootstrap_samples=200, seed=17)

    assert public["acceptance"]["accepted"] is False
    assert public["acceptance"]["critical_failure_count"] == 1


def test_cost_estimate_prices_every_authorized_call() -> None:
    """Catch a preflight that reserves only one call instead of the full arm."""
    assert estimate_cost_usd(
        calls=2,
        max_input_tokens=100,
        max_output_tokens=10,
        prompt_price=0.001,
        completion_price=0.002,
    ) == pytest.approx(0.24)


@pytest.mark.parametrize(
    ("text", "language"),
    [("hello", "en"), ("مرحبا", "ar"), ("كرسي office", "ar")],
)
def test_expected_language_follows_the_customer_opening(
    text: str, language: str
) -> None:
    """Catch the English default overriding an Arabic customer opening."""
    assert expected_language(text) == language


def test_generation_messages_bind_current_prompt_and_catalog_evidence() -> None:
    """Catch a cheap prompt shortcut that stops exercising product behavior."""
    messages = build_generation_messages(
        opening="I need an ergonomic chair",
        language="en",
        catalog_evidence=[
            {"name": "Axis Chair", "sku": "AX-1", "price": 1000, "stock": 9}
        ],
    )

    assert messages[-1] == {
        "role": "user",
        "content": "I need an ergonomic chair",
    }
    system = str(messages[0]["content"])
    assert "You are Noor" in system
    assert "STAGE: GREETING" in system
    assert "[READ-ONLY CATALOG EVIDENCE]" in system
    assert "Axis Chair" in system
    assert "Do not call tools in this isolated acceptance run" in system


def test_the_round_sends_the_directives_the_opening_earns() -> None:
    """A round without them scores a prompt no customer ever receives."""
    from src.llm.engine import _turn_runtime_directives

    opening = "We are fitting out a new office for 12 people"
    earned = _turn_runtime_directives(opening, sales_stage="greeting")
    assert earned, "this opening is supposed to earn the consultative directives"

    system = str(
        build_generation_messages(
            opening=opening,
            language="en",
            catalog_evidence=[],
        )[0]["content"]
    )

    assert "[RUNTIME DIRECTIVES]" in system
    for directive in earned:
        assert directive in system


def test_the_round_sends_the_ask_permissions_production_derives() -> None:
    """The frozen set may ask for a name and for discovery, and nothing else."""
    system = str(
        build_generation_messages(
            opening="I need an ergonomic chair",
            language="en",
            catalog_evidence=[],
        )[0]["content"]
    )

    assert (
        format_permitted_asks_prompt(
            permitted_asks_for_turn(
                is_first_turn=True,
                customer_name=None,
                customer_name_asked=False,
                owes_company_question=False,
                quote_consent_granted=False,
            )
        )
        in system
    )


def test_catalog_matches_use_customer_terms_not_catalog_order() -> None:
    """Catch irrelevant first-page products being injected as evidence."""
    products = [
        {"name": "Executive Desk", "sku": "D-1", "price": 2000},
        {"name": "Axis Ergonomic Chair", "sku": "C-1", "price": 1000},
    ]

    assert catalog_matches("ergonomic chair", products, limit=1) == [products[1]]


def test_critical_failure_codes_combine_judge_and_deterministic_gates() -> None:
    """Catch a bad language or invented number being hidden by a clean judge."""
    assert critical_failure_codes(
        red_flag_codes=["ignored_question", "unverified_commitment"],
        ungrounded_numbers=["9000"],
        language_ok=False,
    ) == [
        "hallucination",
        "ignored_request",
        "unsafe_commitment",
        "wrong_language",
    ]


def test_numeric_grounding_normalizes_catalog_names_and_opening_ranges() -> None:
    """Catch catalog dimensions and formatting changes being called hallucinations."""
    case = {
        "opening": "Please deliver within 2-3 days",
        "catalog_evidence": [{"name": "Desk W1800xD800xH750", "price_aed": 1200.0}],
        "anchor_line": None,
    }

    assert (
        find_ungrounded_numbers(
            "The desk is 1,800 x 800 x 750 and costs AED 1,200; timeline 2–3 days.",
            case,
        )
        == []
    )
    assert find_ungrounded_numbers("Options start at AED 901.", case) == ["901"]


@pytest.mark.asyncio
async def test_the_harness_applies_the_guards_that_ship() -> None:
    """`tj-vz7o.10.1`. The round measured the model plus one guard.

    Production runs `apply_opening_guard`, then the deferral guard, then
    `enforce_grounding_output`, and only then does a customer see the text. A
    harness that stops after the first measures a reply that would never be
    sent. Neither failure found on 2026-08-10 was caused by this gap -- both
    survive the full pipeline -- but a defect production would have filtered
    cannot be told from a real one after the fact.
    """

    calls: list[RepairJudgeRequest] = []

    async def correct(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        calls.append(request)
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text=(
                    "I can help you explore verified catalog options. "
                    "What are you furnishing?"
                ),
                rationale="Remove the unsupported service and keep useful help.",
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    invented = await apply_shipped_output_guards(
        "We can assess and buy your used desks. What are you furnishing?",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="I need an ergonomic chair.",
        runner=correct,
    )

    assert "buy your used desks" not in invented.content
    assert "What are you furnishing?" in invented.content
    assert invented.repair_trace is not None
    assert invented.repair_trace.counts.calls == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_price_on_a_retrieved_row_survives_without_a_repair_call() -> None:
    calls = 0

    async def fail_if_called(
        _request: RepairJudgeRequest,
    ) -> RepairJudgeProviderResult:
        nonlocal calls
        calls += 1
        raise AssertionError("a no-trigger reply must not call the repair judge")

    kept = await apply_shipped_output_guards(
        "The XTEN-S workstation is AED 566.87.",
        language="en",
        anchor_line=None,
        catalog_evidence=[{"name": "XTEN-S", "price_aed": 566.87, "stock": 4}],
        customer_message="What does XTEN-S cost?",
        runner=fail_if_called,
    )

    assert "566.87" in kept.content
    assert kept.repair_trace is None
    assert calls == 0


@pytest.mark.asyncio
async def test_triggered_harness_reply_matches_the_production_finalizer() -> None:
    raw = "We can assess and buy your used desks."
    state = ReplyPolicyState(language="en", is_first_turn=True)

    async def correct(_request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text="I can help you choose furniture from our catalog.",
                rationale="Use the supported catalog path.",
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    harness = await apply_shipped_output_guards(
        raw,
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="Can you buy my desks?",
        runner=correct,
    )
    rendered = render_reply(raw, state=state, provenance="model")
    production = await _finalize_turn_response(
        SimpleNamespace(
            masked_text="Can you buy my desks?",
            pii_map={},
            deps=SimpleNamespace(
                executed_tool_names=(),
                conversation=SimpleNamespace(metadata_={}),
            ),
            _record_reply_on_conversation=lambda _model, _text: None,
        ),
        LLMResponse(
            text=rendered.text,
            tokens_in=10,
            tokens_out=10,
            cost=0.001,
            model=GENERATOR_MODEL,
            repair_flags=rendered.flags,
            repair_policy_state=state,
        ),
        runner=correct,
    )

    assert harness.content == production.text
    assert harness.repair_trace is not None
    assert production.repair_trace is not None
    assert harness.repair_trace.answer == production.repair_trace.answer == "correct"
    assert harness.repair_trace.counts == production.repair_trace.counts


@pytest.mark.asyncio
async def test_the_harness_commits_to_what_it_defers() -> None:
    committed = await apply_shipped_output_guards(
        "Whether assembly can be included still needs confirmation.",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="Can assembly be included?",
    )

    assert (
        "I'll confirm assembly with our team and come back to you." in committed.content
    )


@pytest.mark.asyncio
async def test_preflight_authorizes_the_repair_model_and_round_call_cap(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"Opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    requested_models: list[tuple[str, ...]] = []

    async def model_catalog(models: tuple[str, ...]) -> dict[str, dict[str, object]]:
        requested_models.append(models)
        return {
            model: {
                "id": model,
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            }
            for model in models
        }

    async def catalog_products() -> list[dict[str, object]]:
        return [{"name": "Desk", "sku": "D-1", "price": 1000, "stock": 9}]

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        model_catalog,
    )
    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._fetch_catalog_summaries",
        catalog_products,
    )

    document = await preflight(
        scenarios_path=scenarios_path,
        output_dir=tmp_path / "protected",
        per_model_cap_usd=1.0,
    )

    assert requested_models == [(GENERATOR_MODEL, REPAIR_JUDGE_MODEL)]
    assert document["calls_per_model"] == {
        GENERATOR_MODEL: 20,
        REPAIR_JUDGE_MODEL: REPAIR_JUDGE_CALL_CAP,
        ROOT_JUDGE: 0,
    }
    assert document["repair_judge_authority"] == {
        "model": REPAIR_JUDGE_MODEL,
        "call_cap": REPAIR_JUDGE_CALL_CAP,
    }


def _prepared_round_files(output_dir: pathlib.Path) -> None:
    output_dir.mkdir(mode=0o700)
    preflight_doc = {
        "schema_version": "treejar-real-opening-preflight/v1",
        "paid_calls_made": 0,
        "judge_model": ROOT_JUDGE,
        "scenario_digest": "a" * 64,
        "model_catalog": {
            GENERATOR_MODEL: {
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            },
            REPAIR_JUDGE_MODEL: {
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            },
        },
        "per_model_cap_usd": {
            GENERATOR_MODEL: 1.0,
            REPAIR_JUDGE_MODEL: 1.0,
            ROOT_JUDGE: 0.0,
        },
    }
    cases = [
        {
            "dialog_id": dialog_id,
            "length_stratum": (dialog_id - 1) // 5 + 1,
            "opening": f"Opening {dialog_id}",
            "language": "en",
            "catalog_evidence": [],
            "catalog_relevant": False,
            "anchor_line": None,
            "generation_messages": [
                {"role": "user", "content": f"Opening {dialog_id}"}
            ],
            "generation_prompt_digest": str(dialog_id).zfill(64),
        }
        for dialog_id in range(1, 21)
    ]
    for name, value in (
        ("preflight.json", preflight_doc),
        ("prepared-cases.json", cases),
    ):
        path = output_dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)


@pytest.mark.asyncio
@pytest.mark.parametrize("triggered", [False, True])
async def test_round_journals_only_triggered_repair_calls(
    triggered: bool,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / ("triggered" if triggered else "clean")
    _prepared_round_files(output_dir)
    generation_calls = 0
    repair_calls = 0

    async def request_once(
        _client: object,
        _payload: dict[str, object],
    ) -> tuple[dict[str, object], int]:
        nonlocal generation_calls
        generation_calls += 1
        content = (
            "We can assess and buy your used desks."
            if triggered and generation_calls == 1
            else "I can help you explore our office furniture catalog."
        )
        return (
            {
                "model": GENERATOR_MODEL,
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "cost": 0.0001,
                },
            },
            5,
        )

    async def repair(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        nonlocal repair_calls
        repair_calls += 1
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text="I can help you choose furniture from our catalog.",
                rationale="Use the supported catalog path.",
            ),
            model=REPAIR_JUDGE_MODEL,
            prompt_tokens=20,
            completion_tokens=10,
            cost_usd=0.0002,
        )

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        request_once,
    )
    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance.run_repair_judge",
        repair,
    )
    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._provider_headers",
        lambda _title: {},
    )

    result = await run_paid_round(output_dir)
    state = json.loads((output_dir / "run-state.json").read_text(encoding="utf-8"))
    repair_pack = json.loads(
        (output_dir / "repair-reading-pack.json").read_text(encoding="utf-8")
    )

    assert result["generation_complete"] is True
    assert generation_calls == 20
    assert repair_calls == int(triggered)
    assert state["calls_started_by_arm"] == {
        "generation": 20,
        "repair_judge": int(triggered),
        "scoring_judge": 0,
    }
    assert state["calls_started"][REPAIR_JUDGE_MODEL] == int(triggered)
    assert len(repair_pack) == int(triggered)
    if triggered:
        first = state["records"]["1"]
        assert first["repair_judge"]["answer"] == "correct"
        assert "buy your used desks" not in first["generation"]["content"]


def test_the_round_judges_itself_unless_a_second_reader_is_asked_for() -> None:
    """The owner's standing decision, as a default rather than a directive.

    The judge is the orchestrator reading blind. A paid model may be added
    beside that reading; it may not replace it. `preflight` therefore has to be
    told `--second-reader` before any judging call can be paid for, and the run
    that is not told stops after the generation arm.
    """

    signature = inspect.signature(preflight)
    assert signature.parameters["second_reader"].default is False

    argv = ["preflight", "--scenarios", "s.json", "--output-dir", "out"]
    with patch.object(sys, "argv", ["prog", *argv]):
        assert _parse_args().second_reader is False
    with patch.object(sys, "argv", ["prog", *argv, "--second-reader"]):
        assert _parse_args().second_reader is True


def test_a_root_judged_result_is_a_complete_result() -> None:
    """The scoring path is the same one either judge feeds."""

    results = [_result(index) for index in range(1, 21)]
    for item in results:
        item["judge_model"] = ROOT_JUDGE
        item["glm_latency_ms"] = 0

    validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))

    results[0]["judge_model"] = "anthropic/claude-haiku-4.5"
    with pytest.raises(ValueError, match="root judge"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))
