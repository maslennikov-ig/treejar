"""Regressions for the counter-set and its seven metrics (tj-feet.5)."""

from __future__ import annotations

import pytest
from scripts.model_battle_counterset import (
    ANSWERABLE_CATEGORIES,
    COUNTER_SET,
    GuardConfig,
    PairedRun,
    ResponseObservation,
    paired_delta,
    report_metrics,
)

from src.dialogue.claim_contract import (
    AttributeClaim,
    RetrievedRow,
    check_claim,
    normalize_field_path,
)


def _observe(case_id: str, **overrides: object) -> ResponseObservation:
    return ResponseObservation(case_id=case_id, **overrides)  # type: ignore[arg-type]


# --- coverage of the set ----------------------------------------------------


def test_the_set_covers_every_category_in_both_served_languages() -> None:
    by_language: dict[str, set[str]] = {"en": set(), "ar": set()}
    for case in COUNTER_SET:
        by_language[case.language].add(case.category)

    assert by_language["en"] == by_language["ar"]
    assert by_language["en"] >= ANSWERABLE_CATEGORIES
    assert "control_violation" in by_language["en"]


def test_russian_is_not_in_the_set() -> None:
    """Owner decision of 2026-08-05: the assistant serves English and Arabic."""
    assert {case.language for case in COUNTER_SET} == {"en", "ar"}


def test_controls_exist_so_a_fall_in_refusals_cannot_be_gamed() -> None:
    controls = [case for case in COUNTER_SET if case.is_control]

    assert len(controls) >= 4
    assert all(case.must_answer is False for case in controls)


def test_every_answerable_case_is_answerable_without_its_missing_field() -> None:
    for case in COUNTER_SET:
        if case.is_control:
            continue
        assert case.must_answer is True
        assert case.available_fields
        assert not set(case.available_fields) & set(case.missing_fields)


# --- the seven metrics ------------------------------------------------------


def test_every_metric_reports_its_own_denominator() -> None:
    report = report_metrics(
        [
            _observe(
                "C01-en",
                made_grounded_claim=True,
                cited_a_confirmed_fact=True,
                completed_the_task=True,
                persuasion=4,
                next_step=5,
            ),
            _observe("K01-en", refused=True),
        ]
    )

    assert (report.unsupported_fact.numerator, report.unsupported_fact.denominator) == (
        0,
        1,
    )
    assert report.false_refusal.denominator == 1
    assert report.unnecessary_hedge.denominator == 1
    assert report.task_completion.denominator == 1
    assert report.persuasion.count == 2
    assert report.next_step.count == 2
    assert report.control_compliance.rate == 1.0


def test_a_refused_control_is_not_counted_as_a_false_refusal() -> None:
    report = report_metrics([_observe("K01-en", refused=True)])

    assert report.false_refusal.denominator == 0
    assert report.false_refusal.rate is None
    assert report.control_compliance.rate == 1.0


def test_a_refused_answerable_request_is_a_false_refusal() -> None:
    report = report_metrics([_observe("C03-en", refused=True)])

    assert report.false_refusal.rate == 1.0


def test_agreeing_to_a_control_violation_costs_control_compliance() -> None:
    """A model cannot win the refusal metric by agreeing to everything."""
    report = report_metrics(
        [_observe("K02-en", made_grounded_claim=True, asserted_unsupported_fact=True)]
    )

    assert report.control_compliance.rate == 0.0
    assert report.unsupported_fact.rate == 1.0


def test_an_empty_denominator_reports_none_rather_than_a_flattering_zero() -> None:
    report = report_metrics([_observe("C01-en")])

    assert report.unsupported_fact.rate is None
    assert report.unnecessary_hedge.rate is None
    assert report.deleted_correct_claim.rate is None


@pytest.mark.parametrize("language", ["en", "ar"])
def test_metrics_are_reported_per_language(language: str) -> None:
    observations = [
        _observe("C01-en", refused=True),
        _observe("C01-ar", completed_the_task=True),
    ]

    report = report_metrics(observations, language=language)

    assert report.false_refusal.denominator == 1
    assert report.false_refusal.rate == (1.0 if language == "en" else 0.0)


def test_persuasion_and_next_step_are_their_own_metrics() -> None:
    report = report_metrics(
        [_observe("C01-en", persuasion=5, next_step=1)],
    )

    assert report.persuasion.value == 5
    assert report.next_step.value == 1


# --- metric 5 has to be able to move ----------------------------------------


def test_an_over_strict_configuration_deletes_a_correct_supported_claim() -> None:
    """Metric 5 is the owner's 'the model will get dumber' concern as a number.

    Over-strictness is not hypothetical: dropping path normalization is enough,
    because the live catalog carries `Recommended load` and `Recommended Load`
    as separate specification keys.
    """
    rows = {
        "AX-E1": RetrievedRow(
            sku="AX-E1",
            fields={"attributes.specifications.Recommended load": "120 kg"},
        )
    }
    claim = AttributeClaim(
        claim_type="catalog_fact",
        sku="AX-E1",
        field_path="Recommended Load",
        value="120 kg",
    )

    assert check_claim(claim, rows).may_reach_customer is True
    # The over-strict configuration compares raw paths, so the same supported
    # claim no longer matches.
    over_strict = GuardConfig.over_strict()
    assert over_strict.normalize_field_paths is False
    assert "Recommended Load" not in rows["AX-E1"].fields
    assert normalize_field_path("Recommended Load") in rows["AX-E1"].normalized_fields()


def test_the_deleted_correct_claim_metric_moves_when_a_guard_over_deletes() -> None:
    lenient = report_metrics([_observe("C01-en", guard_withheld_anything=True)])
    strict = report_metrics(
        [
            _observe(
                "C01-en",
                guard_withheld_anything=True,
                guard_withheld_a_supported_claim=True,
            )
        ]
    )

    assert lenient.deleted_correct_claim.rate == 0.0
    assert strict.deleted_correct_claim.rate == 1.0


# --- the paired comparison --------------------------------------------------


def test_the_paired_run_scores_one_generation_under_both_configurations() -> None:
    runs = [
        PairedRun(
            case_id="C03-en",
            baseline=_observe(
                "C03-en",
                made_grounded_claim=True,
                asserted_unsupported_fact=True,
                completed_the_task=True,
            ),
            guarded=_observe(
                "C03-en", made_grounded_claim=True, completed_the_task=True
            ),
        )
    ]

    delta = paired_delta(runs)

    assert delta["baseline"].unsupported_fact.rate == 1.0
    assert delta["guarded"].unsupported_fact.rate == 0.0
    assert delta["baseline"].task_completion.rate == 1.0
    assert delta["guarded"].task_completion.rate == 1.0


def test_the_report_pins_the_rubric_and_counter_set_versions() -> None:
    report = report_metrics([_observe("C01-en")])

    assert report.rubric_version == "noor-claim-rubric/v1"
    assert report.counter_set_version == "noor-counter-set/v1"
