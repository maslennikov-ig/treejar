from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import (
    ConversationStatus,
    EscalationStatus,
    Language,
    SalesStage,
    TimestampModel,
    UUIDModel,
)


class ConversationCreate(BaseModel):
    phone: str
    language: Language = Language.EN


class ConversationRead(UUIDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    customer_name: str | None = None
    language: Language
    sales_stage: SalesStage
    status: ConversationStatus
    escalation_status: EscalationStatus = EscalationStatus.NONE
    zoho_contact_id: str | None = None
    zoho_deal_id: str | None = None


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    sales_stage: SalesStage | None = None
    escalation_status: EscalationStatus | None = None
    customer_name: str | None = None


class MessageCreate(BaseModel):
    conversation_id: uuid.UUID
    role: str
    content: str
    message_type: str = "text"


class MessageRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    role: str
    content: str
    message_type: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost: float | None = None
    model: str | None = None
    created_at: datetime
