from __future__ import annotations

from .admin import (
    MetricsResponse,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
)
from .common import (
    ConversationStatus,
    ErrorResponse,
    EscalationStatus,
    Language,
    PaginatedResponse,
    QualityRating,
    SalesStage,
    TimestampModel,
    UUIDModel,
)
from .conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from .crm import (
    ContactCreate,
    ContactRead,
    DealCreate,
    DealRead,
    DealUpdate,
)
from .health import DependencyHealth, HealthCheckResponse
from .inventory import (
    SaleOrderCreate,
    SaleOrderItem,
    SaleOrderRead,
    StockLevel,
)
from .product import (
    ProductRead,
    ProductSearchQuery,
    ProductSearchResult,
    ProductSyncRequest,
    ProductSyncResponse,
)
from .quality import (
    QualityCriterion,
    QualityReportRequest,
    QualityReportResponse,
    QualityReviewCreate,
    QualityReviewRead,
)
from .webhook import (
    WazzupIncomingMessage,
    WazzupMedia,
    WazzupWebhookPayload,
    WazzupWebhookResponse,
)

__all__ = [
    # common
    "ConversationStatus",
    "ErrorResponse",
    "EscalationStatus",
    "Language",
    "PaginatedResponse",
    "QualityRating",
    "SalesStage",
    "TimestampModel",
    "UUIDModel",
    # health
    "DependencyHealth",
    "HealthCheckResponse",
    # webhook
    "WazzupIncomingMessage",
    "WazzupMedia",
    "WazzupWebhookPayload",
    "WazzupWebhookResponse",
    # conversation
    "ConversationCreate",
    "ConversationDetail",
    "ConversationRead",
    "ConversationUpdate",
    "MessageCreate",
    "MessageRead",
    # product
    "ProductRead",
    "ProductSearchQuery",
    "ProductSearchResult",
    "ProductSyncRequest",
    "ProductSyncResponse",
    # crm
    "ContactCreate",
    "ContactRead",
    "DealCreate",
    "DealRead",
    "DealUpdate",
    # inventory
    "SaleOrderCreate",
    "SaleOrderItem",
    "SaleOrderRead",
    "StockLevel",
    # quality
    "QualityCriterion",
    "QualityReportRequest",
    "QualityReportResponse",
    "QualityReviewCreate",
    "QualityReviewRead",
    # admin
    "MetricsResponse",
    "PromptRead",
    "PromptUpdate",
    "SettingsRead",
    "SettingsUpdate",
]
