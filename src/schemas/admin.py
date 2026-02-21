from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .common import Language, UUIDModel


class PromptRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    content: str
    version: int
    is_active: bool
    updated_at: datetime


class PromptUpdate(BaseModel):
    content: str
    description: str | None = None


class MetricsResponse(BaseModel):
    period: str
    total_conversations: int
    messages_sent: int
    avg_response_time_ms: float | None = None
    llm_cost_usd: float
    escalations: int
    deals_created: int
    quotes_generated: int


class SettingsRead(BaseModel):
    bot_enabled: bool
    default_language: Language
    auto_escalation_enabled: bool
    follow_up_enabled: bool
    max_messages_per_conversation: int


class SettingsUpdate(BaseModel):
    bot_enabled: bool | None = None
    default_language: Language | None = None
    auto_escalation_enabled: bool | None = None
    follow_up_enabled: bool | None = None
