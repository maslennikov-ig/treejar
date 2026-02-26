import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock
from collections.abc import Generator

from src.main import app
from src.api.v1.inventory import get_inventory_client

@pytest.fixture
def mock_inventory() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def override_get_inventory_client(mock_inventory: AsyncMock) -> Generator[None, None, None]:
    async def _override() -> AsyncMock:
        return mock_inventory

    app.dependency_overrides[get_inventory_client] = _override
    yield
    app.dependency_overrides.pop(get_inventory_client, None)


@pytest.mark.asyncio
async def test_get_stock_level_found(override_get_inventory_client: None, mock_inventory: AsyncMock) -> None:
    mock_inventory.get_stock.return_value = {
        "sku": "CHAIR-01",
        "name": "Office Chair",
        "available_stock": 15,
        "rate": 150.0,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/inventory/stock/CHAIR-01")

    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "CHAIR-01"
    assert data["name"] == "Office Chair"
    assert data["stock"] == 15
    assert data["price"] == 150.0
    mock_inventory.get_stock.assert_awaited_once_with("CHAIR-01")


@pytest.mark.asyncio
async def test_get_stock_level_not_found(override_get_inventory_client: None, mock_inventory: AsyncMock) -> None:
    mock_inventory.get_stock.return_value = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/inventory/stock/UNKNOWN")

    assert response.status_code == 404
    assert response.json()["detail"] == "SKU not found in inventory"

@pytest.mark.asyncio
async def test_get_stock_levels_not_implemented(override_get_inventory_client: None, mock_inventory: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/inventory/stock/?skus=A&skus=B")
    assert response.status_code == 501

@pytest.mark.asyncio
async def test_create_sale_order_not_implemented() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/inventory/sale-orders/", json={"contact_name": "x", "items": []})
    assert response.status_code == 501

@pytest.mark.asyncio
async def test_get_sale_order_not_implemented() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/inventory/sale-orders/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 501
