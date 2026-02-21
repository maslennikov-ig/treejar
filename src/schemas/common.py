from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Language(StrEnum):
    EN = "en"
    AR = "ar"


class SalesStage(StrEnum):
    GREETING = "greeting"
    QUALIFYING = "qualifying"
    NEEDS_ANALYSIS = "needs_analysis"
    SOLUTION = "solution"
    COMPANY_DETAILS = "company_details"
    QUOTING = "quoting"
    CLOSING = "closing"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ESCALATED = "escalated"


class EscalationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class QualityRating(StrEnum):
    EXCELLENT = "excellent"  # 26-30
    GOOD = "good"  # 20-25
    SATISFACTORY = "satisfactory"  # 14-19
    POOR = "poor"  # <14


class UUIDModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class TimestampModel(BaseModel):
    created_at: datetime
    updated_at: datetime | None = None


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
