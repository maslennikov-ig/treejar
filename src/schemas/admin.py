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


class SalesMetrics(BaseModel):
    count: int = 0
    amount: float = 0.0


class DashboardMetricsResponse(BaseModel):
    """Full dashboard metrics — 17 KPIs in 6 categories (docs/metrics.md)."""

    period: str  # "day", "week", "month", "all_time"

    # 1. Volume (3)
    total_conversations: int = 0
    unique_customers: int = 0
    new_vs_returning: dict[str, int] = {"new": 0, "returning": 0}

    # 2. Classification (3)
    by_segment: dict[str, int] = {}
    by_language: dict[str, int] = {}
    target_vs_nontarget: dict[str, int] = {"target": 0, "nontarget": 0}

    # 3. Escalation (2)
    escalation_count: int = 0
    escalation_reasons: dict[str, int] = {}

    # 4. Sales (4)
    noor_sales: SalesMetrics = SalesMetrics()
    post_escalation_sales: SalesMetrics = SalesMetrics()
    conversion_rate: float = 0.0
    average_deal_value: float = 0.0

    # 5. Quality (3)
    avg_conversation_length: float = 0.0
    avg_quality_score: float = 0.0
    avg_response_time_ms: float = 0.0

    # 6. Cost
    llm_cost_usd: float = 0.0


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
