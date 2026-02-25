import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.database import get_db
from src.main import app
from src.models.product import Product
from src.api.v1.products import get_embedding_engine


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture
def mock_embedding() -> AsyncMock:
    engine = AsyncMock()
    app.dependency_overrides[get_embedding_engine] = lambda: engine
    yield engine
    app.dependency_overrides.pop(get_embedding_engine, None)


@pytest.mark.asyncio
async def test_list_products(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock
    
    mock_result = MagicMock()
    mock_db.scalar.return_value = 1
    
    prod = Product(
        id=uuid.uuid4(),
        sku="TEST-SKU",
        name_en="Test Product",
        price=10.0,
        currency="USD",
        stock=5,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    mock_result.scalars.return_value.all.return_value = [prod]
    mock_db.execute.return_value = mock_result

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/products/?category=Test")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "TEST-SKU"


@pytest.mark.asyncio
async def test_search_products(mock_db: AsyncMock, mock_embedding: AsyncMock) -> None:
    from unittest.mock import patch
    from src.schemas import ProductSearchResult
    
    mock_search_result = ProductSearchResult(
        products=[],
        total_found=0
    )
    
    with patch("src.api.v1.products.rag_search_products", new_callable=AsyncMock) as mock_rag:
        mock_rag.return_value = mock_search_result
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/v1/products/search", json={"query": "test query"})
            
        assert response.status_code == 200
        data = response.json()
        assert data["total_found"] == 0
        mock_rag.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_products_error(mock_db: AsyncMock, mock_embedding: AsyncMock) -> None:
    from unittest.mock import patch
    
    with patch("src.api.v1.products.rag_search_products", new_callable=AsyncMock) as mock_rag:
        mock_rag.side_effect = ValueError("Some internal error")
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/v1/products/search", json={"query": "test query"})
            
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_sync_products_zoho(mock_db: AsyncMock) -> None:
    # We need to mock the ARQ pool on the app state
    mock_pool = AsyncMock()
    app.state.arq_pool = mock_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/products/sync", json={"source": "zoho"})
        
    assert response.status_code == 200
    assert response.json()["synced"] == 0
    mock_pool.enqueue_job.assert_awaited_with("sync_products_from_zoho")
    
    # Clean up state to not affect other tests
    del app.state.arq_pool


@pytest.mark.asyncio
async def test_sync_products_unsupported(mock_db: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/products/sync", json={"source": "unknown"})
        
    assert response.status_code == 400
    assert "zoho" in response.json()["detail"]
