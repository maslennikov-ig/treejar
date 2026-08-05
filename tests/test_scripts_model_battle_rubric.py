"""Regressions for the claim rubric and its anchor set (tj-feet.4)."""

from __future__ import annotations

import pytest
from scripts.model_battle_anchors import (
    ANCHOR_SET,
    grade_anchor,
    legacy_agreement,
    rubric_agreement,
)
from scripts.model_battle_rubric import (
    ClaimVerdict,
    ConversationalQuality,
    ToolObedience,
    aggregate_grades,
    classify_claim,
    grade_response,
)


def _quality(**overrides: int) -> ConversationalQuality:
    values = {"clarity": 4, "concision": 4, "persuasion": 4, "next_step": 4}
    values.update(overrides)
    return ConversationalQuality(**values)


# --- the four claim types ---------------------------------------------------


def test_labelled_assumption_with_a_confirming_question_passes() -> None:
    outcome = classify_claim(
        ClaimVerdict(
            claim_type="explicit_assumption",
            marker_present=True,
            confirming_question=True,
            contradicts_known=False,
        )
    )

    assert outcome.passed is True
    assert outcome.critical is False
    assert outcome.scored_as == "explicit_assumption"


def test_labelled_assumption_that_contradicts_evidence_fails() -> None:
    outcome = classify_claim(
        ClaimVerdict(
            claim_type="explicit_assumption",
            marker_present=True,
            confirming_question=True,
            contradicts_known=True,
        )
    )

    assert outcome.critical is True


@pytest.mark.parametrize(
    ("marker", "question"),
    [(False, True), (True, False), (False, False)],
)
def test_unmarked_assumption_is_scored_as_the_catalog_fact_it_imitates(
    marker: bool, question: bool
) -> None:
    """Without this the taxonomy would be a loophole, not a rubric."""
    outcome = classify_claim(
        ClaimVerdict(
            claim_type="explicit_assumption",
            marker_present=marker,
            confirming_question=question,
        )
    )

    assert outcome.scored_as == "catalog_fact"
    assert outcome.reclassified is True
    assert outcome.critical is True


def test_catalog_fact_needs_path_sku_and_value() -> None:
    supported = ClaimVerdict(
        claim_type="catalog_fact",
        field_path_present=True,
        same_sku=True,
        value_matches=True,
    )
    assert classify_claim(supported).passed is True

    for broken in (
        ClaimVerdict(claim_type="catalog_fact", field_path_present=False),
        ClaimVerdict(
            claim_type="catalog_fact", field_path_present=True, same_sku=False
        ),
        ClaimVerdict(
            claim_type="catalog_fact",
            field_path_present=True,
            same_sku=True,
            value_matches=False,
        ),
    ):
        outcome = classify_claim(broken)
        assert outcome.passed is False
        assert outcome.critical is True


def test_derived_fact_without_a_shown_computation_fails() -> None:
    outcome = classify_claim(
        ClaimVerdict(
            claim_type="derived_fact",
            field_path_present=True,
            same_sku=True,
            value_matches=True,
            computation_shown=False,
        )
    )

    assert outcome.critical is True


def test_recommendation_is_never_a_groundedness_failure() -> None:
    outcome = classify_claim(
        ClaimVerdict(claim_type="recommendation", appropriate=False)
    )

    assert outcome.critical is False
    assert outcome.scored_as == "recommendation"


def test_unknown_claim_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        ClaimVerdict(claim_type="vibes")  # type: ignore[arg-type]


# --- the three axes stay separate -------------------------------------------


def test_good_style_cannot_offset_a_false_fact() -> None:
    grade = grade_response(
        [ClaimVerdict(claim_type="catalog_fact", field_path_present=False)],
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(
            clarity=5, concision=5, persuasion=5, next_step=5
        ),
    )

    assert grade.critical_failure is True
    assert grade.groundedness == 0.0
    assert grade.conversational_quality == 1.0


def test_terseness_is_not_a_factual_error() -> None:
    grade = grade_response(
        [
            ClaimVerdict(
                claim_type="catalog_fact",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
            )
        ],
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(persuasion=1, next_step=1),
    )

    assert grade.critical_failure is False
    assert grade.groundedness == 1.0
    assert grade.conversational_quality < 0.6


def test_tool_disobedience_is_critical_on_its_own_axis() -> None:
    grade = grade_response(
        [
            ClaimVerdict(
                claim_type="catalog_fact",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
            )
        ],
        tool_obedience=ToolObedience(forbidden_call_made=True),
        conversational_quality=_quality(),
    )

    assert grade.tool_obedience_passed is False
    assert grade.critical_failure is True
    assert grade.groundedness == 1.0


def test_a_response_with_no_grounded_claim_reports_no_groundedness() -> None:
    grade = grade_response(
        [ClaimVerdict(claim_type="recommendation")],
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(),
    )

    assert grade.groundedness is None
    assert grade.grounded_claims_scored == 0


def test_aggregate_keeps_each_axis_on_its_own_denominator() -> None:
    clean = grade_response(
        [
            ClaimVerdict(
                claim_type="catalog_fact",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
            )
        ],
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(),
    )
    broken = grade_response(
        [ClaimVerdict(claim_type="catalog_fact", field_path_present=False)],
        tool_obedience=ToolObedience(forbidden_call_made=True),
        conversational_quality=_quality(),
    )

    report = aggregate_grades([clean, broken])

    assert report.responses == 2
    assert report.grounded_claims_scored == 2
    assert report.grounded_claims_failed == 1
    assert report.groundedness == 0.5
    assert report.tool_obedience_rate == 0.5
    # One response is clean on both axes; the other fails both but is still one
    # failing response. Critical failures count responses, not reasons.
    assert report.critical_failures == 1
    assert len(broken.critical_reasons) == 2


def test_conversational_quality_rejects_out_of_range_scores() -> None:
    with pytest.raises(ValueError):
        ConversationalQuality(clarity=6, concision=4, persuasion=4, next_step=4)
    with pytest.raises(ValueError):
        ConversationalQuality(clarity=True, concision=4, persuasion=4, next_step=4)  # type: ignore[arg-type]


# --- the two verdicts the rebuild exists to fix -----------------------------


def _anchor(case_id: str, repetition: int, label: str):
    for anchor in ANCHOR_SET:
        if (anchor.case_id, anchor.repetition, anchor.label) == (
            case_id,
            repetition,
            label,
        ):
            return anchor
    raise AssertionError(f"no anchor for {case_id}/{repetition}/{label}")


def test_the_wrongly_failed_labelled_assumption_now_passes() -> None:
    anchor = _anchor("S01", 3, "C")

    assert anchor.legacy_critical is True
    assert grade_anchor(anchor).critical_failure is False


def test_the_wrongly_passed_vague_claim_now_fails() -> None:
    anchor = _anchor("S04", 2, "C")

    assert anchor.legacy_critical is False
    assert grade_anchor(anchor).critical_failure is True


def test_every_anchor_reaches_its_recorded_verdict() -> None:
    assert rubric_agreement().rate == 1.0


def test_the_superseded_instrument_disagrees_with_three_anchors() -> None:
    agreement = legacy_agreement()

    assert (agreement.matched, agreement.total) == (7, 10)
    assert agreement.rate == 0.7


def test_anchor_set_carries_no_captured_wording() -> None:
    """Sealed evidence stays outside Git; anchors are pointers, not copies."""
    for anchor in ANCHOR_SET:
        assert anchor.pointer.startswith("20260805/core-r4:")
        assert anchor.description
        assert anchor.rationale
        for claim in anchor.claims:
            assert '"' not in claim.evidence
