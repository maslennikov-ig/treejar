from __future__ import annotations

from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin

class SystemConfig(TimestampMixin, Base):
    """Global system configuration stored as key/value pairs."""

    __tablename__ = "system_configs"

    # The settings key (e.g., 'openrouter_model_main')
    key: Mapped[str] = mapped_column(String, primary_key=True)
    
    # The value of the setting (stored as string/text, can be JSON)
    value: Mapped[str] = mapped_column(Text)
    
    # Optional description of what this key does
    description: Mapped[str | None] = mapped_column(Text, default=None)
