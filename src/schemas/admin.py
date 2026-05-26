from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Language, SalesStage, UUIDModel
from .manager_review import ManagerLeaderboardEntry


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


class RecentFeedbackRead(BaseModel):
    conversation_id: uuid.UUID
    phone: str
    customer_name: str | None = None
    rating_overall: int
    rating_delivery: int
    recommend: bool
    comment: str | None = None
    created_at: datetime


class DashboardMetricsResponse(BaseModel):
    """Admin dashboard payload described in docs/metrics.md."""

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

    # 7. Manager performance
    avg_manager_score: float = 0.0
    avg_manager_response_time_seconds: float = 0.0
    manager_deal_conversion_rate: float = 0.0
    manager_leaderboard: list[ManagerLeaderboardEntry] = []

    # 8. Feedback
    feedback_count: int = 0
    avg_rating_overall: float = 0.0
    avg_rating_delivery: float = 0.0
    nps_score: float = 0.0
    recommend_rate: float = 0.0
    recent_feedback: list[RecentFeedbackRead] = Field(default_factory=list)


class NotificationConfigRead(BaseModel):
    telegram_configured: bool
    telegram_bot_token: str
    telegram_chat_id: str


class NotificationTestResponse(BaseModel):
    status: str
    reason: str | None = None


ClientSelfTestStatus = Literal["passed", "failed", "skipped", "not_tested"]


class ClientSelfTestItem(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=160)
    status: ClientSelfTestStatus
    note: str = Field(default="", max_length=800)


class ClientSelfTestSubmitRequest(BaseModel):
    tester_name: str | None = Field(default=None, max_length=80)
    overall_comment: str | None = Field(default=None, max_length=1000)
    items: list[ClientSelfTestItem] = Field(min_length=1, max_length=30)


class ClientSelfTestSubmitResponse(BaseModel):
    ok: bool
    submitted_count: int


class PendingManagerReviewRead(BaseModel):
    escalation_id: uuid.UUID
    conversation_id: uuid.UUID
    phone: str
    manager_name: str | None = None
    reason: str
    status: str
    updated_at: datetime


class TimeseriesPoint(BaseModel):
    """A single data point in a timeseries."""

    date: str  # ISO date string (YYYY-MM-DD)
    new: int = 0
    returning: int = 0


class TimeseriesResponse(BaseModel):
    """Timeseries data for charts."""

    period: str
    points: list[TimeseriesPoint] = []


class SettingsRead(BaseModel):
    bot_enabled: bool
    default_language: Language
    auto_escalation_enabled: bool
    telegram_test_mode_enabled: bool
    follow_up_enabled: bool
    max_messages_per_conversation: int


class SettingsUpdate(BaseModel):
    bot_enabled: bool | None = None
    default_language: Language | None = None
    auto_escalation_enabled: bool | None = None
    telegram_test_mode_enabled: bool | None = None
    follow_up_enabled: bool | None = None


class AdminActionAuditRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    request_path: str | None = None
    before: dict[str, Any] | list[Any] | None = None
    after: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] | list[Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime


BotRuleType = Literal[
    "hard_rule",
    "playbook",
    "upsell_rule",
    "style_rule",
    "escalation_rule",
]
BotRuleStatus = Literal["draft", "active", "archived"]
BotRuleScope = Literal["global", "stage", "language", "segment", "conversation"]


class AdminBotRuleApplied(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    priority: int
    scope: str
    instruction: str


class AdminBotRuleRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    type: str
    status: str
    priority: int
    scope: str
    stage: str | None = None
    language: str | None = None
    segment: str | None = None
    instruction: str
    trigger_examples: list[str] = Field(default_factory=list)
    has_embedding: bool = False
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime | None = None
    archived_at: datetime | None = None


class AdminBotRuleWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    type: BotRuleType = "playbook"
    status: BotRuleStatus = "draft"
    priority: int = Field(default=100, ge=0, le=1000)
    scope: BotRuleScope = "global"
    stage: SalesStage | None = None
    language: Language | None = None
    segment: str | None = Field(default=None, max_length=120)
    instruction: str = Field(min_length=1, max_length=5000)
    trigger_examples: list[str] = Field(default_factory=list, max_length=20)


class AdminBotRuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    type: BotRuleType | None = None
    status: BotRuleStatus | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    scope: BotRuleScope | None = None
    stage: SalesStage | None = None
    language: Language | None = None
    segment: str | None = Field(default=None, max_length=120)
    instruction: str | None = Field(default=None, min_length=1, max_length=5000)
    trigger_examples: list[str] | None = Field(default=None, max_length=20)


class AdminBotRulePreviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    stage: SalesStage | None = None
    language: Language | None = None
    segment: str | None = Field(default=None, max_length=120)
    conversation_id: uuid.UUID | None = None


class AdminBotRulePreviewResponse(BaseModel):
    applied_rules: list[AdminBotRuleApplied] = Field(default_factory=list)
    prompt_block: str
    rule_count: int


class AdminCustomerListItem(BaseModel):
    phone: str
    customer_name: str | None = None
    latest_conversation_id: uuid.UUID
    latest_message_at: datetime | None = None
    latest_message_preview: str | None = None
    conversation_count: int = 1
    status: str
    sales_stage: str
    language: str
    escalation_status: str
    deal_status: str | None = None
    zoho_contact_id: str | None = None
    zoho_deal_id: str | None = None
    segment: str | None = None
    updated_at: datetime | None = None


class AdminConversationListItem(UUIDModel):
    phone: str
    customer_name: str | None = None
    language: str
    sales_stage: str
    status: str
    escalation_status: str
    deal_status: str | None = None
    deal_amount: float | None = None
    zoho_contact_id: str | None = None
    zoho_deal_id: str | None = None
    message_count: int = 0
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    source: str | None = None
    segment: str | None = None
    utm: dict[str, Any] | None = None
    order_metadata: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AdminTimelineMessage(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    message_type: str
    created_at: datetime
    wazzup_message_id: str | None = None
    model: str | None = None
    cost: float | None = None
    audio_url: str | None = None
    transcription: str | None = None


class AdminEscalationRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    reason: str
    assigned_to: str | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AdminQualityReviewSummary(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    total_score: float
    max_score: int
    rating: str
    summary: str | None = None
    reviewer: str
    created_at: datetime


class AdminManagerReviewSummary(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    escalation_id: uuid.UUID
    conversation_id: uuid.UUID
    manager_name: str | None = None
    total_score: float
    max_score: int
    rating: str
    summary: str | None = None
    deal_converted: bool
    deal_amount: float | None = None
    reviewer: str
    created_at: datetime


class AdminFeedbackRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    deal_id: str | None = None
    rating_overall: int
    rating_delivery: int
    recommend: bool
    comment: str | None = None
    created_at: datetime


class AdminOutboundAuditRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    conversation_id: uuid.UUID
    message_type: str
    source: str
    status: str
    provider_message_id: str | None = None
    crm_message_id: str | None = None
    content: str | None = None
    caption: str | None = None
    error_details: dict[str, Any] | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


class AdminConversationDetail(AdminConversationListItem):
    timeline: list[AdminTimelineMessage] = Field(default_factory=list)
    escalations: list[AdminEscalationRead] = Field(default_factory=list)
    quality_reviews: list[AdminQualityReviewSummary] = Field(default_factory=list)
    manager_reviews: list[AdminManagerReviewSummary] = Field(default_factory=list)
    feedback: list[AdminFeedbackRead] = Field(default_factory=list)
    outbound_audits: list[AdminOutboundAuditRead] = Field(default_factory=list)
    applied_bot_rules: list[AdminBotRuleApplied] = Field(default_factory=list)


class AdminConversationUpdate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=80)
    sales_stage: str | None = Field(default=None, max_length=80)
    escalation_status: str | None = Field(default=None, max_length=80)
    deal_status: str | None = Field(default=None, max_length=80)
    language: Language | None = None


class AdminEscalationWrite(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    assigned_to: str | None = Field(default=None, max_length=255)
    status: str = Field(default="pending", max_length=80)
    notes: str | None = Field(default=None, max_length=4000)


class AdminEscalationClose(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class AdminResetPreviewRead(BaseModel):
    phone: str
    phone_variants: list[str]
    conversation_count: int
    latest_conversation_id: uuid.UUID | None = None
    message_count: int
    pending_escalation_count: int


class AdminResetExecuteRequest(BaseModel):
    confirm: bool = False


class AdminResetExecuteResponse(BaseModel):
    phone: str
    archived_count: int
    new_conversation_id: uuid.UUID | None = None


class AdminActionResult(BaseModel):
    ok: bool
    status: str
    entity_id: uuid.UUID | None = None
    detail: str | None = None


class AdminKnowledgeBaseRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    title: str
    content: str
    language: str
    category: str | None = None
    has_embedding: bool = False
    is_auto_generated: bool = False
    original_question: str | None = None
    manager_draft: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None


class AdminKnowledgeBaseWrite(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=8000)
    language: Language = Language.EN
    category: str | None = Field(default=None, max_length=120)


class AdminKnowledgeBaseUpdate(BaseModel):
    source: str | None = Field(default=None, min_length=1, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, min_length=1, max_length=8000)
    language: Language | None = None
    category: str | None = Field(default=None, max_length=120)


class AdminKnowledgeBasePreview(BaseModel):
    embedding_ready: bool
    duplicate: bool
    duplicate_similarity: float | None = None
    unsafe_reasons: list[str] = Field(default_factory=list)
    context_reasons: list[str] = Field(default_factory=list)


class AdminKnowledgeBaseCandidate(UUIDModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    question: str
    answer: str
    language: str
    confidence: float | None = None
    status: str
    guard_reasons: list[str] = Field(default_factory=list)
    duplicate_similarity: float | None = None
    original_question: str | None = None
    manager_draft: str | None = None
    customer_message: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime
    updated_at: datetime | None = None


class AdminKnowledgeBaseCandidateCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    language: Language = Language.EN
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    original_question: str | None = Field(default=None, max_length=500)
    manager_draft: str | None = Field(default=None, max_length=2000)
    customer_message: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class AdminKnowledgeBaseCandidateReject(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
