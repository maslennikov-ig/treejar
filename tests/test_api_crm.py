import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_crm_contacts() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response1 = await ac.get("/api/v1/crm/contacts/123456789")
        assert response1.status_code == 501
        
        response2 = await ac.post("/api/v1/crm/contacts/", json={
            "phone": "string",
            "name": "string",
            "language": "string"
        })
        assert response2.status_code == 422 or response2.status_code == 501


@pytest.mark.asyncio
async def test_crm_deals() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response1 = await ac.post("/api/v1/crm/deals/", json={
            "contact_id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "title": "string",
            "amount": 0,
            "currency": "string",
            "stage": "string"
        })
        assert response1.status_code == 422 or response1.status_code == 501
        
        some_uuid = str(uuid.uuid4())
        response2 = await ac.patch(f"/api/v1/crm/deals/{some_uuid}", json={
            "stage": "string",
            "amount": 0
        })
        assert response2.status_code == 422 or response2.status_code == 501
