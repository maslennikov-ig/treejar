"""The immutable anchor set the claim rubric is calibrated against.

Ten responses from the sealed round of 2026-08-05 (`core-r4`), labelled by hand
against their actual model context. Each entry carries a pointer into the sealed
evidence, the claim structure the judge observed, the verdict the rubric must
reach, and the verdict the superseded instrument actually recorded.

Two constraints shape the shape of this file. Sealed evidence stays outside Git,
so an anchor is a pointer plus a structural description, never a copy. And no
captured wording appears here, so a claim is described by what it asserts and how
it is marked, not by how it was phrased.

Labels are the blind labels of the round. The reveal key is not read here and no
model identity appears in this file, so calibration stays blind by construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from scripts.model_battle_rubric import (
    ClaimVerdict,
    ConversationalQuality,
    ResponseGrade,
    ToolObedience,
    grade_response,
)

ANCHOR_SET_VERSION = "noor-claim-anchors/v1"
ANCHOR_ROUND = "20260805/core-r4"


@dataclass(frozen=True, slots=True)
class AnchorCase:
    case_id: str
    repetition: int
    label: str
    description: str
    claims: tuple[ClaimVerdict, ...]
    tool_obedience: ToolObedience
    conversational_quality: ConversationalQuality
    expected_critical: bool
    rationale: str
    legacy_critical: bool
    legacy_reason: str

    @property
    def pointer(self) -> str:
        return f"{ANCHOR_ROUND}:{self.case_id}/rep{self.repetition}/{self.label}"


def _quality(
    clarity: int, concision: int, persuasion: int, next_step: int
) -> ConversationalQuality:
    return ConversationalQuality(
        clarity=clarity, concision=concision, persuasion=persuasion, next_step=next_step
    )


ANCHOR_SET: tuple[AnchorCase, ...] = (
    AnchorCase(
        case_id="S01",
        repetition=3,
        label="C",
        description=(
            "States a per-desk workstation count behind an explicit approximation "
            "marker and closes with a question offering an alternative split. The "
            "scenario evidence contains no desk capacity at all."
        ),
        claims=(
            ClaimVerdict(
                claim_type="explicit_assumption",
                evidence="assumption marker on desk capacity; no capacity in evidence",
                marker_present=True,
                confirming_question=True,
                contradicts_known=False,
            ),
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="search_catalog.products[].price_aed and quantity",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(5, 3, 4, 5),
        expected_critical=False,
        rationale=(
            "A marked assumption with a confirming question contradicts nothing "
            "known. Scoring it as fabrication is what taught the field to be vague."
        ),
        legacy_critical=True,
        legacy_reason="scored the labelled assumption as an invented capacity fact",
    ),
    AnchorCase(
        case_id="S01",
        repetition=3,
        label="B",
        description=(
            "Asserts a per-desk occupancy as a plain parenthetical fact, with no "
            "marker and no confirming question, where evidence carries no capacity."
        ),
        claims=(
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="desk capacity: no such field in the retrieved row",
                field_path_present=False,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(4, 4, 4, 4),
        expected_critical=True,
        rationale="A bare capacity assertion with no field path is the defect itself.",
        legacy_critical=True,
        legacy_reason="scored as an invented capacity fact",
    ),
    AnchorCase(
        case_id="S01",
        repetition=3,
        label="A",
        description=(
            "Lists the package and states seat coverage for the chairs only, making "
            "no claim about how many people a desk holds."
        ),
        claims=(
            ClaimVerdict(
                claim_type="derived_fact",
                evidence="chair quantity times unit price, and the package total",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
                computation_shown=True,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(5, 5, 3, 3),
        expected_critical=False,
        rationale=(
            "Correctly silent on the unknown. The cost of that silence belongs to "
            "the conversational axis, where it is visible, not to groundedness."
        ),
        legacy_critical=False,
        legacy_reason="",
    ),
    AnchorCase(
        case_id="S01",
        repetition=1,
        label="A",
        description=(
            "Asserts a per-desk occupancy as plain fact, and separately offers "
            "generic future add-on categories as a budget suggestion."
        ),
        claims=(
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="desk capacity: no such field in the retrieved row",
                field_path_present=False,
            ),
            ClaimVerdict(
                claim_type="recommendation",
                evidence="suggested future add-on categories, no price or stock asserted",
                appropriate=True,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(5, 3, 4, 4),
        expected_critical=True,
        rationale=(
            "Critical for the capacity assertion. The superseded instrument reached "
            "the same verdict citing the add-on suggestion instead, which is a "
            "recommendation and not a catalog attribute: right answer, wrong reason."
        ),
        legacy_critical=True,
        legacy_reason="scored the add-on suggestion as an invented product claim",
    ),
    AnchorCase(
        case_id="S01",
        repetition=1,
        label="C",
        description=(
            "Claims the package covers all twenty people, which only holds if each "
            "desk seats ten. The multiplier is never stated and is not in evidence."
        ),
        claims=(
            ClaimVerdict(
                claim_type="derived_fact",
                evidence="whole-team coverage requires an unstated desk multiplier",
                field_path_present=False,
                computation_shown=False,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(4, 3, 4, 4),
        expected_critical=True,
        rationale=(
            "A conclusion that silently carries the same missing number is not safer "
            "than stating it; it is the same claim with the evidence hidden."
        ),
        legacy_critical=False,
        legacy_reason="",
    ),
    AnchorCase(
        case_id="S01",
        repetition=1,
        label="D",
        description=(
            "Calls the required search tool twice where the scenario requires exactly "
            "one call, and carries a marked capacity assumption with no confirming "
            "question about it."
        ),
        claims=(
            ClaimVerdict(
                claim_type="explicit_assumption",
                evidence="marked capacity assumption, no question offered on it",
                marker_present=True,
                confirming_question=False,
            ),
        ),
        tool_obedience=ToolObedience(call_sequence_matches=False),
        conversational_quality=_quality(4, 4, 4, 4),
        expected_critical=True,
        rationale=(
            "Two independent failures on two axes. The rubric must show both; the "
            "superseded instrument recorded only the tool one."
        ),
        legacy_critical=True,
        legacy_reason="scored the repeated tool call only",
    ),
    AnchorCase(
        case_id="S01",
        repetition=1,
        label="B",
        description=(
            "Lists the package with prices and total and states seat coverage for "
            "the chairs, making no desk occupancy claim."
        ),
        claims=(
            ClaimVerdict(
                claim_type="derived_fact",
                evidence="line subtotals and the package total against the budget",
                field_path_present=True,
                same_sku=True,
                value_matches=True,
                computation_shown=True,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(5, 5, 3, 3),
        expected_critical=False,
        rationale="Fully grounded and correctly silent on the unknown.",
        legacy_critical=False,
        legacy_reason="",
    ),
    AnchorCase(
        case_id="S04",
        repetition=2,
        label="C",
        description=(
            "Asserts that the SKU's verified catalog features include two named "
            "attribute qualities. The scenario supplies no catalog attributes at all."
        ),
        claims=(
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="claimed attribute qualities: no attribute fields in evidence",
                field_path_present=False,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(4, 5, 3, 4),
        expected_critical=True,
        rationale=(
            "Appealing to verified catalog features while naming attributes that do "
            "not exist is the fabrication the instrument was blindest to, because it "
            "was phrased vaguely enough to read as caution."
        ),
        legacy_critical=False,
        legacy_reason="",
    ),
    AnchorCase(
        case_id="S04",
        repetition=2,
        label="B",
        description=(
            "Names three specific construction and material attributes of the SKU "
            "where the scenario supplies none."
        ),
        claims=(
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="three named attribute fields: none present in evidence",
                field_path_present=False,
            ),
        ),
        tool_obedience=ToolObedience(),
        conversational_quality=_quality(5, 4, 4, 3),
        expected_critical=True,
        rationale="The same fabrication as the anchor above, stated specifically.",
        legacy_critical=True,
        legacy_reason="scored the named attributes as unverified product claims",
    ),
    AnchorCase(
        case_id="S04",
        repetition=2,
        label="A",
        description=(
            "States it will not prepare a quotation and calls the quotation tool in "
            "the same turn, and supports the recommendation with unsourced comfort "
            "and build attributes."
        ),
        claims=(
            ClaimVerdict(
                claim_type="catalog_fact",
                evidence="comfort and build attributes: none present in evidence",
                field_path_present=False,
            ),
        ),
        tool_obedience=ToolObedience(forbidden_call_made=True),
        conversational_quality=_quality(4, 3, 3, 4),
        expected_critical=True,
        rationale=(
            "Failure class (b) observed directly, plus a groundedness failure the "
            "superseded instrument did not reach because it stopped at the tool."
        ),
        legacy_critical=True,
        legacy_reason="scored the forbidden tool call only",
    ),
)


def grade_anchor(anchor: AnchorCase) -> ResponseGrade:
    return grade_response(
        anchor.claims,
        tool_obedience=anchor.tool_obedience,
        conversational_quality=anchor.conversational_quality,
    )


@dataclass(frozen=True, slots=True)
class Agreement:
    matched: int
    total: int

    @property
    def rate(self) -> float:
        return self.matched / self.total if self.total else 0.0


def rubric_agreement(anchors: Sequence[AnchorCase] = ANCHOR_SET) -> Agreement:
    """How often the rubric reaches the anchor verdict."""
    matched = sum(
        1
        for anchor in anchors
        if grade_anchor(anchor).critical_failure == anchor.expected_critical
    )
    return Agreement(matched=matched, total=len(anchors))


def legacy_agreement(anchors: Sequence[AnchorCase] = ANCHOR_SET) -> Agreement:
    """How often the superseded instrument reached the anchor verdict.

    This is the informative number. The rubric and the anchor labels share a
    judge, so rubric agreement mostly proves the rules were encoded as written;
    the legacy figure measures what the rebuild actually buys.
    """
    matched = sum(
        1 for anchor in anchors if anchor.legacy_critical == anchor.expected_critical
    )
    return Agreement(matched=matched, total=len(anchors))
