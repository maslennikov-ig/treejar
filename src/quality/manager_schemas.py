"""Internal LLM schemas for the Manager Evaluator.

Separate from API-facing schemas. Used by the PydanticAI judge agent
for structured output when evaluating manager conversations.

Scale: 0-2 per criterion, 10 criteria, max 20 points.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The owner-facing short name for each of the ten criteria, mirroring RULE_NAMES
# in src/quality/schemas.py. These are the criteria of MANAGER_EVALUATION_PROMPT
# said in a few words, for a report where the full sentence will not fit.
MANAGER_RULE_NAMES: dict[int, str] = {
    1: "Fast pickup after the bot.",
    2: "Used the context already collected.",
    3: "Professional tone.",
    4: "Resolved the reason for the escalation.",
    5: "Proactivity and additional options.",
    6: "Objection handling.",
    7: "Movement towards closing.",
    8: "Completeness of information.",
    9: "Collected data for the CRM/quotation.",
    10: "Recorded the outcome and the next step.",
}


class ManagerCriterionScore(BaseModel):
    """Score for a single manager evaluation criterion (0-2 scale)."""

    rule_number: int = Field(ge=1, le=10)
    rule_name: str
    score: int = Field(ge=0, le=2, description="0=not met, 1=partial, 2=fully met")
    comment: str


class ManagerEvaluationResult(BaseModel):
    """Structured output from the manager LLM judge agent.

    The agent is expected to return exactly 10 criteria, one per rule.
    """

    criteria: list[ManagerCriterionScore]
    summary: str
    total_score: float
    rating: Literal["excellent", "good", "satisfactory", "poor"]


def compute_manager_rating(score: float) -> str:
    """Compute manager rating label from total score (0-20 scale).

    Thresholds per docs/08-manager-evaluation-criteria.md:
        17-20 -> excellent
        13-16 -> good
        9-12  -> satisfactory
        <9    -> poor
    """
    if score >= 17:
        return "excellent"
    elif score >= 13:
        return "good"
    elif score >= 9:
        return "satisfactory"
    else:
        return "poor"
