from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import QualityRating, UUIDModel


class QualityCriterion(BaseModel):
    rule_number: int = Field(ge=1, le=15)
    rule_name: str
    score: int = Field(ge=0, le=2)
    max_score: int = 2
    comment: str | None = None
    category: str | None = None
    block_name: str | None = None
    applicable: bool | None = None
    n_a: bool | None = None
    weight_points: float | None = None
    evidence: list[str] = Field(default_factory=list)


class QualityReviewCreate(BaseModel):
    conversation_id: uuid.UUID
    criteria: list[QualityCriterion] | None = None  # ignored if provided; LLM evaluates
    summary: str | None = None
    reviewer: str = "ai"


class QualityReviewRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    total_score: float
    max_score: int = 30
    rating: QualityRating
    criteria: list[QualityCriterion]
    summary: str | None = None
    reviewer: str
    created_at: datetime

    @field_validator("criteria", mode="before")
    @classmethod
    def normalize_legacy_criteria(cls, value: Any) -> Any:
        """Tolerate legacy rows where criteria was stored as a JSON object."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            if not value:
                return []
            if {"rule_number", "rule_name", "score"}.issubset(value):
                return [value]
            values = list(value.values())
            if all(isinstance(item, dict) for item in values):
                return values
            return []
        return value


class QualityReportRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_score: float | None = None


class QualityReportResponse(BaseModel):
    period: str
    total_conversations: int
    reviewed: int
    average_score: float
    rating_distribution: dict[str, int]
    top_issues: list[str]
