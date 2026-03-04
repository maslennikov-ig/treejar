from __future__ import annotations

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_landing_page_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
