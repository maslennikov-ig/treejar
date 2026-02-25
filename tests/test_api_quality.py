import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_list_reviews() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/quality/reviews/")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_create_review() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/quality/reviews/", json={"conversation_id": "test", "score": 5})
    assert response.status_code == 422 or response.status_code == 501  # 422 if validation fails first


@pytest.mark.asyncio
async def test_generate_report() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/quality/reports/", json={"start_date": "2024-01-01"})
    assert response.status_code == 422 or response.status_code == 501
