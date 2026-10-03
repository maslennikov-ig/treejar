from __future__ import annotations

import logging
from datetime import UTC
from typing import Any

from arq import func
from arq.connections import RedisSettings
from arq.cron import cron

from src.core.config import settings
from src.core.safe_logging import install_sensitive_url_filter
from src.integrations.inventory.sync import (
    refresh_zoho_stock_delta,
    refresh_zoho_stock_snapshot,
    sync_products_from_treejar_catalog,
    sync_products_from_zoho,
)
from src.integrations.notifications.telegram_webhook import reconcile_telegram_webhook
from src.llm.conversation_summary import refresh_conversation_summary
from src.quality.job import (
    evaluate_mature_conversations_quality,
    evaluate_realtime_red_flags,
    evaluate_recent_conversations_quality,
)
from src.quality.manager_job import evaluate_escalated_conversations
from src.rag.embeddings import EmbeddingEngine
from src.services.chat import INBOUND_BATCH_MAX_TRIES, process_incoming_batch
from src.services.followup import run_automatic_followups, run_feedback_requests
from src.services.metrics import calculate_and_store_metrics
from src.services.notifications import run_daily_summary
from src.services.proposal_followup import run_proposal_followups
from src.services.quotation_retry import retry_pending_quotation
from src.services.reports import run_weekly_report
from src.services.runtime_monitoring import run_runtime_monitoring

logger = logging.getLogger(__name__)

# On SIGTERM the worker stops taking jobs and lets a running customer turn
# finish before it is cancelled. Without this, a deploy that landed mid-turn
# cancelled it, and the at-most-once guard then quarantined the message with
# no reply sent (2026-09-28). A turn is bounded by its 90 s core deadline plus
# tool and send time; docker-compose.yml stop_grace_period and the deploy
# script's stop timeout must exceed this value.
WORKER_JOB_COMPLETION_WAIT_SECONDS = 170


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
    install_sensitive_url_filter()

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

    # Bootstrap once under the owned lease, in both runtime modes. Repeated
    # starts with valid state are read-only and do not redownload the catalog.
    if ctx.get("redis") is not None and settings.zoho_inventory_org_id:
        startup_ctx = {**ctx, "stock_startup": True}
        if (
            settings.zoho_stock_incremental_enabled
            and settings.zoho_stock_coverage_evidence.strip()
        ):
            await refresh_zoho_stock_delta(startup_ctx)
        else:
            await refresh_zoho_stock_snapshot(startup_ctx)

    if settings.test_channel_restore_mode:
        logger.warning(
            "Test-channel restore mode active: embedding warmup disabled; approved stock cron jobs remain enabled"
        )
        return

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


def build_worker_functions() -> list[Any]:
    """Build the ARQ function allowlist for the selected runtime mode."""
    inbound = func(process_incoming_batch, max_tries=INBOUND_BATCH_MAX_TRIES)
    # Acts only on quotations a customer already requested in an accepted
    # inbound conversation, so it stays on in test-channel restore mode.
    quotation_retry = func(retry_pending_quotation, max_tries=1)
    # Enqueued by the inbound turn itself once a dialogue outgrows the history
    # window; without it long conversations silently lose their early context.
    # Keeps the shared Zoho stock snapshot fresh so customer turns only read
    # it; stock is customer-facing in every mode, so it runs in restore mode.
    stock_snapshot = func(refresh_zoho_stock_snapshot, max_tries=1)
    stock_delta = func(refresh_zoho_stock_delta, max_tries=1)
    # Keeps the admin /reset path reachable when an outside token holder moves
    # the webhook; restore mode depends on that path, so it runs there too.
    webhook_reconcile = func(reconcile_telegram_webhook, max_tries=1)
    if settings.test_channel_restore_mode:
        return [
            inbound,
            quotation_retry,
            func(refresh_conversation_summary),
            stock_snapshot,
            stock_delta,
            webhook_reconcile,
        ]
    return [
        stock_snapshot,
        stock_delta,
        webhook_reconcile,
        sync_products_from_treejar_catalog,
        sync_products_from_zoho,
        inbound,
        quotation_retry,
        refresh_conversation_summary,
        run_automatic_followups,
        run_proposal_followups,
        run_feedback_requests,
        calculate_and_store_metrics,
        evaluate_realtime_red_flags,
        evaluate_mature_conversations_quality,
        evaluate_recent_conversations_quality,
        evaluate_escalated_conversations,
        run_daily_summary,
        run_weekly_report,
        run_runtime_monitoring,
    ]


def build_worker_cron_jobs() -> list[Any]:
    """Build scheduled work; recovery mode keeps the stock and webhook checks."""
    eligible = bool(
        settings.zoho_stock_incremental_enabled
        and settings.zoho_stock_coverage_evidence.strip()
    )
    stock_snapshot = cron(
        refresh_zoho_stock_snapshot,
        hour={settings.zoho_stock_daily_hour_utc} if eligible else None,
        minute={settings.zoho_stock_daily_minute_utc}
        if eligible
        else set(range(1, 60, 5)),
        run_at_startup=False,
        unique=True,
    )
    stock_delta = cron(
        refresh_zoho_stock_delta,
        minute=set(range(1, 60, 10)),
        run_at_startup=False,
        unique=True,
    )
    stock_crons = [stock_snapshot, stock_delta] if eligible else [stock_snapshot]
    webhook_reconcile = cron(
        reconcile_telegram_webhook,
        run_at_startup=True,
        unique=True,
    )
    if settings.test_channel_restore_mode:
        return [*stock_crons, webhook_reconcile]
    return [
        *stock_crons,
        webhook_reconcile,
        cron(
            sync_products_from_treejar_catalog,
            hour={0, 6, 12, 18},
            minute={0},
            run_at_startup=False,
        ),
        cron(run_automatic_followups, minute={0}, run_at_startup=False),
        cron(run_proposal_followups, minute={15}, run_at_startup=False),
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
        cron(
            run_runtime_monitoring,
            minute={2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57},
            run_at_startup=False,
        ),
    ]


class WorkerSettings:
    functions: list[Any] = build_worker_functions()
    cron_jobs: list[Any] = build_worker_cron_jobs()
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    timezone = UTC
    job_timeout = 600  # 10 min — accommodate large catalogs (856+ SKU)
    job_completion_wait = WORKER_JOB_COMPLETION_WAIT_SECONDS
    max_jobs = 2
    keep_result = 3600  # keep results for 1 hour for debugging
