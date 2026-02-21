from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.escalation import Escalation
    from src.models.message import Message
    from src.models.quality_review import QualityReview


class Conversation(UUIDMixin, TimestampMixin, Base):
    """A WhatsApp conversation with a customer."""

    __tablename__ = "conversations"

    phone: Mapped[str] = mapped_column(String, index=True)
    customer_name: Mapped[str | None] = mapped_column(String, default=None)
    zoho_contact_id: Mapped[str | None] = mapped_column(String, default=None)
    zoho_deal_id: Mapped[str | None] = mapped_column(String, default=None)
    language: Mapped[str] = mapped_column(String, default="en")
    sales_stage: Mapped[str] = mapped_column(String, default="greeting")
    status: Mapped[str] = mapped_column(String, default="active")
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True, default=None
    )

    # Relationships
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
    )
    quality_reviews: Mapped[list[QualityReview]] = relationship(
        back_populates="conversation",
    )
    escalations: Mapped[list[Escalation]] = relationship(
        back_populates="conversation",
    )
