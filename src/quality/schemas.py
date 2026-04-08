"""Internal schemas and deterministic scoring helpers for quality evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QualityRating = Literal["excellent", "good", "satisfactory", "poor"]
RedFlagCode = Literal[
    "missing_identity",
    "hard_deflection",
    "unverified_commitment",
    "ignored_question",
    "bad_tone",
]

RULE_NAMES: dict[int, str] = {
    1: "Always greeting + name (Siyyad) + company (Treejar).",
    2: "Polite greeting and introduction.",
    3: "Asked how to address the customer.",
    4: "Friendly tone and active listening.",
    5: "Showed genuine interest in the client's needs.",
    6: "Gave a sincere compliment or appreciation.",
    7: "Briefly communicated Treejar's value proposition.",
    8: "Asked clarifying questions about requirements.",
    9: 'Applied the "drill and hole" principle.',
    10: "Proposed a comprehensive solution beyond the initial request.",
    11: "Offered a discount, bundle, or bonus.",
    12: "Collected contact details.",
    13: "Asked what the client's company does.",
    14: "Confirmed the order, details, and next step.",
    15: "Agreed the next contact if the client was not ready.",
}


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    block_name: str
    weight: float
    rules: tuple[int, ...]


BLOCK_DEFINITIONS: tuple[BlockDefinition, ...] = (
    BlockDefinition("Opening & Trust", 6.0, (1, 2, 3, 7)),
    BlockDefinition("Relationship & Discovery", 9.0, (4, 5, 6, 8, 13)),
    BlockDefinition("Consultative Solution", 9.0, (9, 10, 11)),
    BlockDefinition("Conversion & Next Step", 6.0, (12, 14, 15)),
)
BLOCKS_BY_NAME: dict[str, BlockDefinition] = {
    block.block_name: block for block in BLOCK_DEFINITIONS
}
RULE_TO_BLOCK: dict[int, BlockDefinition] = {
    rule_number: block for block in BLOCK_DEFINITIONS for rule_number in block.rules
}


class CriterionScore(BaseModel):
    """Score for a single evaluation criterion (0-2 scale)."""

    rule_number: int = Field(ge=1, le=15)
    rule_name: str
    score: int = Field(ge=0, le=2, description="0=not met, 1=partial, 2=fully met")
    comment: str
    applicable: bool = True
    n_a: bool = False
    category: str | None = None
    block_name: str | None = None
    weight_points: float | None = None
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_applicability(self) -> CriterionScore:
        if not self.applicable:
            self.score = 0
            self.n_a = True
        elif self.n_a:
            self.n_a = False
        return self


class BlockScore(BaseModel):
    """Deterministic weighted block score for final owner-facing reports."""

    block_name: str
    weight: float
    points: float
    applicable_rules: int


class EvaluationResult(BaseModel):
    """Structured output from the final LLM judge."""

    criteria: list[CriterionScore]
    summary: str
    total_score: float
    rating: QualityRating
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_best_action: str = ""
    block_scores: list[BlockScore] = Field(default_factory=list)


class RedFlagItem(BaseModel):
    """A critical realtime warning signal."""

    code: RedFlagCode
    title: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class RedFlagEvaluationResult(BaseModel):
    """Structured output from the red-flag evaluator."""

    flags: list[RedFlagItem] = Field(default_factory=list)
    recommended_action: str = ""


def compute_rating(score: float) -> QualityRating:
    """Compute quality rating label from total score (0-30 scale)."""
    if score >= 26:
        return "excellent"
    if score >= 20:
        return "good"
    if score >= 14:
        return "satisfactory"
    return "poor"


def _round_1(value: float) -> float:
    return round(value + 1e-9, 1)


def _clean_items(items: list[str], fallback: str) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return cleaned or [fallback]


def build_summary_text(
    strengths: list[str],
    weaknesses: list[str],
    recommendations: list[str],
    next_best_action: str,
) -> str:
    """Create a deterministic narrative summary from sectioned findings."""
    summary_lines = [
        "Что сделано хорошо:",
        *[
            f"- {item}"
            for item in _clean_items(
                strengths, "Явно выраженные сильные стороны не зафиксированы."
            )
        ],
        "",
        "Что ухудшило диалог:",
        *[
            f"- {item}"
            for item in _clean_items(
                weaknesses, "Существенные проблемы по диалогу не зафиксированы."
            )
        ],
        "",
        "Рекомендации:",
        *[
            f"- {item}"
            for item in _clean_items(
                recommendations, "Дополнительные рекомендации не зафиксированы."
            )
        ],
        "",
        "Следующее действие:",
        f"- {next_best_action.strip() or 'Проверить диалог вручную и определить следующий шаг по клиенту.'}",
    ]
    return "\n".join(summary_lines)


def canonicalize_criteria(
    criteria: list[CriterionScore],
    *,
    applicability_map: dict[int, bool] | None = None,
) -> list[CriterionScore]:
    """Normalize criteria shape and align rule applicability deterministically."""
    criteria_by_rule = {criterion.rule_number: criterion for criterion in criteria}
    canonical: list[CriterionScore] = []

    for rule_number in range(1, 16):
        original = criteria_by_rule[rule_number]
        block = RULE_TO_BLOCK[rule_number]
        applicable = (
            applicability_map[rule_number]
            if applicability_map is not None
            else original.applicable
        )
        evidence = [quote.strip() for quote in original.evidence if quote.strip()]
        canonical.append(
            CriterionScore(
                rule_number=rule_number,
                rule_name=original.rule_name.strip() or RULE_NAMES[rule_number],
                score=original.score if applicable else 0,
                comment=original.comment.strip(),
                applicable=applicable,
                n_a=not applicable,
                category=block.block_name,
                block_name=block.block_name,
                evidence=evidence,
            )
        )

    return canonical


def calculate_weighted_score(
    criteria: list[CriterionScore],
) -> tuple[float, list[BlockScore]]:
    """Compute weighted /30 score without penalizing non-applicable rules."""
    criteria_by_rule = {criterion.rule_number: criterion for criterion in criteria}
    block_scores: list[BlockScore] = []
    total_score_raw = 0.0

    for block in BLOCK_DEFINITIONS:
        applicable_criteria = [
            criteria_by_rule[rule_number]
            for rule_number in block.rules
            if criteria_by_rule[rule_number].applicable
        ]

        if not applicable_criteria:
            block_scores.append(
                BlockScore(
                    block_name=block.block_name,
                    weight=block.weight,
                    points=0.0,
                    applicable_rules=0,
                )
            )
            continue

        per_rule_weight = block.weight / len(applicable_criteria)
        raw_block_points = 0.0
        for criterion in applicable_criteria:
            raw_points = (criterion.score / 2) * per_rule_weight
            criterion.weight_points = round(raw_points, 3)
            criterion.category = block.block_name
            criterion.block_name = block.block_name
            raw_block_points += raw_points

        block_points = _round_1(raw_block_points)
        total_score_raw += raw_block_points
        block_scores.append(
            BlockScore(
                block_name=block.block_name,
                weight=block.weight,
                points=block_points,
                applicable_rules=len(applicable_criteria),
            )
        )

    total_score = _round_1(total_score_raw)
    return total_score, block_scores


def finalize_evaluation_result(
    result: EvaluationResult,
    *,
    applicability_map: dict[int, bool] | None = None,
) -> EvaluationResult:
    """Apply deterministic scoring, block breakdown, and summary formatting."""
    canonical_criteria = canonicalize_criteria(
        result.criteria,
        applicability_map=applicability_map,
    )
    total_score, block_scores = calculate_weighted_score(canonical_criteria)
    strengths = _clean_items(
        result.strengths, "Явно выраженные сильные стороны не зафиксированы."
    )
    weaknesses = _clean_items(
        result.weaknesses, "Существенные проблемы по диалогу не зафиксированы."
    )
    recommendations = _clean_items(
        result.recommendations, "Дополнительные рекомендации не зафиксированы."
    )
    next_best_action = (
        result.next_best_action.strip()
        or "Проверить диалог вручную и определить следующий шаг по клиенту."
    )

    return result.model_copy(
        update={
            "criteria": canonical_criteria,
            "summary": build_summary_text(
                strengths,
                weaknesses,
                recommendations,
                next_best_action,
            ),
            "total_score": total_score,
            "rating": compute_rating(total_score),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "next_best_action": next_best_action,
            "block_scores": block_scores,
        }
    )
