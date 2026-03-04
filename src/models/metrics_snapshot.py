from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MetricsSnapshot(TimestampMixin, Base):
    """Aggregated metrics snapshot, calculated periodically via ARQ."""

    __tablename__ = "metrics_snapshots"

    period: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # e.g., 'all_time', 'today'
    total_conversations: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    llm_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    escalations: Mapped[int] = mapped_column(Integer, default=0)
    deals_created: Mapped[int] = mapped_column(Integer, default=0)
    quotes_generated: Mapped[int] = mapped_column(Integer, default=0)
