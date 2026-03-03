from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_redis
from src.core.database import get_db
from src.models.system_config import SystemConfig
from src.models.system_prompt import SystemPrompt
from src.schemas import (
    MetricsResponse,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
)

router = APIRouter()


@router.get("/prompts/", response_model=list[PromptRead])
async def list_prompts(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SystemPrompt]:
    """List all prompt templates."""
    stmt = select(SystemPrompt).order_by(SystemPrompt.name, SystemPrompt.version.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemPrompt:
    """Get a specific prompt template."""
    prompt = await db.get(SystemPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@router.put("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SystemPrompt:
    """Update a prompt template (creates new version)."""
    old_prompt = await db.get(SystemPrompt, prompt_id)
    if not old_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Inactivate old prompt
    old_prompt.is_active = False

    # Create new version
    new_prompt = SystemPrompt(
        name=old_prompt.name,
        content=body.content,
        version=old_prompt.version + 1,
        is_active=True,
    )
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)

    # Invalidate the cache cache
    cache_key = f"prompt:{old_prompt.name}"
    await redis.delete(cache_key)

    return new_prompt


@router.get("/metrics/", response_model=MetricsResponse)
async def get_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MetricsResponse:
    """Get dashboard metrics for the current period."""
    from src.models.conversation import Conversation
    from src.models.message import Message

    # Total conversations
    total_convs = await db.scalar(select(func.count(Conversation.id))) or 0

    # Messages sent by assistant
    msgs_sent = await db.scalar(
        select(func.count(Message.id)).where(Message.role == "assistant")
    ) or 0

    # LLM Cost USD
    cost = await db.scalar(
        select(func.sum(Message.cost))
    ) or 0.0

    # Escalations
    escalations = await db.scalar(
        select(func.count(Conversation.id)).where(Conversation.escalation_status != "none")
    ) or 0

    # Deals created
    deals = await db.scalar(
        select(func.count(Conversation.id)).where(Conversation.zoho_deal_id.is_not(None))
    ) or 0

    # Quotes generated (assuming message_type == 'quote' or just 0 for now)
    quotes = await db.scalar(
        select(func.count(Message.id)).where(Message.message_type == "quote")
    ) or 0

    return MetricsResponse(
        period="all_time",
        total_conversations=total_convs,
        messages_sent=msgs_sent,
        avg_response_time_ms=0.0,
        llm_cost_usd=float(cost),
        escalations=escalations,
        deals_created=deals,
        quotes_generated=quotes,
    )


def _parse_bool(val: str | None, default: bool) -> bool:
    if val is None:
        return default
    return val.lower() == "true"


@router.get("/settings/", response_model=SettingsRead)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRead:
    """Get current bot settings."""
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    configs = {c.key: c.value for c in result.scalars().all()}

    return SettingsRead(
        bot_enabled=_parse_bool(configs.get("bot_enabled"), True),
        default_language=configs.get("default_language", "en"),
        auto_escalation_enabled=_parse_bool(configs.get("auto_escalation_enabled"), True),
        follow_up_enabled=_parse_bool(configs.get("follow_up_enabled"), True),
        max_messages_per_conversation=int(configs.get("max_messages_per_conversation", "50")),
    )


@router.patch("/settings/", response_model=SettingsRead)
async def update_settings(
    body: SettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRead:
    """Update bot settings."""
    update_data = body.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        stmt = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(stmt)
        config = result.scalars().first()

        if isinstance(value, bool):
            str_val = "true" if value else "false"
        else:
            str_val = str(value)

        if config:
            config.value = str_val
        else:
            db.add(SystemConfig(key=key, value=str_val))

    await db.commit()

    # Return updated settings
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    configs = {c.key: c.value for c in result.scalars().all()}

    return SettingsRead(
        bot_enabled=_parse_bool(configs.get("bot_enabled"), True),
        default_language=configs.get("default_language", "en"),
        auto_escalation_enabled=_parse_bool(configs.get("auto_escalation_enabled"), True),
        follow_up_enabled=_parse_bool(configs.get("follow_up_enabled"), True),
        max_messages_per_conversation=int(configs.get("max_messages_per_conversation", "50")),
    )
