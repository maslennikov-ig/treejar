from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron

from src.core.config import settings
from src.integrations.inventory.sync import sync_products_from_zoho
from src.llm.conversation_summary import refresh_conversation_summary
from src.quality.job import (
    evaluate_mature_conversations_quality,
    evaluate_realtime_red_flags,
    evaluate_recent_conversations_quality,
)
from src.quality.manager_job import evaluate_escalated_conversations
from src.rag.embeddings import EmbeddingEngine
from src.services.chat import process_incoming_batch
from src.services.followup import run_automatic_followups, run_feedback_requests
from src.services.metrics import calculate_and_store_metrics
from src.services.notifications import run_daily_summary
from src.services.reports import run_weekly_report

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup — initialize shared resources.

    ARQ provides ctx["redis"] automatically. We configure logging
    and verify critical settings are present.
    """
    # Configure root logger for structured output in Docker
    logging.basicConfig(
        level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )

    # Verify critical settings
    if not settings.wazzup_channel_id:
        logger.warning("WAZZUP_CHANNEL_ID is not set — bot cannot send replies!")
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY is not set — LLM calls will fail!")

    logger.info(
        "ARQ worker started. channel_id=%s, model=%s, log_level=%s",
        settings.wazzup_channel_id[:8] + "..."
        if settings.wazzup_channel_id
        else "MISSING",
        settings.openrouter_model_main,
        settings.app_log_level,
    )

    try:
        await EmbeddingEngine().warmup_async()
        logger.info("Embedding model warmed up successfully.")
    except Exception:
        logger.warning(
            "Embedding model warmup failed during worker startup; "
            "continuing with lazy loading.",
            exc_info=True,
        )


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown — log clean exit."""
    logger.info("ARQ worker shutting down.")


class WorkerSettings:
    functions: list[Any] = [
        sync_products_from_zoho,
        process_incoming_batch,
        refresh_conversation_summary,
        run_automatic_followups,
        run_feedback_requests,
        calculate_and_store_metrics,
        evaluate_realtime_red_flags,
        evaluate_mature_conversations_quality,
        evaluate_recent_conversations_quality,
        evaluate_escalated_conversations,
        run_daily_summary,
        run_weekly_report,
    ]
    cron_jobs = [
        cron(
            sync_products_from_zoho,
            hour={0, 6, 12, 18},
            minute={0},
            run_at_startup=False,
        ),
        cron(run_automatic_followups, minute={0}, run_at_startup=False),
        cron(run_feedback_requests, hour={10}, minute={0}, run_at_startup=False),
        cron(
            calculate_and_store_metrics,
            minute={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
        ),
        cron(
            evaluate_mature_conversations_quality,
            minute={0},
            run_at_startup=False,
        ),
        cron(
            evaluate_realtime_red_flags,
            minute={30},
            run_at_startup=False,
        ),
        cron(
            evaluate_escalated_conversations,
            minute={0, 30},
            run_at_startup=False,
        ),
        cron(run_daily_summary, hour={6}, minute={0}, run_at_startup=False),
        cron(
            run_weekly_report,
            weekday={0},
            hour={6},
            minute={0},
            run_at_startup=False,
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 600  # 10 min — accommodate large catalogs (856+ SKU)
    max_jobs = 2
    keep_result = 3600  # keep results for 1 hour for debugging
