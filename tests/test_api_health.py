from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_redis
from src.main import app


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: redis
    yield redis
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_check_ok(mock_redis: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dependencies"]["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_degraded(mock_redis: AsyncMock) -> None:
    mock_redis.ping.side_effect = Exception("Redis connection refused")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["redis"]["status"] == "error"
    assert "refused" in data["dependencies"]["redis"]["message"]
