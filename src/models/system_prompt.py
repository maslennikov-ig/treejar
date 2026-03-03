from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class SystemPrompt(TimestampMixin, UUIDMixin, Base):
    """System prompts used by the LLM."""

    __tablename__ = "system_prompts"

    # Unique name for the prompt
    name: Mapped[str] = mapped_column(String, index=True)

    # Content of the prompt
    content: Mapped[str] = mapped_column(Text)

    # Version of the prompt
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Whether the prompt is currently active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_system_prompt_name_version"),
    )
