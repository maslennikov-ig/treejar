from __future__ import annotations

import json

import pytest
from scripts.model_battle import (
    BACKGROUND_HARD_PROFILE,
    CORE_HARD_PROFILE,
    EXTENDED_PROFILE,
    CandidateMetrics,
    _build_jobs,
    _safe_error_text,
    _sanitize_provider_payload,
    aggregate_rows,
    assert_catalog_capabilities,
    assert_existing_run_evidence,
    blind_scores_digest,
    build_base_payload,
    build_blind_pair,
    build_survivor_jobs,
    candidate_metrics_from_evidence,
    cases_for_profile,
    contains_pii_leakage,
    detect_evaluator_disagreements,
    enforce_model_cost_caps,
    evaluate_blind_reviews,
    extract_numeric_tokens,
    merge_run_manifest,
    models_for_profile,
    normalize_blind_reviews,
    parse_json_content,
    percentile,
    reasoning_was_observed,
    rescore_system_rows,
    retry_was_used,
    score_blind_reviews,
    score_expected_fields,
    score_sales_response,
    select_differentiating_system_cases,
    select_hard_profile_winner,
    select_winner,
    should_retry_status,
    summarize_attempt_accounting,
    validate_json_schema,
    verify_blind_scores_seal,
)
from scripts.model_battle_cases import (
    BACKGROUND_HARD_CASES,
    CORE_HARD_CASES,
    SALES_CASES,
    SYSTEM_CASES,
    validate_case_sets,
)


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


def test_hard_profiles_pin_exact_candidates_and_fixtures() -> None:
    assert models_for_profile(CORE_HARD_PROFILE, "sales") == (
        "z-ai/glm-5.2",
        "deepseek/deepseek-v4-flash-0731",
        "openai/gpt-5.6-luna",
        "xiaomi/mimo-v2.5-pro",
    )
    assert models_for_profile(BACKGROUND_HARD_PROFILE, "system") == (
        "deepseek/deepseek-v4-flash",
        "z-ai/glm-5.2",
        "deepseek/deepseek-v4-flash-0731",
        "openai/gpt-5.6-luna",
        "xiaomi/mimo-v2.5-pro",
    )
    assert cases_for_profile(CORE_HARD_PROFILE, "sales") == CORE_HARD_CASES
    assert cases_for_profile(BACKGROUND_HARD_PROFILE, "system") == (
        BACKGROUND_HARD_CASES
    )
    assert {case.case_id for case in CORE_HARD_CASES} == {
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "S08",
    }
    assert all(case.conversation for case in CORE_HARD_CASES)
    assert len(BACKGROUND_HARD_CASES) == 6
    assert (
        len(
            _build_jobs(
                suite="sales",
                repetitions=1,
                seed=27072026,
                profile=CORE_HARD_PROFILE,
            )
        )
        == 24
    )
    assert (
        len(
            _build_jobs(
                suite="system",
                repetitions=1,
                seed=27072026,
                profile=BACKGROUND_HARD_PROFILE,
            )
        )
        == 30
    )


def test_hard_profile_payload_is_first_party_and_parameter_minimal() -> None:
    payload = build_base_payload(
        model="openai/gpt-5.6-luna",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=2200,
        reasoning_enabled=False,
    )

    assert payload == {
        "model": "openai/gpt-5.6-luna",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 2200,
        "provider": {
            "only": ["openai"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "reasoning": {"enabled": False},
    }
    assert (
        not {
            "temperature",
            "top_p",
            "seed",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "parallel_tool_calls",
        }
        & payload.keys()
    )


def test_survivor_jobs_exclude_core_hard_failure_and_use_three_repetitions() -> None:
    rows = [
        {
            "suite": "sales",
            "case_id": case.case_id,
            "model": model,
            "repetition": 1,
            "objective": {"hard_gate_passed": model != "unsafe"},
        }
        for case in CORE_HARD_CASES
        for model in ("safe", "unsafe")
    ]

    jobs = build_survivor_jobs(
        suite="sales",
        profile=CORE_HARD_PROFILE,
        round_zero_rows=rows,
        seed=27072026,
    )

    assert {model for model, _case, _repetition in jobs} == {"safe"}
    assert {repetition for _model, _case, repetition in jobs} == {2, 3}
    assert len(jobs) == len(CORE_HARD_CASES) * 2


def test_background_survivors_repeat_only_three_differentiating_cases() -> None:
    rows = []
    for index, case in enumerate(BACKGROUND_HARD_CASES):
        rows.extend(
            [
                {
                    "suite": "system",
                    "case_id": case.case_id,
                    "model": "left",
                    "repetition": 1,
                    "first_pass_success": True,
                    "json_parse_ok": True,
                    "schema_ok": True,
                    "semantic_correct": 100,
                    "semantic_total": 100,
                    "semantic_mismatches": [],
                },
                {
                    "suite": "system",
                    "case_id": case.case_id,
                    "model": "right",
                    "repetition": 1,
                    "first_pass_success": True,
                    "json_parse_ok": True,
                    "schema_ok": True,
                    "semantic_correct": 100 if index < 3 else 102 - index,
                    "semantic_total": 100,
                    "semantic_mismatches": [] if index < 3 else ["different"],
                },
            ]
        )

    selected = select_differentiating_system_cases(rows, limit=3)
    jobs = build_survivor_jobs(
        suite="system",
        profile=BACKGROUND_HARD_PROFILE,
        round_zero_rows=rows,
        seed=27072026,
    )

    assert selected == tuple(case.case_id for case in BACKGROUND_HARD_CASES[-3:][::-1])
    assert {case.case_id for _model, case, _repetition in jobs} == set(selected)
    assert {repetition for _model, _case, repetition in jobs} == {2, 3}
    assert len(jobs) == 2 * 3 * 2


def test_core_hard_tie_keeps_glm_baseline() -> None:
    rows = [
        {
            "suite": "sales",
            "case_id": case.case_id,
            "model": model,
            "repetition": repetition,
            "first_pass_success": True,
            "latency_ms": 500,
            "accounting": {"cost_usd": 0.01},
            "objective": {
                "hard_gate_passed": True,
                "score_out_of_30": score,
                "tool_sequence_ok": True,
                "tool_arguments_ok": True,
            },
        }
        for case in CORE_HARD_CASES
        for repetition in (1, 2, 3)
        for model, score in (
            ("z-ai/glm-5.2", 25.0),
            ("openai/gpt-5.6-luna", 25.5),
        )
    ]

    decision = select_hard_profile_winner(CORE_HARD_PROFILE, rows)

    assert decision.outcome == "practical_tie"
    assert decision.winner == "z-ai/glm-5.2"


def test_background_hard_tie_keeps_current_fast_baseline() -> None:
    rows = [
        {
            "suite": "system",
            "case_id": case.case_id,
            "model": model,
            "repetition": 1,
            "first_pass_success": True,
            "latency_ms": 200,
            "accounting": {"cost_usd": 0.001},
            "json_parse_ok": True,
            "schema_ok": True,
            "semantic_correct": 20,
            "semantic_total": 20,
            "semantic_mismatches": [],
            "tool_parse_error": None,
        }
        for case in BACKGROUND_HARD_CASES
        for model in (
            "deepseek/deepseek-v4-flash",
            "xiaomi/mimo-v2.5-pro",
        )
    ]

    decision = select_hard_profile_winner(BACKGROUND_HARD_PROFILE, rows)

    assert decision.outcome == "practical_tie"
    assert decision.winner == "deepseek/deepseek-v4-flash"


def test_run_manifest_merges_separate_suite_invocations() -> None:
    existing = {
        "seed": 27072026,
        "repetitions": 2,
        "suites": ["sales"],
        "profile": EXTENDED_PROFILE,
        "models": {
            "sales": list(models_for_profile(EXTENDED_PROFILE, "sales")),
        },
        "production_changed": False,
        "synthetic_evidence_only": True,
    }

    merged = merge_run_manifest(
        existing,
        suites=("system",),
        profile=EXTENDED_PROFILE,
        repetitions=2,
        seed=27072026,
    )

    assert merged["suites"] == ["sales", "system"]
    assert set(merged["models"]) == {"sales", "system"}
    assert merged["models"]["sales"] == list(
        models_for_profile(EXTENDED_PROFILE, "sales")
    )
    assert merged["models"]["system"] == list(
        models_for_profile(EXTENDED_PROFILE, "system")
    )

    reverse_existing = {
        **existing,
        "suites": ["system"],
        "models": {
            "system": list(models_for_profile(EXTENDED_PROFILE, "system")),
        },
    }
    reverse = merge_run_manifest(
        reverse_existing,
        suites=("sales",),
        profile=EXTENDED_PROFILE,
        repetitions=2,
        seed=27072026,
    )
    assert reverse["suites"] == ["sales", "system"]

    with pytest.raises(ValueError, match="models"):
        merge_run_manifest(
            {**reverse_existing, "models": {"system": []}},
            suites=("sales",),
            profile=EXTENDED_PROFILE,
            repetitions=2,
            seed=27072026,
        )


def test_existing_suite_evidence_rejects_incomplete_matrix(tmp_path) -> None:
    manifest = {
        "seed": 27072026,
        "repetitions": 2,
        "suites": ["sales"],
        "profile": EXTENDED_PROFILE,
        "models": {
            "sales": list(models_for_profile(EXTENDED_PROFILE, "sales")),
        },
        "production_changed": False,
        "synthetic_evidence_only": True,
    }
    (tmp_path / "sales_results.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="incomplete"):
        assert_existing_run_evidence(tmp_path, manifest)


def test_existing_suite_evidence_rejects_wrong_suite_tag(tmp_path) -> None:
    manifest = {
        "seed": 27072026,
        "repetitions": 1,
        "suites": ["sales"],
        "profile": EXTENDED_PROFILE,
        "models": {
            "sales": list(models_for_profile(EXTENDED_PROFILE, "sales")),
        },
        "production_changed": False,
        "synthetic_evidence_only": True,
    }
    rows = [
        {
            "suite": "system",
            "case_id": case.case_id,
            "repetition": 1,
            "model": model,
        }
        for case in SALES_CASES
        for model in models_for_profile(EXTENDED_PROFILE, "sales")
    ]
    (tmp_path / "sales_results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="suite tag"):
        assert_existing_run_evidence(tmp_path, manifest)


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


def test_reasoning_diagnostic_detects_ignored_disable_control() -> None:
    attempts = [
        {
            "response": {
                "choices": [{"message": {"reasoning": "hidden work"}}],
                "usage": {
                    "completion_tokens_details": {"reasoning_tokens": 12},
                },
            }
        }
    ]

    assert reasoning_was_observed(attempts) is True
    assert (
        reasoning_was_observed(
            [
                {
                    "response": {
                        "choices": [{"message": {"reasoning": None}}],
                        "usage": {
                            "completion_tokens_details": {"reasoning_tokens": 0},
                        },
                    }
                }
            ]
        )
        is False
    )


def test_provider_evidence_redacts_account_identifiers() -> None:
    payload = {
        "error": {"message": "Provider returned error"},
        "user_id": "user_private_account",
        "nested": {"authorization": "Bearer private"},
        "error_text": "{'user_id': 'user_private_account'}",
    }

    sanitized = _sanitize_provider_payload(payload)

    assert sanitized["user_id"] == "[REDACTED]"
    assert sanitized["nested"]["authorization"] == "[REDACTED]"
    assert "user_private_account" not in sanitized["error_text"]
    assert "user_private_account" not in _safe_error_text(payload)


def test_attempt_accounting_includes_every_retry_and_provider_resolution() -> None:
    accounting = summarize_attempt_accounting(
        [
            {
                "elapsed_ms": 100.0,
                "response": {
                    "model": "resolved-a",
                    "provider": "openai",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "cost": 0.01,
                        "prompt_tokens_details": {"cached_tokens": 4},
                    },
                },
            },
            {
                "elapsed_ms": 250.0,
                "response": {
                    "model": "resolved-a",
                    "provider": "openai",
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 5,
                        "total_tokens": 25,
                        "cost": 0.02,
                    },
                },
            },
        ]
    )

    assert accounting == {
        "attempts": 2,
        "input_tokens": 30,
        "output_tokens": 7,
        "total_tokens": 37,
        "cached_tokens": 4,
        "cost_usd": pytest.approx(0.03),
        "latency_ms": 350.0,
        "resolved_models": ["resolved-a"],
        "providers": ["openai"],
        "endpoints": [],
    }


def test_cost_cap_is_125_percent_of_estimate_capped_at_one_dollar() -> None:
    rows = [
        {"model": "cheap", "accounting": {"cost_usd": 0.5}},
        {"model": "cheap", "accounting": {"cost_usd": 0.2}},
        {"model": "expensive", "accounting": {"cost_usd": 0.99}},
    ]

    enforce_model_cost_caps(rows, {"cheap": 0.6, "expensive": 0.9})

    with pytest.raises(RuntimeError, match="cheap"):
        enforce_model_cost_caps(
            rows + [{"model": "cheap", "accounting": {"cost_usd": 0.06}}],
            {"cheap": 0.6, "expensive": 0.9},
        )
    with pytest.raises(RuntimeError, match="expensive"):
        enforce_model_cost_caps(
            rows + [{"model": "expensive", "accounting": {"cost_usd": 0.02}}],
            {"cheap": 0.6, "expensive": 0.9},
        )


def test_blind_audit_disagreement_blocks_on_score_or_applicability() -> None:
    disagreements = detect_evaluator_disagreements(
        [
            {
                "case_id": "S01",
                "repetition": 1,
                "model": "model-a",
                "score_out_of_30": 25,
                "applicable_rules": ["catalog", "language"],
            },
            {
                "case_id": "S01",
                "repetition": 1,
                "model": "model-b",
                "score_out_of_30": 24,
                "applicable_rules": ["catalog"],
            },
        ],
        [
            {
                "case_id": "S01",
                "repetition": 1,
                "scores": {
                    "A": {
                        "score_out_of_30": 22,
                        "applicable_rules": ["catalog", "language"],
                    },
                    "B": {
                        "score_out_of_30": 24,
                        "applicable_rules": ["catalog", "language"],
                    },
                },
            }
        ],
        [
            {
                "case_id": "S01",
                "repetition": 1,
                "reveal": {"A": "model-a", "B": "model-b"},
            }
        ],
    )

    assert {(item["model"], item["reason"]) for item in disagreements} == {
        ("model-a", "score_delta"),
        ("model-b", "applicability"),
    }
    assert {item["status"] for item in disagreements} == {"EVAL_DISAGREEMENT"}


def test_blind_scores_must_match_pre_reveal_seal() -> None:
    scores = [{"case_id": "S01", "repetition": 1, "scores": {"A": {}}}]
    digest = blind_scores_digest(scores)

    verify_blind_scores_seal(scores, digest)
    with pytest.raises(ValueError, match="seal"):
        verify_blind_scores_seal([*scores, {"tampered": True}], digest)


def test_background_pii_guard_allows_source_facts_but_blocks_invention() -> None:
    assert contains_pii_leakage(
        "Call +971501234567 or email hidden@example.com",
        "No contact details were supplied.",
    )
    assert not contains_pii_leakage(
        "The supplied email is sales@example.com",
        "Customer email: sales@example.com",
    )


@pytest.mark.parametrize("status", [429, 500, 501, 502, 503, 504, 599])
def test_retry_status_accepts_only_transient_http_errors(status: int) -> None:
    assert should_retry_status(status) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 409, 422])
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


def test_score_expected_fields_ignores_terminal_punctuation() -> None:
    correct, total, mismatches = score_expected_fields(
        {"summary": "Customer requests 15% discount."},
        {"summary": "Customer requests 15% discount"},
    )

    assert (correct, total) == (1, 1)
    assert mismatches == []


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

    russian = score_sales_response(
        content="Модель AX-E1 доступна по подтверждённым фактам.",
        required_phrases=("AX-E1",),
        forbidden_phrases=(),
        expected_tools=(),
        observed_tools=(),
        expected_language="ru",
        allowed_numbers=set(),
    )
    assert russian["language_ok"] is True


def test_sales_scoring_does_not_treat_negated_claim_as_asserted() -> None:
    score = score_sales_response(
        content=(
            "Stock is unconfirmed, so I can't guarantee 20 units are "
            "available at this moment."
        ),
        required_phrases=("unconfirmed",),
        forbidden_phrases=("20 units are available",),
        expected_tools=(),
        observed_tools=(),
        expected_language="en",
        allowed_numbers={"20"},
    )

    assert score["forbidden_phrases"] == {"20 units are available": True}
    assert score["hard_gate_passed"] is True


def test_sales_scoring_detects_assertion_after_negated_prior_clause() -> None:
    score = score_sales_response(
        content="Stock is not unconfirmed, and 20 units are available.",
        required_phrases=(),
        forbidden_phrases=("20 units are available",),
        expected_tools=(),
        observed_tools=(),
        expected_language="en",
        allowed_numbers={"20"},
    )

    assert score["forbidden_phrases"] == {"20 units are available": False}
    assert score["hard_gate_passed"] is False


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


def test_original_pair_keeps_accepted_label_algorithm() -> None:
    pair = build_blind_pair(
        case_id="sales-02",
        repetition=1,
        candidates={
            "z-ai/glm-5": "First neutral answer",
            "deepseek/deepseek-v4-flash": "Second neutral answer",
        },
        seed=27072026,
    )

    assert pair["reveal"]["A"] == "deepseek/deepseek-v4-flash"
    assert pair["reveal"]["B"] == "z-ai/glm-5"


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


def test_four_way_blinding_is_counterbalanced_across_groups() -> None:
    candidates = {
        "one": "Answer one",
        "two": "Answer two",
        "three": "Answer three",
        "four": "Answer four",
    }
    counts = {
        model: {label: 0 for label in ("A", "B", "C", "D")} for model in candidates
    }

    for assignment_index in range(8):
        blind = build_blind_pair(
            case_id=f"sales-{assignment_index:02d}",
            repetition=1,
            candidates=candidates,
            seed=27072026,
            assignment_index=assignment_index,
        )
        for label, model in blind["reveal"].items():
            counts[model][label] += 1

    assert all(
        label_counts == {"A": 2, "B": 2, "C": 2, "D": 2}
        for label_counts in counts.values()
    )


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


def test_blind_review_normalizes_answers_alias_to_scores() -> None:
    rows = normalize_blind_reviews(
        [
            {
                "case_id": "sales-01",
                "repetition": 1,
                "answers": {"A": {"scores": {"clarity": 5}}},
            }
        ]
    )

    assert "answers" not in rows[0]
    assert rows[0]["scores"] == {"A": {"scores": {"clarity": 5}}}


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


def test_candidate_metrics_support_four_models() -> None:
    models = ("one", "two", "three", "four")
    rows = [
        {
            "suite": "sales",
            "case_id": "sales-01",
            "model": model,
            "first_pass_success": True,
            "retry_used": False,
            "latency_ms": 500.0,
            "objective": {
                "checks_passed": 5,
                "checks_total": 5,
                "passed": True,
                "hard_gate_passed": True,
                "tool_sequence_ok": True,
                "tool_arguments_ok": True,
            },
        }
        for model in models
    ]

    metrics, details = candidate_metrics_from_evidence(
        suite="sales",
        rows=rows,
        blind_quality={model: 0.8 for model in models},
    )

    assert {metric.model for metric in metrics} == set(models)
    assert set(details) == set(models)


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


def test_rescore_system_rows_applies_current_text_normalization() -> None:
    rows = rescore_system_rows(
        [
            {
                "suite": "system",
                "case_id": "system-tool-03",
                "category": "tool_arguments",
                "model": "candidate",
                "parsed": {
                    "reason_code": "discount_approval",
                    "summary": "Customer requests 15% discount.",
                },
                "json_parse_ok": True,
                "observed_tool": "escalate_to_manager",
                "expected_tool": "escalate_to_manager",
            }
        ]
    )

    assert rows[0]["semantic_correct"] == rows[0]["semantic_total"]
    assert rows[0]["semantic_mismatches"] == []
