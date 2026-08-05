"""The claim rubric that replaces a single blended quality score.

Defect class (c) of the 2026-08-05 sealed round: the instrument scored
specificity rather than fabrication. A clearly labelled assumption carrying a
confirming question was marked a critical failure, while a vaguer unsourced
assertion in a well-scoring response was not flagged at all. Averaging five
dimensions into one number let good style offset a false fact, and let terseness
read as factual strength.

This module fixes both halves deterministically:

* a claim is scored as one of four types, and only the two that assert catalog
  truth can fail groundedness;
* groundedness, tool obedience and conversational quality are graded separately
  and are never summed.

Nothing here calls a provider. The judge supplies per-claim observations; this
code decides what they mean. That split is the point: the verdict is
reproducible from the observations, so a disagreement is always locatable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

RUBRIC_VERSION = "noor-claim-rubric/v1"
"""Pinned with every scored round. Bump on any change to the decision rules."""

CLAIM_TYPES = ("catalog_fact", "derived_fact", "explicit_assumption", "recommendation")
ClaimType = Literal[
    "catalog_fact", "derived_fact", "explicit_assumption", "recommendation"
]

GROUNDED_CLAIM_TYPES = frozenset(
    {"catalog_fact", "derived_fact", "explicit_assumption"}
)
"""A recommendation is an opinion. It is never scored as a catalog attribute."""


@dataclass(frozen=True, slots=True)
class ClaimVerdict:
    """One atomic claim and what the judge observed about its support.

    `evidence` names a field path, a computation or the assumption marker. It
    never carries captured customer or model wording.
    """

    claim_type: ClaimType
    evidence: str = ""
    field_path_present: bool = False
    same_sku: bool = False
    value_matches: bool = False
    computation_shown: bool = False
    marker_present: bool = False
    confirming_question: bool = False
    contradicts_known: bool = False
    appropriate: bool = True

    def __post_init__(self) -> None:
        if self.claim_type not in CLAIM_TYPES:
            raise ValueError(f"unknown claim_type {self.claim_type!r}")


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    scored_as: ClaimType
    passed: bool
    critical: bool
    reason: str
    reclassified: bool = False


def classify_claim(claim: ClaimVerdict) -> ClaimOutcome:
    """Decide one claim under the four-type taxonomy.

    The reclassification rule is what stops the taxonomy becoming a loophole.
    Calling something an assumption only earns the assumption's protection when
    the customer can actually see it is one, so an unmarked "assumption" is
    judged as the catalog fact it is pretending not to be.
    """
    if claim.claim_type == "recommendation":
        return ClaimOutcome(
            scored_as="recommendation",
            passed=claim.appropriate,
            critical=False,
            reason=(
                "recommendation judged on appropriateness, not as a catalog attribute"
            ),
        )

    if claim.claim_type == "explicit_assumption":
        if not (claim.marker_present and claim.confirming_question):
            missing = (
                "visible marker" if not claim.marker_present else "confirming question"
            )
            return ClaimOutcome(
                scored_as="catalog_fact",
                passed=False,
                critical=True,
                reason=(
                    f"assumption lacks a {missing}, so the customer reads it as a "
                    "stated fact; scored as catalog_fact"
                ),
                reclassified=True,
            )
        if claim.contradicts_known:
            return ClaimOutcome(
                scored_as="explicit_assumption",
                passed=False,
                critical=True,
                reason="labelled assumption contradicts data already in evidence",
            )
        return ClaimOutcome(
            scored_as="explicit_assumption",
            passed=True,
            critical=False,
            reason=(
                "labelled assumption with a confirming question, contradicting "
                "nothing known: not a fabrication"
            ),
        )

    if claim.claim_type == "derived_fact":
        if not claim.computation_shown:
            return ClaimOutcome(
                scored_as="derived_fact",
                passed=False,
                critical=True,
                reason="derived value stated without the computation that produces it",
            )
        if not (claim.field_path_present and claim.same_sku and claim.value_matches):
            return ClaimOutcome(
                scored_as="derived_fact",
                passed=False,
                critical=True,
                reason="derived value rests on a source that is absent from the row",
            )
        return ClaimOutcome(
            scored_as="derived_fact",
            passed=True,
            critical=False,
            reason="sources present and computation deterministic",
        )

    if not claim.field_path_present:
        return ClaimOutcome(
            scored_as="catalog_fact",
            passed=False,
            critical=True,
            reason="field path is absent from the retrieved row",
        )
    if not claim.same_sku:
        return ClaimOutcome(
            scored_as="catalog_fact",
            passed=False,
            critical=True,
            reason="field belongs to a different SKU than the one claimed",
        )
    if not claim.value_matches:
        return ClaimOutcome(
            scored_as="catalog_fact",
            passed=False,
            critical=True,
            reason="wording asserts more than the stored value supports",
        )
    return ClaimOutcome(
        scored_as="catalog_fact",
        passed=True,
        critical=False,
        reason="exact SKU, field path and value present",
    )


@dataclass(frozen=True, slots=True)
class ToolObedience:
    """Actions, graded on their own axis so style can never offset them."""

    required_calls_made: bool = True
    forbidden_call_made: bool = False
    effect_claimed_without_call: bool = False
    call_sequence_matches: bool = True

    @property
    def failures(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.required_calls_made:
            reasons.append("a required tool call was not made")
        if self.forbidden_call_made:
            reasons.append("a tool was called that the customer had refused")
        if self.effect_claimed_without_call:
            reasons.append("an effect was asserted that no successful call produced")
        if not self.call_sequence_matches:
            reasons.append("the observed tool sequence does not match the required one")
        return tuple(reasons)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class ConversationalQuality:
    """Style. Never folded into groundedness, in either direction."""

    clarity: int
    concision: int
    persuasion: int
    next_step: int

    def __post_init__(self) -> None:
        for name in ("clarity", "concision", "persuasion", "next_step"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer 1..5")
            if not 1 <= value <= 5:
                raise ValueError(f"{name} must be an integer 1..5")

    @property
    def normalized(self) -> float:
        return (self.clarity + self.concision + self.persuasion + self.next_step) / 20


@dataclass(frozen=True, slots=True)
class ResponseGrade:
    """Three axes, reported separately. There is deliberately no total."""

    groundedness: float | None
    grounded_claims_scored: int
    grounded_claims_failed: int
    tool_obedience_passed: bool
    conversational_quality: float
    critical_failure: bool
    critical_reasons: tuple[str, ...] = field(default_factory=tuple)
    outcomes: tuple[ClaimOutcome, ...] = field(default_factory=tuple)


def grade_response(
    claims: Sequence[ClaimVerdict],
    *,
    tool_obedience: ToolObedience,
    conversational_quality: ConversationalQuality,
) -> ResponseGrade:
    outcomes = tuple(classify_claim(claim) for claim in claims)
    grounded = [
        outcome for outcome in outcomes if outcome.scored_as in GROUNDED_CLAIM_TYPES
    ]
    failed = [outcome for outcome in grounded if not outcome.passed]
    reasons = [outcome.reason for outcome in grounded if outcome.critical]
    reasons.extend(tool_obedience.failures)
    return ResponseGrade(
        groundedness=(
            (len(grounded) - len(failed)) / len(grounded) if grounded else None
        ),
        grounded_claims_scored=len(grounded),
        grounded_claims_failed=len(failed),
        tool_obedience_passed=tool_obedience.passed,
        conversational_quality=conversational_quality.normalized,
        critical_failure=bool(reasons),
        critical_reasons=tuple(reasons),
        outcomes=outcomes,
    )


@dataclass(frozen=True, slots=True)
class AxisReport:
    """Per-model result. Each axis keeps its own denominator."""

    responses: int
    groundedness: float | None
    grounded_claims_scored: int
    grounded_claims_failed: int
    tool_obedience_rate: float
    conversational_quality: float
    critical_failures: int


def aggregate_grades(grades: Sequence[ResponseGrade]) -> AxisReport:
    if not grades:
        raise ValueError("aggregate_grades needs at least one graded response")
    scored = sum(grade.grounded_claims_scored for grade in grades)
    failed = sum(grade.grounded_claims_failed for grade in grades)
    return AxisReport(
        responses=len(grades),
        groundedness=(scored - failed) / scored if scored else None,
        grounded_claims_scored=scored,
        grounded_claims_failed=failed,
        tool_obedience_rate=sum(1 for grade in grades if grade.tool_obedience_passed)
        / len(grades),
        conversational_quality=sum(grade.conversational_quality for grade in grades)
        / len(grades),
        critical_failures=sum(1 for grade in grades if grade.critical_failure),
    )
