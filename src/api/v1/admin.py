from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from src.schemas import (
    MetricsResponse,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
)

router = APIRouter()


@router.get("/prompts/", response_model=list[PromptRead])
async def list_prompts() -> list[PromptRead]:
    """List all prompt templates."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: uuid.UUID,
) -> PromptRead:
    """Get a specific prompt template."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
) -> PromptRead:
    """Update a prompt template (creates new version)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/metrics/", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get dashboard metrics for the current period."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/settings/", response_model=SettingsRead)
async def get_settings() -> SettingsRead:
    """Get current bot settings."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/settings/", response_model=SettingsRead)
async def update_settings(
    body: SettingsUpdate,
) -> SettingsRead:
    """Update bot settings."""
    raise HTTPException(status_code=501, detail="Not implemented")
