from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.v1.crm import get_crm_client
from src.main import app


@pytest.fixture
def mock_crm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def override_get_crm_client(mock_crm: AsyncMock) -> Generator[None, None, None]:
    async def _override() -> AsyncMock:
        return mock_crm

    app.dependency_overrides[get_crm_client] = _override
    yield
    app.dependency_overrides.pop(get_crm_client, None)


@pytest.mark.asyncio
async def test_get_contact_found(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.find_contact_by_phone.return_value = {
        "id": "123",
        "Phone": "123456789",
        "First_Name": "Jane",
        "Last_Name": "Doe",
        "Email": "jane@example.com",
        "Created_Time": "2026-02-26T12:00:00+00:00",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/crm/contacts/123456789")

    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "123456789"
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert data["zoho_contact_id"] == "123"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_contact_not_found(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.find_contact_by_phone.return_value = None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/crm/contacts/123456789")

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


@pytest.mark.asyncio
async def test_create_contact_success(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.create_contact.return_value = {"code": "SUCCESS", "details": {"id": "456"}}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/crm/contacts/", json={
            "phone": "987654321",
            "name": "John Smith",
            "email": "john@example.com",
            "company": "Test Co",
            "position": "CEO",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["zoho_contact_id"] == "456"
    assert data["name"] == "John Smith"
    mock_crm.create_contact.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_contact_failure(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.create_contact.return_value = {"code": "ERROR"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/crm/contacts/", json={"phone": "987654321"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_deal_success(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.create_deal.return_value = {"code": "SUCCESS", "details": {"id": "789"}}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/crm/deals/", json={
            "contact_id": "456",
            "title": "New Deal",
            "amount": 1000.50,
            "currency": "AED",
            "stage": "New Lead",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["zoho_deal_id"] == "789"
    assert data["amount"] == 1000.5
    assert data["stage"] == "New Lead"
    mock_crm.create_deal.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_deal_success(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    mock_crm.update_deal.return_value = {"code": "SUCCESS"}
    deal_id = "789"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(f"/api/v1/crm/deals/{deal_id}", json={
            "stage": "Negotiations",
            "amount": 2000.0,
            "notes": "Testing notes",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "Negotiations"
    assert data["amount"] == 2000.0
    mock_crm.update_deal.assert_awaited_once_with("789", {
        "Stage": "Negotiations",
        "Amount": 2000.0,
        "Description": "Testing notes",
    })

@pytest.mark.asyncio
async def test_update_deal_no_fields(override_get_crm_client: None, mock_crm: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch("/api/v1/crm/deals/789", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "No fields to update"
