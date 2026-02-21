from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .common import QualityRating, UUIDModel


class QualityCriterion(BaseModel):
    rule_number: int = Field(ge=1, le=15)
    rule_name: str
    score: int = Field(ge=0, le=2)
    max_score: int = 2
    comment: str | None = None


class QualityReviewCreate(BaseModel):
    conversation_id: uuid.UUID
    criteria: list[QualityCriterion]
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
