import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_endpoints(client: AsyncClient) -> None:
    # --- test_admin_prompts ---
    response1 = await client.get("/api/v1/admin/prompts/")
    assert response1.status_code == 200
    data = response1.json()
    assert isinstance(data, list)

    some_uuid = str(uuid.uuid4())
    response2 = await client.get(f"/api/v1/admin/prompts/{some_uuid}")
    assert response2.status_code == 404

    response3 = await client.put(
        f"/api/v1/admin/prompts/{some_uuid}",
        json={
            "content": "new system prompt content",
            "description": "updated prompt description",
        },
    )
    assert response3.status_code == 404

    # --- test_admin_metrics ---
    response_m = await client.get("/api/v1/admin/metrics/")
    assert response_m.status_code == 200
    data_m = response_m.json()
    assert "total_conversations" in data_m
    assert "messages_sent" in data_m
    assert "llm_cost_usd" in data_m
    assert "escalations" in data_m
    assert "deals_created" in data_m
    assert "quotes_generated" in data_m

    # --- test_admin_settings ---
    response_s1 = await client.get("/api/v1/admin/settings/")
    assert response_s1.status_code == 200
    data1 = response_s1.json()
    assert "bot_enabled" in data1
    assert "default_language" in data1

    response_s2 = await client.patch(
        "/api/v1/admin/settings/", json={"bot_enabled": False, "default_language": "ar"}
    )
    assert response_s2.status_code == 200
    data2 = response_s2.json()
    assert data2["bot_enabled"] is False
    assert data2["default_language"] == "ar"

    # --- test_admin_mount_redirects_to_login ---
    response_rm = await client.get("/admin/")
    assert response_rm.status_code in (302, 303)
    assert "/admin/login" in response_rm.headers["location"]
