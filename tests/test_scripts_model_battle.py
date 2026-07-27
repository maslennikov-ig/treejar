from __future__ import annotations

import json

import pytest
from scripts.model_battle import (
    EXTENDED_PROFILE,
    CandidateMetrics,
    _build_jobs,
    aggregate_rows,
    assert_catalog_capabilities,
    build_base_payload,
    build_blind_pair,
    candidate_metrics_from_evidence,
    evaluate_blind_reviews,
    extract_numeric_tokens,
    models_for_profile,
    parse_json_content,
    percentile,
    retry_was_used,
    score_blind_reviews,
    score_expected_fields,
    score_sales_response,
    select_winner,
    should_retry_status,
    validate_json_schema,
)
from scripts.model_battle_cases import SALES_CASES, SYSTEM_CASES, validate_case_sets


def test_case_sets_cover_the_accepted_battle_shape() -> None:
    validate_case_sets()

    assert len(SALES_CASES) == 12
    assert len(SYSTEM_CASES) == 24
    assert len({case.case_id for case in SALES_CASES}) == len(SALES_CASES)
    assert len({case.case_id for case in SYSTEM_CASES}) == len(SYSTEM_CASES)
    assert {case.category for case in SYSTEM_CASES} == {
        "fact_extraction",
        "red_flags",
        "faq_candidate",
        "summary",
        "translation",
        "tool_arguments",
    }


def test_extended_profile_has_four_candidates_per_route() -> None:
    assert models_for_profile(EXTENDED_PROFILE, "sales") == (
        "z-ai/glm-5",
        "z-ai/glm-5.2",
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
    )
    assert models_for_profile(EXTENDED_PROFILE, "system") == (
        "nex-agi/nex-n2-mini",
        "z-ai/glm-5.2",
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
    )


def test_extended_profile_builds_complete_deterministic_job_matrix() -> None:
    first = _build_jobs(
        suite="sales",
        repetitions=2,
        seed=27072026,
        profile=EXTENDED_PROFILE,
    )
    second = _build_jobs(
        suite="sales",
        repetitions=2,
        seed=27072026,
        profile=EXTENDED_PROFILE,
    )

    assert first == second
    assert len(first) == len(SALES_CASES) * 2 * 4
    assert {model for model, _case, _repetition in first} == set(
        models_for_profile(EXTENDED_PROFILE, "sales")
    )


def test_catalog_preflight_rejects_missing_required_model_capability() -> None:
    catalog = {
        "z-ai/glm-5": {"supported_parameters": ["tools", "tool_choice"]},
        "deepseek/deepseek-v4-flash": {
            "supported_parameters": [
                "tools",
                "tool_choice",
                "response_format",
                "reasoning",
                "structured_outputs",
            ]
        },
        "nex-agi/nex-n2-mini": {
            "supported_parameters": [
                "tools",
                "tool_choice",
                "response_format",
                "reasoning",
            ]
        },
    }

    with pytest.raises(RuntimeError, match="structured_outputs"):
        assert_catalog_capabilities(catalog, ("sales", "system"))


def test_catalog_preflight_accepts_extended_profile_capabilities() -> None:
    all_parameters = [
        "tools",
        "tool_choice",
        "response_format",
        "reasoning",
        "structured_outputs",
    ]
    catalog = {
        model: {"supported_parameters": all_parameters}
        for suite in ("sales", "system")
        for model in models_for_profile(EXTENDED_PROFILE, suite)
    }

    assert_catalog_capabilities(
        catalog,
        ("sales", "system"),
        profile=EXTENDED_PROFILE,
    )


def test_base_payload_requires_an_endpoint_supporting_all_parameters() -> None:
    payload = build_base_payload(
        model="candidate",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=900,
        reasoning_enabled=False,
    )

    assert payload["provider"] == {"require_parameters": True}
    assert payload["reasoning"] == {"enabled": False}


@pytest.mark.parametrize("status", [408, 409, 429, 500, 502, 503, 504])
def test_retry_status_accepts_only_transient_http_errors(status: int) -> None:
    assert should_retry_status(status) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_retry_status_rejects_permanent_http_errors(status: int) -> None:
    assert should_retry_status(status) is False


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"name":"Maya","quantity":2}', {"name": "Maya", "quantity": 2}),
        (
            '```json\n{"language":"ar","needs_confirmation":false}\n```',
            {"language": "ar", "needs_confirmation": False},
        ),
    ],
)
def test_parse_json_content_accepts_plain_json_and_fenced_json(
    content: str,
    expected: object,
) -> None:
    assert parse_json_content(content) == expected


def test_parse_json_content_rejects_non_json() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_json_content("The answer is two.")


def test_validate_json_schema_reports_nested_contract_errors() -> None:
    schema = {
        "type": "object",
        "required": ["customer", "items"],
        "additionalProperties": False,
        "properties": {
            "customer": {
                "type": "object",
                "required": ["language"],
                "additionalProperties": False,
                "properties": {
                    "language": {"type": "string", "enum": ["en", "ar"]},
                },
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["sku", "quantity"],
                    "additionalProperties": False,
                    "properties": {
                        "sku": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
    }

    assert (
        validate_json_schema(
            {
                "customer": {"language": "ar"},
                "items": [{"sku": "CHAIR-1", "quantity": 2}],
            },
            schema,
        )
        == []
    )

    errors = validate_json_schema(
        {
            "customer": {"language": "fr"},
            "items": [{"sku": "CHAIR-1", "quantity": 0, "color": "red"}],
        },
        schema,
    )
    assert any("$.customer.language" in error and "enum" in error for error in errors)
    assert any(
        "$.items[0].quantity" in error and "minimum" in error for error in errors
    )
    assert any(
        "$.items[0].color" in error and "unexpected" in error for error in errors
    )


def test_score_expected_fields_handles_nested_lists_and_nulls() -> None:
    payload = {
        "language": "en",
        "facts": [
            {"key": "company", "value": "Orbit Labs", "needs_confirmation": False},
            {"key": "budget", "value": None, "needs_confirmation": True},
        ],
    }
    expected = {
        "language": "en",
        "facts[0].key": "company",
        "facts[0].value": "Orbit Labs",
        "facts[0].needs_confirmation": False,
        "facts[1].value": None,
        "facts[1].needs_confirmation": True,
    }

    correct, total, mismatches = score_expected_fields(payload, expected)

    assert (correct, total) == (6, 6)
    assert mismatches == []


def test_score_expected_fields_can_penalize_extra_array_items() -> None:
    payload = {"flags": [{"code": "bad_tone"}, {"code": "bad_tone"}]}
    expected = {"flags.$length": 1, "flags[0].code": "bad_tone"}

    correct, total, mismatches = score_expected_fields(payload, expected)

    assert (correct, total) == (1, 2)
    assert mismatches == ["$.flags.$length: expected 1, got 2"]


def test_score_expected_fields_normalizes_strings_but_not_numbers() -> None:
    payload = {"answer": "  Delivery TAKES 3–5 days. ", "quantity": 3}
    expected = {"answer": "delivery takes 3-5 days.", "quantity": 2}

    correct, total, mismatches = score_expected_fields(payload, expected)

    assert (correct, total) == (1, 2)
    assert mismatches == ["$.quantity: expected 2, got 3"]


def test_score_expected_fields_supports_semantic_text_fragments() -> None:
    payload = {"translation": "السعر هو 1,450 درهم إماراتي، والضمان لمدة 5 سنوات."}
    expected = {
        "translation": {
            "$contains_all": ["1,450", "درهم", "الضمان", "5"],
        }
    }

    correct, total, mismatches = score_expected_fields(payload, expected)

    assert (correct, total) == (1, 1)
    assert mismatches == []


def test_score_expected_fields_supports_numeric_value_inside_currency_text() -> None:
    correct, total, mismatches = score_expected_fields(
        {"value": "AED 8,000"},
        {"value": {"$number": 8000}},
    )

    assert (correct, total) == (1, 1)
    assert mismatches == []


def test_sales_scoring_blocks_ungrounded_numbers_and_wrong_language() -> None:
    score = score_sales_response(
        content="Axis Ergo متاح بسعر 1,450 درهم، ويمكن توصيل 99 وحدة.",
        required_phrases=("Axis Ergo", "1,450"),
        forbidden_phrases=(),
        expected_tools=(),
        observed_tools=(),
        expected_language="ar",
        allowed_numbers={"1450"},
    )

    assert score["language_ok"] is True
    assert score["ungrounded_numbers"] == ["99"]
    assert score["passed"] is False
    assert extract_numeric_tokens("AED 1,450 and 15%") == {"1450", "15"}


def test_tool_rounds_do_not_count_as_provider_retries() -> None:
    assert retry_was_used([1, 1, 1]) is False
    assert retry_was_used([1, 2]) is True


def test_aggregate_does_not_count_recovered_schema_as_first_pass() -> None:
    aggregate = aggregate_rows(
        [
            {
                "suite": "system",
                "case_id": "case",
                "category": "fact_extraction",
                "model": "candidate",
                "first_pass_success": False,
                "retry_used": True,
                "latency_ms": 100.0,
                "json_parse_ok": True,
                "schema_ok": True,
                "semantic_correct": 2,
                "semantic_total": 2,
                "semantic_mismatches": [],
                "tool_parse_error": None,
            }
        ]
    )

    assert aggregate["candidate"]["json_schema_first_pass"] == 0.0


def test_percentile_uses_linear_interpolation() -> None:
    timings = [100.0, 200.0, 400.0, 800.0]

    assert percentile(timings, 0.5) == pytest.approx(300.0)
    assert percentile(timings, 0.95) == pytest.approx(740.0)


def test_blind_pair_is_deterministic_and_hides_model_names() -> None:
    first = build_blind_pair(
        case_id="sales-01",
        repetition=1,
        candidates={
            "z-ai/glm-5": "First neutral answer",
            "deepseek/deepseek-v4-flash": "Second neutral answer",
        },
        seed=27072026,
    )
    second = build_blind_pair(
        case_id="sales-01",
        repetition=1,
        candidates={
            "z-ai/glm-5": "First neutral answer",
            "deepseek/deepseek-v4-flash": "Second neutral answer",
        },
        seed=27072026,
    )

    assert first == second
    assert set(first["answers"]) == {"A", "B"}
    assert "glm" not in json.dumps(first["answers"]).lower()
    assert "deepseek" not in json.dumps(first["answers"]).lower()
    assert set(first["reveal"]) == {"A", "B"}


def test_blind_group_supports_four_anonymous_candidates() -> None:
    candidates = {
        "z-ai/glm-5": "Answer one",
        "z-ai/glm-5.2": "Answer two",
        "deepseek/deepseek-v4-flash": "Answer three",
        "deepseek/deepseek-v4-pro": "Answer four",
    }

    blind = build_blind_pair(
        case_id="sales-01",
        repetition=1,
        candidates=candidates,
        seed=27072026,
    )

    assert set(blind["answers"]) == {"A", "B", "C", "D"}
    assert set(blind["reveal"].values()) == set(candidates)
    assert set(blind["answers"].values()) == set(candidates.values())
    assert not any(model in json.dumps(blind["answers"]) for model in candidates)


def test_blind_review_scores_map_back_to_models_only_after_review() -> None:
    reviews = [
        {
            "case_id": "sales-01",
            "repetition": 1,
            "scores": {
                "A": {
                    "scores": {
                        "clarity": 5,
                        "factual_trust": 5,
                        "persuasion": 4,
                        "concision": 4,
                        "next_step": 5,
                    },
                    "critical_failure": False,
                    "critical_failure_reason": "",
                },
                "B": {
                    "scores": {
                        "clarity": 3,
                        "factual_trust": 4,
                        "persuasion": 3,
                        "concision": 3,
                        "next_step": 2,
                    },
                    "critical_failure": True,
                    "critical_failure_reason": "Invented stock.",
                },
            },
        }
    ]
    key = [
        {
            "case_id": "sales-01",
            "repetition": 1,
            "reveal": {"A": "left", "B": "right"},
        }
    ]

    quality = score_blind_reviews(reviews, key)

    assert quality["left"] == pytest.approx(23 / 25)
    assert quality["right"] == pytest.approx(15 / 25)
    _, hard_gates = evaluate_blind_reviews(reviews, key)
    assert hard_gates == {"left": True, "right": False}


def test_blind_review_maps_all_labels_from_reveal_key() -> None:
    rubric = {
        "scores": {
            "clarity": 4,
            "factual_trust": 5,
            "persuasion": 4,
            "concision": 4,
            "next_step": 3,
        },
        "critical_failure": False,
        "critical_failure_reason": "",
    }
    reviews = [
        {
            "case_id": "sales-01",
            "repetition": 1,
            "scores": {label: dict(rubric) for label in ("A", "B", "C", "D")},
        }
    ]
    key = [
        {
            "case_id": "sales-01",
            "repetition": 1,
            "reveal": {
                "A": "one",
                "B": "two",
                "C": "three",
                "D": "four",
            },
        }
    ]

    quality, hard_gates = evaluate_blind_reviews(reviews, key)

    assert quality == {model: 0.8 for model in ("one", "two", "three", "four")}
    assert hard_gates == {model: True for model in ("one", "two", "three", "four")}


def test_blind_review_rejects_missing_pair() -> None:
    with pytest.raises(ValueError, match="do not match"):
        score_blind_reviews(
            [],
            [
                {
                    "case_id": "sales-01",
                    "repetition": 1,
                    "reveal": {"A": "left", "B": "right"},
                }
            ],
        )


def test_select_winner_blocks_candidate_that_fails_hard_gate() -> None:
    unsafe_fast = CandidateMetrics(
        model="fast-but-unsafe",
        weighted_score=98.0,
        hard_gates_passed=False,
        reliability=1.0,
        p95_ms=100.0,
    )
    safe_slower = CandidateMetrics(
        model="safe",
        weighted_score=82.0,
        hard_gates_passed=True,
        reliability=0.99,
        p95_ms=500.0,
    )

    decision = select_winner([unsafe_fast, safe_slower])

    assert decision.winner == "safe"
    assert decision.outcome == "winner"
    assert "hard gate" in decision.reason.lower()


def test_select_winner_reports_practical_tie_inside_two_points() -> None:
    left = CandidateMetrics(
        model="left",
        weighted_score=91.0,
        hard_gates_passed=True,
        reliability=0.99,
        p95_ms=1000.0,
    )
    right = CandidateMetrics(
        model="right",
        weighted_score=90.0,
        hard_gates_passed=True,
        reliability=0.99,
        p95_ms=950.0,
    )

    decision = select_winner([left, right])

    assert decision.winner is None
    assert decision.outcome == "practical_tie"


def test_select_winner_uses_material_latency_advantage_inside_tie_band() -> None:
    left = CandidateMetrics(
        model="left",
        weighted_score=91.0,
        hard_gates_passed=True,
        reliability=0.99,
        p95_ms=1000.0,
    )
    right = CandidateMetrics(
        model="right",
        weighted_score=90.0,
        hard_gates_passed=True,
        reliability=0.99,
        p95_ms=650.0,
    )

    decision = select_winner([left, right])

    assert decision.winner == "right"
    assert decision.outcome == "winner"
    assert "latency" in decision.reason.lower()


def test_select_winner_reports_no_safe_replacement_when_all_fail() -> None:
    candidates = [
        CandidateMetrics("one", 75.0, False, 0.8, 100.0),
        CandidateMetrics("two", 85.0, False, 0.9, 120.0),
    ]

    decision = select_winner(candidates)

    assert decision.winner is None
    assert decision.outcome == "no_safe_replacement"


def test_select_winner_supports_multiple_candidates() -> None:
    candidates = [
        CandidateMetrics("unsafe-fast", 99.0, False, 1.0, 100.0),
        CandidateMetrics("leader", 94.0, True, 1.0, 900.0),
        CandidateMetrics("runner-up", 90.0, True, 1.0, 600.0),
        CandidateMetrics("third", 85.0, True, 1.0, 400.0),
    ]

    decision = select_winner(candidates)

    assert decision.winner == "leader"
    assert decision.outcome == "winner"


def test_sales_candidate_metrics_include_blind_quality_and_hard_gates() -> None:
    rows = [
        {
            "suite": "sales",
            "case_id": "sales-01",
            "model": model,
            "first_pass_success": True,
            "retry_used": False,
            "latency_ms": latency,
            "objective": {
                "checks_passed": 5,
                "checks_total": 5,
                "passed": True,
                "hard_gate_passed": hard_gate,
                "tool_sequence_ok": True,
                "tool_arguments_ok": True,
            },
        }
        for model, latency, hard_gate in (
            ("left", 1000.0, True),
            ("right", 500.0, False),
        )
    ]

    metrics, details = candidate_metrics_from_evidence(
        suite="sales",
        rows=rows,
        blind_quality={"left": 0.8, "right": 1.0},
    )

    by_model = {metric.model: metric for metric in metrics}
    assert by_model["left"].hard_gates_passed is True
    assert by_model["right"].hard_gates_passed is False
    assert details["left"]["blind_quality"] == 0.8
    assert by_model["right"].weighted_score > by_model["left"].weighted_score


def test_system_candidate_metrics_enforce_schema_and_semantic_gates() -> None:
    rows: list[dict[str, object]] = []
    for model, schema_ok in (("safe", True), ("unsafe", False)):
        rows.extend(
            [
                {
                    "suite": "system",
                    "case_id": "json-case",
                    "category": "summary",
                    "model": model,
                    "first_pass_success": True,
                    "retry_used": False,
                    "latency_ms": 500.0,
                    "json_parse_ok": schema_ok,
                    "schema_ok": schema_ok,
                    "semantic_correct": 20 if schema_ok else 0,
                    "semantic_total": 20,
                    "semantic_mismatches": [] if schema_ok else ["bad"],
                    "tool_parse_error": None,
                },
                {
                    "suite": "system",
                    "case_id": "tool-case",
                    "category": "tool_arguments",
                    "model": model,
                    "first_pass_success": True,
                    "retry_used": False,
                    "latency_ms": 400.0,
                    "json_parse_ok": True,
                    "schema_ok": True,
                    "semantic_correct": 3,
                    "semantic_total": 3,
                    "semantic_mismatches": [],
                    "tool_parse_error": None,
                },
            ]
        )

    metrics, details = candidate_metrics_from_evidence(suite="system", rows=rows)

    by_model = {metric.model: metric for metric in metrics}
    assert by_model["safe"].hard_gates_passed is True
    assert by_model["unsafe"].hard_gates_passed is False
    assert details["unsafe"]["hard_gates"]["json_schema_at_least_97_5"] is False
