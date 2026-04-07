from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.deps import get_redis
from src.core.database import get_db
from src.models.system_config import SystemConfig
from src.models.system_prompt import SystemPrompt
from src.schemas import (
    DashboardMetricsResponse,
    MetricsResponse,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
    TimeseriesResponse,
)


async def require_admin_session(request: Request) -> None:
    """Verify the admin session token (same as SQLAdmin session auth)."""
    try:
        token = request.session.get("token")
    except AssertionError:
        # SessionMiddleware not installed — treat as unauthenticated
        raise HTTPException(
            status_code=401, detail="Admin authentication required"
        ) from None
    if token != "admin_session":
        raise HTTPException(status_code=401, detail="Admin authentication required")


router = APIRouter(dependencies=[Depends(require_admin_session)])

PeriodType = Literal["day", "week", "month", "all_time"]


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
    """Get dashboard metrics from the aggregated snapshot."""
    from src.models.metrics_snapshot import MetricsSnapshot

    snapshot = await db.get(MetricsSnapshot, "all_time")
    if not snapshot:
        # Return zeros if job hasn't run yet
        return MetricsResponse(
            period="all_time",
            total_conversations=0,
            messages_sent=0,
            avg_response_time_ms=0.0,
            llm_cost_usd=0.0,
            escalations=0,
            deals_created=0,
            quotes_generated=0,
        )

    return MetricsResponse(
        period=snapshot.period,
        total_conversations=snapshot.total_conversations,
        messages_sent=snapshot.messages_sent,
        avg_response_time_ms=snapshot.avg_response_time_ms,
        llm_cost_usd=snapshot.llm_cost_usd,
        escalations=snapshot.escalations,
        deals_created=snapshot.deals_created,
        quotes_generated=snapshot.quotes_generated,
    )


@router.get("/dashboard/metrics/", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodType = "all_time",
) -> DashboardMetricsResponse:
    """Get comprehensive dashboard metrics (17 KPIs, 6 categories).

    Query params:
        period: day | week | month | all_time (default: all_time)
    """
    from src.services.dashboard_metrics import calculate_dashboard_metrics

    return await calculate_dashboard_metrics(db, period)


@router.get("/dashboard/timeseries/", response_model=TimeseriesResponse)
async def get_dashboard_timeseries(
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodType = "all_time",
) -> TimeseriesResponse:
    """Get daily new vs returning conversation timeseries.

    Query params:
        period: day | week | month | all_time (default: all_time)
    """
    from src.services.dashboard_metrics import calculate_timeseries

    return await calculate_timeseries(db, period)


@router.get("/settings/", response_model=SettingsRead)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRead:
    """Get current bot settings."""
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    configs = {c.key: c.value for c in result.scalars().all()}

    return SettingsRead(
        bot_enabled=bool(configs.get("bot_enabled", True)),
        default_language=str(configs.get("default_language", "en")),
        auto_escalation_enabled=bool(configs.get("auto_escalation_enabled", True)),
        telegram_test_mode_enabled=bool(
            configs.get("telegram_test_mode_enabled", True)
        ),
        follow_up_enabled=bool(configs.get("follow_up_enabled", True)),
        max_messages_per_conversation=int(
            str(configs.get("max_messages_per_conversation", 50))
        ),
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

        if config:
            config.value = (
                value  # SQLAlchemy JSONB handles dict/bool/int types effortlessly
            )
        else:
            db.add(SystemConfig(key=key, value=value))

    await db.commit()

    # Return updated settings
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    configs = {c.key: c.value for c in result.scalars().all()}

    return SettingsRead(
        bot_enabled=bool(configs.get("bot_enabled", True)),
        default_language=str(configs.get("default_language", "en")),
        auto_escalation_enabled=bool(configs.get("auto_escalation_enabled", True)),
        telegram_test_mode_enabled=bool(
            configs.get("telegram_test_mode_enabled", True)
        ),
        follow_up_enabled=bool(configs.get("follow_up_enabled", True)),
        max_messages_per_conversation=int(
            str(configs.get("max_messages_per_conversation", 50))
        ),
    )
