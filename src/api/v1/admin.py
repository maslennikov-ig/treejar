from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.deps import get_redis
from src.api.v1 import notifications as notifications_api
from src.api.v1.manager_reviews import evaluate_escalation, list_manager_reviews
from src.api.v1.reports import (
    ReportRequest,
    ReportResponse,
    generate_report_endpoint,
)
from src.core.database import get_db
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.manager_review import ManagerReview
from src.models.system_config import SystemConfig
from src.models.system_prompt import SystemPrompt
from src.quality.config import (
    AIQualityControlsConfig,
    AIQualityControlsResponse,
    AIQualityControlsUpdate,
    build_ai_quality_response,
    get_ai_quality_controls_config,
    merge_ai_quality_controls_update,
    save_ai_quality_controls_config,
)
from src.schemas import (
    DashboardMetricsResponse,
    ManagerReviewDetail,
    ManagerReviewRead,
    MetricsResponse,
    NotificationConfigRead,
    NotificationTestResponse,
    PaginatedResponse,
    PendingManagerReviewRead,
    ProductSyncRequest,
    ProductSyncResponse,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
    TimeseriesResponse,
)
from src.services.followup import (
    PaymentReminderControlsConfig,
    PaymentReminderControlsResponse,
    PaymentReminderControlsUpdate,
    build_payment_reminder_response,
    get_payment_reminder_controls_config,
    merge_payment_reminder_controls_update,
    save_payment_reminder_controls_config,
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
    """Get the current admin dashboard metrics payload.

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


@router.get("/notifications/config", response_model=NotificationConfigRead)
async def get_admin_notification_config() -> NotificationConfigRead:
    """Expose masked Telegram configuration inside the admin session boundary."""
    data = await notifications_api.get_notification_config()
    return NotificationConfigRead.model_validate(data)


@router.post("/notifications/test", response_model=NotificationTestResponse)
async def send_admin_test_notification() -> NotificationTestResponse:
    """Trigger a Telegram test notification from the dashboard."""
    data = await notifications_api.send_test_notification()
    return NotificationTestResponse.model_validate(data)


@router.post("/products/sync", response_model=ProductSyncResponse)
async def trigger_admin_product_sync(
    request: Request,
    body: Annotated[ProductSyncRequest, Body(default_factory=ProductSyncRequest)],
) -> ProductSyncResponse:
    """Queue a protected product sync via the shared admin session."""
    from src.api.v1.products import sync_products as sync_products_endpoint

    return await sync_products_endpoint(body=body, request=request, _=None)


@router.get(
    "/manager-reviews/",
    response_model=PaginatedResponse[ManagerReviewRead],
)
async def get_admin_manager_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manager_name: str | None = None,
    rating: str | None = None,
    period: Literal["day", "week", "month"] | None = None,
) -> PaginatedResponse[ManagerReviewRead]:
    """List recent manager reviews for the dashboard operator surface."""
    return await list_manager_reviews(
        db=db,
        page=page,
        page_size=page_size,
        manager_name=manager_name,
        rating=rating,
        period=period,
    )


@router.get(
    "/manager-reviews/pending",
    response_model=list[PendingManagerReviewRead],
)
async def get_admin_pending_manager_reviews(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
) -> list[PendingManagerReviewRead]:
    """List resolved escalations that still need manual manager evaluation."""
    return await list_pending_manager_reviews(db=db, limit=limit)


async def list_pending_manager_reviews(
    db: AsyncSession,
    limit: int = 10,
) -> list[PendingManagerReviewRead]:
    """Fetch resolved escalations that still need manual manager evaluation."""
    from sqlalchemy import exists as sa_exists

    stmt = (
        select(
            Escalation.id.label("escalation_id"),
            Escalation.conversation_id,
            Conversation.phone,
            Escalation.assigned_to.label("manager_name"),
            Escalation.reason,
            Escalation.status,
            Escalation.updated_at,
        )
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(
            Escalation.status == "resolved",
            ~sa_exists().where(ManagerReview.escalation_id == Escalation.id),
        )
        .order_by(Escalation.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)

    return [
        PendingManagerReviewRead(
            escalation_id=row.escalation_id,
            conversation_id=row.conversation_id,
            phone=row.phone,
            manager_name=row.manager_name,
            reason=row.reason,
            status=row.status,
            updated_at=row.updated_at,
        )
        for row in result.all()
    ]


@router.post(
    "/manager-reviews/{escalation_id}/evaluate",
    response_model=ManagerReviewDetail,
)
async def evaluate_admin_manager_review(
    escalation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ManagerReviewDetail:
    """Run a manager review from the dashboard operator surface."""
    return await evaluate_escalation(escalation_id=escalation_id, db=db)


@router.post("/reports/generate", response_model=ReportResponse)
async def generate_admin_report(
    body: Annotated[ReportRequest, Body(default_factory=ReportRequest)],
) -> ReportResponse:
    """Generate the operator-facing weekly report inside the admin session."""
    return await generate_report_endpoint(body)


@router.get("/ai-quality-controls", response_model=AIQualityControlsResponse)
async def get_admin_ai_quality_controls(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIQualityControlsResponse:
    """Read SystemConfig-backed AI Quality Controls."""
    return build_ai_quality_response(await get_ai_quality_controls_config(db))


@router.put("/ai-quality-controls", response_model=AIQualityControlsResponse)
async def put_admin_ai_quality_controls(
    body: AIQualityControlsConfig,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIQualityControlsResponse:
    """Replace SystemConfig-backed AI Quality Controls."""
    saved = await save_ai_quality_controls_config(db, body)
    return build_ai_quality_response(saved)


@router.patch("/ai-quality-controls", response_model=AIQualityControlsResponse)
async def patch_admin_ai_quality_controls(
    body: AIQualityControlsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIQualityControlsResponse:
    """Merge a partial SystemConfig-backed AI Quality Controls update."""
    current = await get_ai_quality_controls_config(db)
    merged = merge_ai_quality_controls_update(current, body)
    saved = await save_ai_quality_controls_config(db, merged)
    return build_ai_quality_response(saved)


@router.get(
    "/payment-reminder-controls", response_model=PaymentReminderControlsResponse
)
async def get_admin_payment_reminder_controls(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentReminderControlsResponse:
    """Read SystemConfig-backed payment reminder controls."""
    return build_payment_reminder_response(
        await get_payment_reminder_controls_config(db)
    )


@router.put(
    "/payment-reminder-controls", response_model=PaymentReminderControlsResponse
)
async def put_admin_payment_reminder_controls(
    body: PaymentReminderControlsConfig,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentReminderControlsResponse:
    """Replace SystemConfig-backed payment reminder controls."""
    saved = await save_payment_reminder_controls_config(db, body)
    return build_payment_reminder_response(saved)


@router.patch(
    "/payment-reminder-controls",
    response_model=PaymentReminderControlsResponse,
)
async def patch_admin_payment_reminder_controls(
    body: PaymentReminderControlsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentReminderControlsResponse:
    """Merge a partial SystemConfig-backed payment reminder controls update."""
    current = await get_payment_reminder_controls_config(db)
    merged = merge_payment_reminder_controls_update(current, body)
    saved = await save_payment_reminder_controls_config(db, merged)
    return build_payment_reminder_response(saved)


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
