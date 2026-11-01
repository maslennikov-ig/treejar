from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.deps import get_redis
from src.api.v1 import notifications as notifications_api
from src.api.v1.manager_reviews import (
    evaluate_escalation_with_settings,
    list_manager_reviews,
)
from src.api.v1.reports import (
    ReportRequest,
    ReportResponse,
    generate_report_endpoint,
)
from src.core.config import settings
from src.core.config_bool import parse_config_bool
from src.core.database import get_db
from src.core.redis import get_redis_client
from src.integrations.inventory.stock_state import (
    LEGACY_KEY as ZOHO_SNAPSHOT_LEGACY_KEY,
)
from src.integrations.inventory.stock_state import (
    STATE_KEY as ZOHO_STOCK_STATE_KEY,
)
from src.integrations.inventory.stock_state import (
    StockState,
)
from src.models.bot_behavior_rule import BotBehaviorRule
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.knowledge_base import KnowledgeBase
from src.models.manager_review import ManagerReview
from src.models.message import Message
from src.models.product import Product
from src.models.system_config import SystemConfig
from src.models.system_prompt import SystemPrompt
from src.quality.config import (
    AIQualityControlsConfig,
    AIQualityControlsUpdate,
    AIQualityScope,
    get_ai_quality_controls_config,
    get_ai_quality_usage_today,
    merge_ai_quality_controls_update,
    save_ai_quality_controls_config,
)
from src.schemas import (
    ClientSelfTestSubmitRequest,
    ClientSelfTestSubmitResponse,
    DashboardMetricsResponse,
    ManagerReviewDetail,
    ManagerReviewRead,
    MetricsResponse,
    NotificationConfigRead,
    NotificationTestResponse,
    PaginatedResponse,
    PendingManagerReviewRead,
    ProductSyncRequest,
    PromptRead,
    PromptUpdate,
    SettingsRead,
    SettingsUpdate,
    TimeseriesResponse,
)
from src.schemas.admin import (
    AdminCatalogStatusResponse,
    AdminCatalogSyncSourceStatus,
    AdminSessionInfoResponse,
    AdminSystemHealthContour,
    AdminSystemHealthResponse,
    AdminZohoSnapshotStatus,
    AIQualityControlsResponse,
    RecentFeedbackRead,
    build_admin_ai_quality_response,
)
from src.schemas.admin import (
    AdminProductSyncResponse as ProductSyncResponse,
)
from src.services.admin_audit import log_admin_action
from src.services.admin_crm import (
    admin_ai_quality_evaluator_kwargs,
    record_admin_ai_quality_spend,
    require_admin_ai_quality_manual_gate,
    reserve_admin_ai_quality_manual_call,
)
from src.services.client_self_test import format_client_self_test_summary
from src.services.followup import (
    PaymentReminderControlsConfig,
    PaymentReminderControlsResponse,
    PaymentReminderControlsUpdate,
    build_payment_reminder_response,
    get_payment_reminder_controls_config,
    merge_payment_reminder_controls_update,
    save_payment_reminder_controls_config,
)
from src.services.notifications import send_telegram_message
from src.services.referrals import (
    ReferralPolicyResponse,
    build_referral_policy_response,
    get_referral_policy_config,
)

logger = logging.getLogger(__name__)


async def record_best_effort_admin_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None = None,
    before: dict[str, Any] | list[Any] | None = None,
    after: dict[str, Any] | list[Any] | None = None,
    metadata: dict[str, Any] | list[Any] | None = None,
    request: Request | None = None,
) -> None:
    """Persist an admin action audit entry without failing non-DB operator endpoints."""
    try:
        await log_admin_action(
            db,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            metadata=metadata,
            request=request,
        )
        await db.commit()
    except Exception:
        logger.warning("Failed to persist admin audit entry %s", action, exc_info=True)
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            try:
                maybe = rollback()
                if hasattr(maybe, "__await__"):
                    await maybe
            except Exception:
                pass


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


@router.get("/session", response_model=AdminSessionInfoResponse)
async def get_admin_session_info(request: Request) -> AdminSessionInfoResponse:
    """Return active admin session metadata for the header account menu."""
    raw_method = request.session.get("auth_method")
    auth_method: Literal["telegram", "password", "session"] = (
        raw_method if raw_method in ("telegram", "password") else "session"
    )
    display_name = request.session.get("admin_display_name")
    username = request.session.get("admin_username")
    actor = request.session.get("admin_actor")
    return AdminSessionInfoResponse(
        authenticated=True,
        auth_method=auth_method,
        display_name=str(display_name) if display_name else None,
        username=str(username) if username else None,
        actor=str(actor) if actor else "admin",
        logout_url="/admin/logout",
        sqladmin_url="/admin/",
    )


_PROMPT_DESCRIPTIONS_CONFIG_KEY = "prompt_descriptions"


async def _load_prompt_descriptions(db: AsyncSession) -> dict[str, str]:
    try:
        row = await db.get(SystemConfig, _PROMPT_DESCRIPTIONS_CONFIG_KEY)
    except Exception:
        return {}
    raw = getattr(row, "value", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in raw.items()
        if isinstance(k, str) and isinstance(v, str)
    }


async def _save_prompt_description(
    db: AsyncSession, prompt_name: str, description: str | None
) -> None:
    if description is None:
        return
    try:
        row = await db.get(SystemConfig, _PROMPT_DESCRIPTIONS_CONFIG_KEY)
    except Exception:
        row = None
    existing = getattr(row, "value", None)
    next_map = dict(existing) if isinstance(existing, dict) else {}
    next_map[prompt_name] = description
    if row is not None and isinstance(row, SystemConfig):
        row.value = next_map
    else:
        db.add(
            SystemConfig(
                key=_PROMPT_DESCRIPTIONS_CONFIG_KEY,
                value=next_map,
                description="Admin prompt descriptions keyed by prompt name",
            )
        )


def _attach_prompt_description(
    prompt: SystemPrompt, descriptions: dict[str, str]
) -> SystemPrompt:
    current = getattr(prompt, "description", None)
    if current is None and prompt.name in descriptions:
        prompt.description = descriptions[prompt.name]  # type: ignore[attr-defined]
    return prompt


@router.get("/prompts/", response_model=list[PromptRead])
async def list_prompts(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SystemPrompt]:
    """List all prompt templates."""
    stmt = select(SystemPrompt).order_by(SystemPrompt.name, SystemPrompt.version.desc())
    result = await db.execute(stmt)
    prompts = list(result.scalars().all())
    descriptions = await _load_prompt_descriptions(db)
    return [_attach_prompt_description(prompt, descriptions) for prompt in prompts]


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemPrompt:
    """Get a specific prompt template."""
    prompt = await db.get(SystemPrompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    descriptions = await _load_prompt_descriptions(db)
    return _attach_prompt_description(prompt, descriptions)


@router.put("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> SystemPrompt:
    """Update a prompt template (creates new version)."""
    old_prompt = await db.get(SystemPrompt, prompt_id)
    if not old_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    descriptions = await _load_prompt_descriptions(db)
    old_description = getattr(old_prompt, "description", None)
    if old_description is None:
        old_description = descriptions.get(old_prompt.name)

    before = {
        "id": str(old_prompt.id),
        "name": old_prompt.name,
        "description": old_description,
        "version": old_prompt.version,
        "content": old_prompt.content,
    }

    # Inactivate old prompt
    old_prompt.is_active = False

    next_description = (
        body.description if body.description is not None else old_description
    )

    # Create new version
    new_prompt = SystemPrompt(
        name=old_prompt.name,
        content=body.content,
        version=old_prompt.version + 1,
        is_active=True,
    )
    db.add(new_prompt)
    await _save_prompt_description(db, old_prompt.name, next_description)
    await db.flush()
    await log_admin_action(
        db,
        action="prompt.update",
        entity_type="system_prompt",
        entity_id=new_prompt.id,
        before=before,
        after={
            "id": str(new_prompt.id),
            "name": new_prompt.name,
            "description": next_description,
            "version": new_prompt.version,
            "content": new_prompt.content,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(new_prompt)
    new_prompt.description = next_description  # type: ignore[attr-defined]

    # Invalidate the prompt cache
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


@router.get("/feedback/recent", response_model=list[RecentFeedbackRead])
async def get_admin_recent_feedback(
    db: Annotated[AsyncSession, Depends(get_db)],
    period: PeriodType = "all_time",
    limit: int = Query(5, ge=1, le=20),
) -> list[RecentFeedbackRead]:
    """List recent post-delivery feedback inside the admin session."""
    from src.services.dashboard_metrics import list_recent_feedback

    return await list_recent_feedback(db, period=period, limit=limit)


@router.get("/referrals/policy", response_model=ReferralPolicyResponse)
async def get_admin_referral_policy(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReferralPolicyResponse:
    """Expose referral launch policy status without applying discounts."""
    return build_referral_policy_response(await get_referral_policy_config(db))


@router.get("/notifications/config", response_model=NotificationConfigRead)
async def get_admin_notification_config() -> NotificationConfigRead:
    """Expose masked Telegram configuration inside the admin session boundary."""
    data = await notifications_api.get_notification_config()
    return NotificationConfigRead.model_validate(data)


@router.post("/notifications/test", response_model=NotificationTestResponse)
async def send_admin_test_notification(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTestResponse:
    """Trigger a Telegram test notification from the dashboard."""
    data = await notifications_api.send_test_notification()
    parsed = NotificationTestResponse.model_validate(data)
    await record_best_effort_admin_audit(
        db,
        action="notification.test",
        entity_type="notification",
        entity_id="telegram",
        after=parsed.model_dump(mode="json"),
        request=request,
    )
    return parsed


@router.post(
    "/client-self-test/submit",
    response_model=ClientSelfTestSubmitResponse,
)
async def submit_client_self_test(
    body: ClientSelfTestSubmitRequest,
) -> ClientSelfTestSubmitResponse:
    """Receive a client acceptance checklist and forward the summary to Telegram."""
    await send_telegram_message(format_client_self_test_summary(body))
    return ClientSelfTestSubmitResponse(ok=True, submitted_count=len(body.items))


_CATALOG_SYNC_REDIS_KEY_PREFIX = "admin:catalog:last_sync:"
_LAST_CATALOG_SYNC_SOURCES: dict[str, dict[str, Any]] = {}


async def record_catalog_sync_status(
    *,
    source_key: str,
    last_status: str,
    job_name: str | None,
    detail: str | None,
) -> None:
    """Persist catalog sync trigger status in Redis with an in-memory fallback."""
    now = datetime.now(UTC)
    _LAST_CATALOG_SYNC_SOURCES[source_key] = {
        "source": source_key,
        "last_triggered_at": now,
        "last_status": last_status,
        "job_name": job_name,
        "detail": detail,
    }
    payload = {
        "source": source_key,
        "last_triggered_at": now.isoformat(),
        "last_status": last_status,
        "job_name": job_name,
        "detail": detail,
    }
    try:
        redis = get_redis_client()
        await redis.set(
            f"{_CATALOG_SYNC_REDIS_KEY_PREFIX}{source_key}",
            json.dumps(payload),
        )
    except Exception:
        logger.debug(
            "Redis unavailable while saving catalog sync status", exc_info=True
        )


async def _read_catalog_sync_source_state(source_key: str) -> dict[str, Any] | None:
    """Read catalog sync trigger status from Redis first, falling back to memory."""
    try:
        redis = get_redis_client()
        raw = await redis.get(f"{_CATALOG_SYNC_REDIS_KEY_PREFIX}{source_key}")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if isinstance(raw, str) and raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                ts = parsed.get("last_triggered_at")
                if isinstance(ts, str) and ts:
                    try:
                        parsed["last_triggered_at"] = datetime.fromisoformat(ts)
                    except ValueError:
                        parsed["last_triggered_at"] = None
                return parsed
    except Exception:
        logger.debug(
            "Redis unavailable while reading catalog sync status", exc_info=True
        )
    return _LAST_CATALOG_SYNC_SOURCES.get(source_key)


async def _read_zoho_snapshot_status(
    *, raise_on_error: bool = False
) -> AdminZohoSnapshotStatus:
    """Inspect Redis for Zoho stock snapshot freshness without external calls."""
    try:
        redis = get_redis_client()
        raw_v2 = await redis.get(ZOHO_STOCK_STATE_KEY)
        state = StockState.from_raw(raw_v2) if raw_v2 else None
        if state is not None:
            latest_ts = max(
                [
                    ts
                    for ts in [
                        state.full_at,
                        state.delta_at,
                        *(state.observed.values() if state.observed else []),
                    ]
                    if isinstance(ts, int | float) and ts > 0
                ],
                default=None,
            )
            ttl = await redis.ttl(ZOHO_STOCK_STATE_KEY)
            ttl_val = int(ttl) if isinstance(ttl, int) and ttl >= 0 else None
            age_sec = (
                max(0, int(time.time() - latest_ts)) if latest_ts is not None else None
            )
            updated_dt = (
                datetime.fromtimestamp(latest_ts, UTC)
                if latest_ts is not None
                else None
            )
            fresh = age_sec is not None and age_sec <= 3600
            return AdminZohoSnapshotStatus(
                present=True,
                status="fresh" if fresh else "stale",
                item_count=len(state.items),
                updated_at=updated_dt,
                age_seconds=age_sec,
                ttl_seconds=ttl_val,
            )

        raw_v1 = await redis.get(ZOHO_SNAPSHOT_LEGACY_KEY)
        if raw_v1:
            ttl = await redis.ttl(ZOHO_SNAPSHOT_LEGACY_KEY)
            ttl_val = int(ttl) if isinstance(ttl, int) and ttl >= 0 else None
            parsed = json.loads(raw_v1) if isinstance(raw_v1, str | bytes) else {}
            items = parsed.get("items", parsed) if isinstance(parsed, dict) else {}
            item_count = len(items) if isinstance(items, dict | list) else 0
            return AdminZohoSnapshotStatus(
                present=True,
                status="fresh" if (ttl_val is None or ttl_val > 300) else "stale",
                item_count=item_count,
                updated_at=None,
                age_seconds=None,
                ttl_seconds=ttl_val,
            )
    except Exception:
        if raise_on_error:
            raise
    return AdminZohoSnapshotStatus(present=False, status="missing", item_count=0)


@router.post("/products/sync", response_model=ProductSyncResponse)
async def trigger_admin_product_sync(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[ProductSyncRequest, Body(default_factory=ProductSyncRequest)],
) -> ProductSyncResponse:
    """Queue a protected product sync via the shared admin session."""
    from src.api.v1.products import enqueue_product_sync

    result, source_key, job_name = await enqueue_product_sync(
        body=body,
        request=request,
    )
    await record_catalog_sync_status(
        source_key=source_key,
        last_status="queued",
        job_name=job_name,
        detail=f"Queued {source_key} sync job",
    )
    await record_best_effort_admin_audit(
        db,
        action="catalog.sync",
        entity_type="product_sync",
        entity_id=source_key,
        after={"source": source_key, "job_name": job_name, "status": "queued"},
        request=request,
    )
    return result


@router.get("/catalog/status", response_model=AdminCatalogStatusResponse)
async def get_admin_catalog_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogStatusResponse:
    """Return persisted catalog sync status, product counts, and Zoho stock freshness."""
    active_count = 0
    total_count = 0
    indexed_count = 0
    latest_product_update: datetime | None = None
    try:
        active_count = int(
            await db.scalar(
                select(func.count())
                .select_from(Product)
                .where(Product.is_active.is_(True))
            )
            or 0
        )
        total_count = int(
            await db.scalar(select(func.count()).select_from(Product)) or 0
        )
        indexed_count = int(
            await db.scalar(
                select(func.count())
                .select_from(Product)
                .where(Product.is_active.is_(True), Product.embedding.is_not(None))
            )
            or 0
        )
        latest_product_update = await db.scalar(select(func.max(Product.updated_at)))
    except Exception:
        pass

    zoho_snapshot = await _read_zoho_snapshot_status()
    treejar_state = await _read_catalog_sync_source_state("treejar")
    zoho_state = await _read_catalog_sync_source_state("zoho")

    treejar_status = AdminCatalogSyncSourceStatus(
        source="treejar",
        last_triggered_at=(
            treejar_state.get("last_triggered_at")
            if treejar_state
            else latest_product_update
        ),
        last_status=(
            str(treejar_state.get("last_status", "queued"))
            if treejar_state
            else ("synced" if active_count > 0 else "never")
        ),
        job_name="sync_products_from_treejar_catalog",
        detail=(
            treejar_state.get("detail")
            if treejar_state
            else (f"Active products: {active_count}" if active_count > 0 else None)
        ),
    )
    zoho_status = AdminCatalogSyncSourceStatus(
        source="zoho",
        last_triggered_at=(
            zoho_state.get("last_triggered_at")
            if zoho_state
            else zoho_snapshot.updated_at
        ),
        last_status=(
            str(zoho_state.get("last_status", "queued"))
            if zoho_state
            else ("synced" if zoho_snapshot.present else "never")
        ),
        job_name="sync_products_from_zoho",
        detail=(
            zoho_state.get("detail")
            if zoho_state
            else (
                f"Snapshot items: {zoho_snapshot.item_count}"
                if zoho_snapshot.present
                else None
            )
        ),
    )
    return AdminCatalogStatusResponse(
        active_products_count=active_count,
        total_products_count=total_count,
        indexed_products_count=indexed_count,
        sources={"treejar": treejar_status, "zoho": zoho_status},
        zoho_snapshot=zoho_snapshot,
    )


@router.get("/system/health", response_model=AdminSystemHealthResponse)
async def get_admin_system_health(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminSystemHealthResponse:
    """Return real operational contour checks without exposing secrets."""
    now = datetime.now(UTC)
    active_kb = 0
    active_rules = 0
    open_escalations = 0
    pending_reviews = 0
    last_inbound: datetime | None = None

    try:
        open_escalations = int(
            await db.scalar(
                select(func.count())
                .select_from(Escalation)
                .where(
                    Escalation.status.in_(["pending", "in_progress", "manual_takeover"])
                )
            )
            or 0
        )
        pending_reviews_list = await list_pending_manager_reviews(db, limit=50)
        pending_reviews = len(pending_reviews_list)
    except Exception:
        logger.warning("System health queue counter check failed", exc_info=True)

    # 1. WhatsApp / Wazzup contour
    try:
        last_inbound = await db.scalar(
            select(func.max(Message.created_at)).where(Message.role == "user")
        )
        raw_bot_enabled = await db.scalar(
            select(SystemConfig.value).where(SystemConfig.key == "bot_enabled")
        )
        bot_enabled = parse_config_bool(raw_bot_enabled, default=True)
        wa_configured = bool(getattr(settings, "wazzup_api_key", None))
        whatsapp_contour = AdminSystemHealthContour(
            id="whatsapp",
            label="WhatsApp / Wazzup",
            status="ok" if (wa_configured and bot_enabled) else "warning",
            summary="active" if (wa_configured and bot_enabled) else "paused",
            detail=(
                f"Last inbound: {last_inbound.isoformat()}"
                if last_inbound
                else "Ready for inbound messages"
            ),
            updated_at=last_inbound,
        )
    except Exception as exc:
        logger.warning("System health WhatsApp contour check failed", exc_info=True)
        whatsapp_contour = AdminSystemHealthContour(
            id="whatsapp",
            label="WhatsApp / Wazzup",
            status="error",
            summary="error",
            detail=f"Health check failed ({type(exc).__name__})",
        )

    # 2. Telegram contour
    try:
        tg_configured = bool(
            getattr(settings, "telegram_bot_token", None)
            and getattr(settings, "telegram_chat_id", None)
        )
        telegram_contour = AdminSystemHealthContour(
            id="telegram",
            label="Telegram Bot & Alerts",
            status="ok" if tg_configured else "warning",
            summary="configured" if tg_configured else "not_configured",
            detail="Webhook & operator alerts active"
            if tg_configured
            else "Missing token or chat ID",
        )
    except Exception as exc:
        logger.warning("System health Telegram contour check failed", exc_info=True)
        telegram_contour = AdminSystemHealthContour(
            id="telegram",
            label="Telegram Bot & Alerts",
            status="error",
            summary="error",
            detail=f"Health check failed ({type(exc).__name__})",
        )

    # 3. Zoho Inventory contour
    try:
        zoho_snapshot = await _read_zoho_snapshot_status(raise_on_error=True)
        zoho_contour = AdminSystemHealthContour(
            id="zoho_inventory",
            label="Zoho Inventory & Stock",
            status="ok" if zoho_snapshot.status == "fresh" else "warning",
            summary=zoho_snapshot.status,
            detail=f"Snapshot SKU count: {zoho_snapshot.item_count}",
            updated_at=zoho_snapshot.updated_at,
        )
    except Exception as exc:
        logger.warning("System health Zoho contour check failed", exc_info=True)
        zoho_contour = AdminSystemHealthContour(
            id="zoho_inventory",
            label="Zoho Inventory & Stock",
            status="error",
            summary="error",
            detail=f"Snapshot check failed ({type(exc).__name__})",
        )

    # 4. RAG Knowledge & Rules contour
    try:
        active_kb = int(
            await db.scalar(
                select(func.count())
                .select_from(KnowledgeBase)
                .where(KnowledgeBase.deleted_at.is_(None))
            )
            or 0
        )
        active_rules = int(
            await db.scalar(
                select(func.count())
                .select_from(BotBehaviorRule)
                .where(
                    BotBehaviorRule.archived_at.is_(None),
                    BotBehaviorRule.status == "active",
                )
            )
            or 0
        )
        rag_contour = AdminSystemHealthContour(
            id="knowledge_rag",
            label="RAG Knowledge & Rules",
            status="ok" if (active_kb > 0 and active_rules > 0) else "warning",
            summary="ready" if (active_kb > 0 and active_rules > 0) else "needs_seed",
            detail=f"KB: {active_kb}, Rules: {active_rules}",
        )
    except Exception as exc:
        logger.warning("System health RAG contour check failed", exc_info=True)
        rag_contour = AdminSystemHealthContour(
            id="knowledge_rag",
            label="RAG Knowledge & Rules",
            status="error",
            summary="error",
            detail=f"Knowledge check failed ({type(exc).__name__})",
        )

    # 5. LLM Runtime contour
    try:
        llm_configured = bool(getattr(settings, "openrouter_api_key", None))
        llm_contour = AdminSystemHealthContour(
            id="llm_engine",
            label="LLM Runtime (OpenRouter)",
            status="ok" if llm_configured else "warning",
            summary="connected" if llm_configured else "unconfigured",
            detail=str(getattr(settings, "openrouter_model_main", "configured")),
        )
    except Exception as exc:
        logger.warning("System health LLM contour check failed", exc_info=True)
        llm_contour = AdminSystemHealthContour(
            id="llm_engine",
            label="LLM Runtime (OpenRouter)",
            status="error",
            summary="error",
            detail=f"Runtime check failed ({type(exc).__name__})",
        )

    contours: list[AdminSystemHealthContour] = [
        whatsapp_contour,
        telegram_contour,
        zoho_contour,
        rag_contour,
        llm_contour,
    ]
    overall: Literal["ok", "warning", "error"] = (
        "error"
        if any(c.status == "error" for c in contours)
        else ("warning" if any(c.status == "warning" for c in contours) else "ok")
    )
    return AdminSystemHealthResponse(
        overall_status=overall,
        contours=contours,
        last_inbound_message_at=last_inbound,
        active_kb_count=active_kb,
        active_bot_rules_count=active_rules,
        open_escalations_count=open_escalations,
        pending_manager_reviews_count=pending_reviews,
        checked_at=now,
    )


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
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ManagerReviewDetail:
    """Run a manager review from the dashboard operator surface."""
    gate = await require_admin_ai_quality_manual_gate(db, AIQualityScope.MANAGER_QA)

    async def reserve_call() -> None:
        await reserve_admin_ai_quality_manual_call(gate)

    async def record_spend(evaluation: Any) -> None:
        await record_admin_ai_quality_spend(gate, evaluation)

    result = await evaluate_escalation_with_settings(
        escalation_id,
        db,
        evaluator_kwargs=admin_ai_quality_evaluator_kwargs(gate),
        before_llm_call=reserve_call,
        after_llm_call=record_spend,
    )
    await log_admin_action(
        db,
        action="quality.manager_review",
        entity_type="escalation",
        entity_id=escalation_id,
        after={
            "review_id": str(result.id),
            "total_score": result.total_score,
            "rating": result.rating,
        },
        request=request,
    )
    await db.commit()
    return result


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
    """Read SystemConfig-backed AI Quality Controls plus today's usage."""
    config = await get_ai_quality_controls_config(db)
    usage_today = await get_ai_quality_usage_today(config)
    return build_admin_ai_quality_response(config, usage_today=usage_today)


@router.put("/ai-quality-controls", response_model=AIQualityControlsResponse)
async def put_admin_ai_quality_controls(
    body: AIQualityControlsConfig,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIQualityControlsResponse:
    """Replace SystemConfig-backed AI Quality Controls."""
    before = (await get_ai_quality_controls_config(db)).model_dump(mode="json")
    saved = await save_ai_quality_controls_config(db, body)
    await log_admin_action(
        db,
        action="ai_quality_controls.replace",
        entity_type="system_config",
        entity_id="ai_quality_controls",
        before=before,
        after=saved.model_dump(mode="json"),
        request=request,
    )
    await db.commit()
    usage_today = await get_ai_quality_usage_today(saved)
    return build_admin_ai_quality_response(saved, usage_today=usage_today)


@router.patch("/ai-quality-controls", response_model=AIQualityControlsResponse)
async def patch_admin_ai_quality_controls(
    body: AIQualityControlsUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIQualityControlsResponse:
    """Merge a partial SystemConfig-backed AI Quality Controls update."""
    current = await get_ai_quality_controls_config(db)
    before = current.model_dump(mode="json")
    merged = merge_ai_quality_controls_update(current, body)
    saved = await save_ai_quality_controls_config(db, merged)
    await log_admin_action(
        db,
        action="ai_quality_controls.update",
        entity_type="system_config",
        entity_id="ai_quality_controls",
        before=before,
        after=saved.model_dump(mode="json"),
        request=request,
    )
    await db.commit()
    usage_today = await get_ai_quality_usage_today(saved)
    return build_admin_ai_quality_response(saved, usage_today=usage_today)


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
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentReminderControlsResponse:
    """Replace SystemConfig-backed payment reminder controls."""
    before = (await get_payment_reminder_controls_config(db)).model_dump(mode="json")
    saved = await save_payment_reminder_controls_config(db, body)
    await log_admin_action(
        db,
        action="payment_reminder_controls.replace",
        entity_type="system_config",
        entity_id="payment_reminder_controls",
        before=before,
        after=saved.model_dump(mode="json"),
        request=request,
    )
    await db.commit()
    return build_payment_reminder_response(saved)


@router.patch(
    "/payment-reminder-controls",
    response_model=PaymentReminderControlsResponse,
)
async def patch_admin_payment_reminder_controls(
    body: PaymentReminderControlsUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentReminderControlsResponse:
    """Merge a partial SystemConfig-backed payment reminder controls update."""
    current = await get_payment_reminder_controls_config(db)
    before = current.model_dump(mode="json")
    merged = merge_payment_reminder_controls_update(current, body)
    saved = await save_payment_reminder_controls_config(db, merged)
    await log_admin_action(
        db,
        action="payment_reminder_controls.update",
        entity_type="system_config",
        entity_id="payment_reminder_controls",
        before=before,
        after=saved.model_dump(mode="json"),
        request=request,
    )
    await db.commit()
    return build_payment_reminder_response(saved)


def _build_settings_read(configs: dict[str, Any]) -> SettingsRead:
    return SettingsRead(
        bot_enabled=parse_config_bool(configs.get("bot_enabled"), default=True),
        telegram_test_mode_enabled=parse_config_bool(
            configs.get("telegram_test_mode_enabled"), default=True
        ),
    )


@router.get("/settings/", response_model=SettingsRead)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRead:
    """Get current bot settings."""
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    configs = {c.key: c.value for c in result.scalars().all()}
    return _build_settings_read(configs)


@router.patch("/settings/", response_model=SettingsRead)
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsRead:
    """Update bot settings."""
    stmt = select(SystemConfig)
    result = await db.execute(stmt)
    existing_rows = {c.key: c for c in result.scalars().all()}
    before_settings = _build_settings_read(
        {key: row.value for key, row in existing_rows.items()}
    )

    update_data = body.model_dump(exclude_unset=True)
    updated_values = {key: row.value for key, row in existing_rows.items()}

    for key, value in update_data.items():
        config = existing_rows.get(key)
        if config:
            config.value = value
        else:
            new_row = SystemConfig(key=key, value=value)
            db.add(new_row)
            existing_rows[key] = new_row
        updated_values[key] = value

    after_settings = _build_settings_read(updated_values)
    if update_data:
        await log_admin_action(
            db,
            action="settings.update",
            entity_type="system_config",
            entity_id="settings",
            before=before_settings.model_dump(mode="json"),
            after=after_settings.model_dump(mode="json"),
            metadata={"updated_fields": sorted(update_data)},
            request=request,
        )

    await db.commit()
    return after_settings
