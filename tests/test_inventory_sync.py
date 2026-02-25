from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.inventory.sync import _upsert_items_batch, sync_products_from_zoho
from src.schemas.product import ProductSyncResponse


@pytest.mark.asyncio
async def test_sync_products_from_zoho_success() -> None:
    ctx = {"redis": AsyncMock()}
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get_items.side_effect = [
        {
            "items": [{"sku": "ITEM_1", "status": "active", "name": "Item 1"}],
            "page_context": {"has_more_page": True}
        },
        {
            "items": [{"sku": "ITEM_2", "status": "active", "name": "Item 2"}],
            "page_context": {"has_more_page": False}
        }
    ]

    with patch("src.integrations.inventory.sync._upsert_items_batch", new_callable=AsyncMock) as mock_upsert:
        # Mock the context manager behavior of _zoho_client
        with patch("src.integrations.inventory.sync._zoho_client") as mock_cm:
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

    with patch("src.integrations.inventory.sync._upsert_items_batch", new_callable=AsyncMock) as mock_upsert:
        with patch("src.integrations.inventory.sync._zoho_client") as mock_cm:
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
