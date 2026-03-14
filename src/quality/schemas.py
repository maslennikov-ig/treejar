"""Internal LLM schemas for the Quality Evaluator.

Separate from src/schemas/quality.py (which are the API-facing schemas).
These are used by the PydanticAI judge agent for structured output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """Score for a single evaluation criterion (0-2 scale)."""

    rule_number: int = Field(ge=1, le=15)
    rule_name: str
    score: int = Field(ge=0, le=2, description="0=not met, 1=partial, 2=fully met")
    comment: str


class EvaluationResult(BaseModel):
    """Structured output from the LLM judge agent.

    The agent is expected to return exactly 15 criteria, one per rule.
    """

    criteria: list[CriterionScore]
    summary: str
    total_score: float
    rating: Literal["excellent", "good", "satisfactory", "poor"]


def compute_rating(score: float) -> str:
    """Compute quality rating label from total score (0-30 scale).

    Thresholds per docs/06-dialogue-evaluation-checklist.md:
        26-30 -> excellent
        20-25 -> good
        14-19 -> satisfactory
        <14   -> poor
    """
    if score >= 26:
        return "excellent"
    elif score >= 20:
        return "good"
    elif score >= 14:
        return "satisfactory"
    else:
        return "poor"
