"""Shared schemas for Auto-FAQ candidate review."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AutoFAQCandidate(BaseModel):
    """Generalized FAQ candidate proposed from a manager reply."""

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    language: str = Field(default="en", min_length=2, max_length=8)
