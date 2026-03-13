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

    # Crons should include product sync
    assert settings.cron_jobs is not None
    assert len(settings.cron_jobs) > 0
    cron_names = [c.coroutine.__qualname__ for c in settings.cron_jobs]
    assert "sync_products_from_zoho" in cron_names


def test_worker_startup_shutdown_callable() -> None:
    """Verify startup and shutdown are async callables."""
    assert callable(WorkerSettings.on_startup)
    assert callable(WorkerSettings.on_shutdown)


@pytest.mark.asyncio
async def test_worker_startup_runs() -> None:
    """Verify startup doesn't crash and configures logging."""
    import logging

    ctx = {"redis": None}
    await WorkerSettings.on_startup(ctx)

    # Check that root logger has been configured
    root_logger = logging.getLogger()
    assert root_logger.level is not None


@pytest.mark.asyncio
async def test_worker_shutdown_runs() -> None:
    """Verify shutdown doesn't crash."""
    ctx = {"redis": None}
    await WorkerSettings.on_shutdown(ctx)
