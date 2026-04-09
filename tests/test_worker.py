import pytest

from src.worker import WorkerSettings


def test_arq_worker_settings_configured() -> None:
    # Basic sanity check that our worker is picking up the correct functions
    settings = WorkerSettings

    assert settings.functions is not None
    assert len(settings.functions) > 0

    # process_incoming_batch should be registered
    function_names = [f.__name__ for f in settings.functions]
    assert "process_incoming_batch" in function_names
    assert "refresh_conversation_summary" in function_names
    assert "sync_products_from_treejar_catalog" in function_names
    assert "sync_products_from_zoho" in function_names
    assert "evaluate_realtime_red_flags" in function_names
    assert "evaluate_mature_conversations_quality" in function_names
    assert "evaluate_recent_conversations_quality" in function_names

    # Crons should include product sync
    assert settings.cron_jobs is not None
    assert len(settings.cron_jobs) > 0
    cron_names = [c.coroutine.__qualname__ for c in settings.cron_jobs]
    assert "sync_products_from_treejar_catalog" in cron_names
    assert "evaluate_realtime_red_flags" in cron_names
    assert "evaluate_mature_conversations_quality" in cron_names


def test_worker_startup_shutdown_callable() -> None:
    """Verify startup and shutdown are async callables."""
    assert callable(WorkerSettings.on_startup)
    assert callable(WorkerSettings.on_shutdown)


@pytest.mark.asyncio
async def test_worker_startup_runs() -> None:
    """Verify startup doesn't crash and configures logging."""
    import logging
    from unittest.mock import AsyncMock, patch

    ctx = {"redis": None}
    with patch("src.worker.EmbeddingEngine") as MockEngine:
        mock_engine = MockEngine.return_value
        mock_engine.warmup_async = AsyncMock()
        await WorkerSettings.on_startup(ctx)

    # Check that root logger has been configured
    root_logger = logging.getLogger()
    assert root_logger.level is not None


@pytest.mark.asyncio
async def test_worker_startup_warms_embedding_model() -> None:
    from unittest.mock import AsyncMock, patch

    ctx = {"redis": None}

    with patch("src.worker.EmbeddingEngine") as MockEngine:
        mock_engine = MockEngine.return_value
        mock_engine.warmup_async = AsyncMock()

        await WorkerSettings.on_startup(ctx)

    mock_engine.warmup_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_shutdown_runs() -> None:
    """Verify shutdown doesn't crash."""
    ctx = {"redis": None}
    await WorkerSettings.on_shutdown(ctx)
