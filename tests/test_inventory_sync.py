from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.inventory.sync import (
    _deactivate_stale_products,
    _upsert_items_batch,
    sync_products_from_zoho,
)
from src.schemas.product import ProductSyncResponse


@pytest.mark.asyncio
async def test_sync_products_from_zoho_success() -> None:
    ctx = {"redis": AsyncMock()}

    mock_client_instance = AsyncMock()
    mock_client_instance.get_items.side_effect = [
        {
            "items": [{"sku": "ITEM_1", "status": "active", "name": "Item 1"}],
            "page_context": {"has_more_page": True},
        },
        {
            "items": [{"sku": "ITEM_2", "status": "active", "name": "Item 2"}],
            "page_context": {"has_more_page": False},
        },
    ]

    with (
        patch(
            "src.integrations.inventory.sync._upsert_items_batch",
            new_callable=AsyncMock,
        ) as mock_upsert,
        patch("src.integrations.inventory.sync._zoho_client") as mock_cm,
    ):
        mock_cm.return_value.__aenter__.return_value = mock_client_instance

        result = await sync_products_from_zoho(ctx)

        # Upsert should be called twice (for 2 pages)
        assert mock_upsert.call_count == 2
        assert result["errors"] == 0
        # Synced objects are tracked strictly by the upsert logic modifying the stats reference,
        # but in this mock, the mock_upsert doesn't actually mutate stats.
        # It should just execute without crashing.


@pytest.mark.asyncio
async def test_sync_products_from_zoho_api_error() -> None:
    ctx = {"redis": AsyncMock()}

    mock_client_instance = AsyncMock()
    mock_client_instance.get_items.side_effect = Exception("API Down")

    with (
        patch(
            "src.integrations.inventory.sync._upsert_items_batch",
            new_callable=AsyncMock,
        ) as mock_upsert,
        patch("src.integrations.inventory.sync._zoho_client") as mock_cm,
    ):
        mock_cm.return_value.__aenter__.return_value = mock_client_instance

        result = await sync_products_from_zoho(ctx)

        assert mock_upsert.call_count == 0
        assert result["errors"] == 1


@pytest.mark.asyncio
@patch("src.integrations.inventory.sync.async_session_factory")
async def test_upsert_items_batch(mock_session_factory: AsyncMock) -> None:
    # 1 valid, 1 inactive (skipped), 1 missing sku (skipped)
    items = [
        {"sku": "SKU_1", "status": "active", "name": "Active Item"},
        {"sku": "SKU_2", "status": "inactive", "name": "Inactive Item"},
        {"status": "active", "name": "No SKU Item"},
    ]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)

    # Mock DB session execution and returning rows pattern
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    class MockResult:
        def all(self) -> list[tuple[str, int]]:
            return [("uuid-1", 0)]

    mock_session.execute.return_value = MockResult()

    await _upsert_items_batch(items, stats)

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()

    # Only 1 item should have been processed
    assert stats.created == 1
    assert stats.updated == 0
    assert stats.synced == 1
    assert stats.errors == 0


@pytest.mark.asyncio
async def test_upsert_items_batch_empty() -> None:
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
    # Should safely return without touching DB
    await _upsert_items_batch([], stats)

    assert stats.synced == 0
    assert stats.errors == 0


def test_sync_response_has_new_fields() -> None:
    resp = ProductSyncResponse(synced=0, created=0, updated=0, errors=0, deactivated=0, embeddings_generated=0)
    assert resp.deactivated == 0
    assert resp.embeddings_generated == 0


@pytest.mark.asyncio
@patch("src.integrations.inventory.sync.async_session_factory")
async def test_upsert_resets_embedding(mock_session_factory: AsyncMock) -> None:
    """Verify that the upsert sets embedding = NULL so changed products get re-embedded."""
    items = [{"sku": "SKU_1", "status": "active", "name": "Updated Item"}]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    class MockResult:
        def all(self) -> list[tuple[str, int]]:
            return [("uuid-1", 1)]  # xmax > 0 = UPDATE

    mock_session.execute.return_value = MockResult()

    await _upsert_items_batch(items, stats)

    # Inspect the statement that was executed
    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    # The ON CONFLICT SET clause must include embedding = None
    compiled = stmt.compile()
    set_clause_str = str(compiled)
    assert "embedding" in set_clause_str, "Upsert must reset embedding on conflict"


@pytest.mark.asyncio
@patch("src.integrations.inventory.sync.async_session_factory")
async def test_deactivate_stale_products(mock_session_factory: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    # Mock the execute result to return rowcount = 3
    mock_result = AsyncMock()
    mock_result.rowcount = 3
    mock_session.execute.return_value = mock_result

    from datetime import datetime, timezone
    sync_start = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
    
    count = await _deactivate_stale_products(sync_start)
    
    assert count == 3
    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_calls_deactivate_and_embed() -> None:
    ctx = {"redis": AsyncMock()}

    mock_client_instance = AsyncMock()
    mock_client_instance.get_items.return_value = {
        "items": [{"sku": "ITEM_1", "status": "active", "name": "Item 1"}],
        "page_context": {"has_more_page": False},
    }

    async def mock_upsert_impl(items, stats):
        stats.synced += len(items)

    with (
        patch("src.integrations.inventory.sync._upsert_items_batch", new_callable=AsyncMock, side_effect=mock_upsert_impl) as mock_upsert,
        patch("src.integrations.inventory.sync._zoho_client") as mock_cm,
        patch("src.integrations.inventory.sync._deactivate_stale_products", new_callable=AsyncMock, return_value=2) as mock_deactivate,
        patch("src.integrations.inventory.sync._generate_missing_embeddings", new_callable=AsyncMock, return_value=5) as mock_embed,
    ):
        mock_cm.return_value.__aenter__.return_value = mock_client_instance

        result = await sync_products_from_zoho(ctx)

        mock_deactivate.assert_awaited_once()
        mock_embed.assert_awaited_once()
        assert result["deactivated"] == 2
        assert result["embeddings_generated"] == 5
