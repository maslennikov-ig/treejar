import json
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_admin_prompts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response1 = await ac.get("/api/v1/admin/prompts/")
        assert response1.status_code == 501
        
        some_uuid = str(uuid.uuid4())
        response2 = await ac.get(f"/api/v1/admin/prompts/{some_uuid}")
        assert response2.status_code == 501
        
        response3 = await ac.put(f"/api/v1/admin/prompts/{some_uuid}", json={
            "name": "string",
            "content": "string",
            "language": "string",
            "is_active": True
        })
        assert response3.status_code == 422 or response3.status_code == 501


@pytest.mark.asyncio
async def test_admin_metrics() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/admin/metrics/")
        assert response.status_code == 501


@pytest.mark.asyncio
async def test_admin_settings() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response1 = await ac.get("/api/v1/admin/settings/")
        assert response1.status_code == 501
        
        response2 = await ac.patch("/api/v1/admin/settings/", json={
            "operating_mode": "string",
            "auto_reply_enabled": True
        })
        assert response2.status_code == 422 or response2.status_code == 501
