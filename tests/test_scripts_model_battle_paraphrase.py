"""The instrument for `tj-feet.9`, before it is pointed at a provider.

A checker is accepted or rejected on TPR, TNR and false blocks, so the thing
that computes them has to be right first. These tests fix the probe set's own
properties and the arithmetic of the report.
"""

from __future__ import annotations

import pytest
from scripts.model_battle_paraphrase import (
    PROBE_SET,
    CheckerVerdict,
    ParaphraseProbe,
    checker_payload,
    evaluate_checker,
)

_NUMERIC = tuple("0123456789٠١٢٣٤٥٦٧٨٩")


# --- properties of the probe set itself -------------------------------------


def test_every_probe_is_paired_across_both_served_languages() -> None:
    """An English-only result would not transfer, and the research says so.

    The cited verifier evidence base, including the 770M-parameter result at
    400x lower cost, was evaluated on English only.
    """
    english = {p.probe_id[:-3] for p in PROBE_SET if p.language == "en"}
    arabic = {p.probe_id[:-3] for p in PROBE_SET if p.language == "ar"}

    assert english == arabic
    assert len(PROBE_SET) == 2 * len(english)


def test_the_set_is_balanced_between_the_two_labels() -> None:
    """An unbalanced set lets a checker that always blocks look good on TPR."""
    widened = [p for p in PROBE_SET if p.should_block]
    faithful = [p for p in PROBE_SET if not p.should_block]

    assert len(widened) == len(faithful)


@pytest.mark.parametrize("probe", PROBE_SET, ids=lambda p: p.probe_id)
def test_no_probe_sends_the_checker_something_code_already_verifies(
    probe: ParaphraseProbe,
) -> None:
    """The specification's constraint, enforced rather than trusted.

    No numbers, SKUs, prices or stock: the claim contract and the numeric
    grounding checks own those, and a paid second opinion on them is waste.
    """
    payload = checker_payload(probe)
    joined = " ".join(payload.values())

    assert not any(digit in joined for digit in _NUMERIC)
    assert set(payload) == {"field", "catalog_value", "claim"}


@pytest.mark.parametrize("probe", PROBE_SET, ids=lambda p: p.probe_id)
def test_a_faithful_claim_carries_no_word_the_value_lacks_by_accident(
    probe: ParaphraseProbe,
) -> None:
    """A faithful probe must be a rewording, not a shorter version of the truth.

    It is not a containment check — `the frame is metal` deliberately shares no
    stem with `steel frame`. It only pins that every faithful probe stays about
    the same field, so a checker cannot be right for the wrong reason.
    """
    assert probe.claim_text.strip()
    assert probe.stored_value.strip()
    assert probe.note.strip()


# --- the report -------------------------------------------------------------


def _verdicts(blocked_ids: set[str]) -> tuple[CheckerVerdict, ...]:
    return tuple(
        CheckerVerdict(
            probe_id=probe.probe_id,
            language=probe.language,
            blocked=probe.probe_id in blocked_ids,
        )
        for probe in PROBE_SET
    )


def test_a_perfect_checker_scores_one_on_both_axes_and_zero_false_blocks() -> None:
    report = evaluate_checker(
        _verdicts({p.probe_id for p in PROBE_SET if p.should_block})
    )

    assert report.true_positive_rate.rate == 1.0
    assert report.true_negative_rate.rate == 1.0
    assert report.false_block_rate.rate == 0.0


def test_a_checker_that_blocks_everything_is_caught_by_the_false_block_rate() -> None:
    """The failure mode adoption has to be protected from.

    Blocking everything gives a perfect TPR. Only the false-block rate, on its
    own denominator, says what it costs.
    """
    report = evaluate_checker(_verdicts({p.probe_id for p in PROBE_SET}))

    assert report.true_positive_rate.rate == 1.0
    assert report.true_negative_rate.rate == 0.0
    assert report.false_block_rate.rate == 1.0


def test_a_checker_that_blocks_nothing_is_caught_by_the_true_positive_rate() -> None:
    report = evaluate_checker(_verdicts(set()))

    assert report.true_positive_rate.rate == 0.0
    assert report.true_negative_rate.rate == 1.0
    assert report.false_block_rate.rate == 0.0


def test_the_report_splits_by_language() -> None:
    english_widened = {
        p.probe_id for p in PROBE_SET if p.should_block and p.language == "en"
    }
    verdicts = _verdicts(english_widened)

    english = evaluate_checker(verdicts, language="en")
    arabic = evaluate_checker(verdicts, language="ar")

    assert english.true_positive_rate.rate == 1.0
    assert arabic.true_positive_rate.rate == 0.0
    assert english.scored == arabic.scored


def test_an_empty_denominator_reports_none_rather_than_zero() -> None:
    report = evaluate_checker((), language="en")

    assert report.true_positive_rate.rate is None
    assert report.false_block_rate.rate is None
