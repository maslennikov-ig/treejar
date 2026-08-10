"""The real-opening acceptance round is complete, bounded, and text-safe."""

from __future__ import annotations

import json
import pathlib

import pytest
from scripts.corpus_bridge.real_opening_acceptance import (
    _load_frozen_scenarios,
    apply_shipped_output_guards,
    build_generation_messages,
    build_public_summary,
    catalog_matches,
    critical_failure_codes,
    ensure_protected_output,
    estimate_cost_usd,
    expected_language,
    find_ungrounded_numbers,
    validate_complete_results,
)


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


def test_the_harness_applies_the_guards_that_ship() -> None:
    """`tj-vz7o.10.1`. The round measured the model plus one guard.

    Production runs `apply_opening_guard`, then the deferral guard, then
    `enforce_grounding_output`, and only then does a customer see the text. A
    harness that stops after the first measures a reply that would never be
    sent. Neither failure found on 2026-08-10 was caused by this gap -- both
    survive the full pipeline -- but a defect production would have filtered
    cannot be told from a real one after the fact.
    """

    invented = apply_shipped_output_guards(
        "Our ergonomic chairs start from AED 500 in our catalog. "
        "What are you furnishing?",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
    )

    assert "AED 500" not in invented
    assert "What are you furnishing?" in invented


def test_a_price_on_a_retrieved_row_survives_the_harness_guards() -> None:
    kept = apply_shipped_output_guards(
        "The XTEN-S workstation is AED 566.87.",
        language="en",
        anchor_line=None,
        catalog_evidence=[{"name": "XTEN-S", "price_aed": 566.87, "stock": 4}],
    )

    assert "566.87" in kept


def test_the_harness_commits_to_what_it_defers() -> None:
    committed = apply_shipped_output_guards(
        "Whether assembly can be included still needs confirmation.",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
    )

    assert "I'll confirm assembly with our team and come back to you." in committed
