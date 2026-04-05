from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import settings
from src.main import app
from src.services.public_media import (
    build_signed_product_image_url,
    sign_product_image_token,
    verify_signed_product_image_token,
)


@pytest.fixture
def restore_public_media_settings() -> Generator[None, None, None]:
    original_domain = settings.domain
    original_secret = settings.app_secret_key
    yield
    settings.domain = original_domain
    settings.app_secret_key = original_secret


@pytest.fixture
async def public_media_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


def test_build_signed_product_image_url_uses_canonical_fallback(
    restore_public_media_settings: None,
) -> None:
    settings.domain = ""
    settings.app_secret_key = "test-secret"

    url = build_signed_product_image_url("ITEM-1")
    assert url.startswith(
        "https://noor.starec.ai/api/v1/public-media/products/ITEM-1?token="
    )


def test_verify_signed_product_image_token_rejects_expired(
    restore_public_media_settings: None,
) -> None:
    settings.app_secret_key = "test-secret"
    token = sign_product_image_token("ITEM-1")

    assert verify_signed_product_image_token(token, "ITEM-1", ttl_seconds=60) is True
    assert verify_signed_product_image_token(token, "ITEM-1", ttl_seconds=-1) is False


@pytest.mark.asyncio
async def test_public_media_route_returns_image_for_valid_token(
    public_media_client: AsyncClient,
    restore_public_media_settings: None,
) -> None:
    from src.api.v1.public_media import get_inventory_client

    settings.app_secret_key = "test-secret"
    token = sign_product_image_token("ZOHO-1")
    inventory = SimpleNamespace(
        get_item_image=AsyncMock(return_value=(b"img-bytes", "image/jpeg"))
    )

    async def _override_inventory_client() -> AsyncGenerator[object, None]:
        yield inventory

    app.dependency_overrides[get_inventory_client] = _override_inventory_client
    try:
        response = await public_media_client.get(
            f"/api/v1/public-media/products/ZOHO-1?token={token}"
        )
    finally:
        app.dependency_overrides.pop(get_inventory_client, None)

    assert response.status_code == 200
    assert response.content == b"img-bytes"
    assert response.headers["content-type"].startswith("image/jpeg")


@pytest.mark.asyncio
async def test_public_media_route_rejects_invalid_token(
    public_media_client: AsyncClient,
    restore_public_media_settings: None,
) -> None:
    from src.api.v1.public_media import get_inventory_client

    settings.app_secret_key = "test-secret"
    inventory = SimpleNamespace(get_item_image=AsyncMock(return_value=None))

    async def _override_inventory_client() -> AsyncGenerator[object, None]:
        yield inventory

    app.dependency_overrides[get_inventory_client] = _override_inventory_client
    try:
        response = await public_media_client.get(
            "/api/v1/public-media/products/ZOHO-1?token=bad-token"
        )
    finally:
        app.dependency_overrides.pop(get_inventory_client, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_public_media_route_rejects_missing_image(
    public_media_client: AsyncClient,
    restore_public_media_settings: None,
) -> None:
    from src.api.v1.public_media import get_inventory_client

    settings.app_secret_key = "test-secret"
    token = sign_product_image_token("ZOHO-1")
    inventory = SimpleNamespace(get_item_image=AsyncMock(return_value=None))

    async def _override_inventory_client() -> AsyncGenerator[object, None]:
        yield inventory

    app.dependency_overrides[get_inventory_client] = _override_inventory_client
    try:
        response = await public_media_client.get(
            f"/api/v1/public-media/products/ZOHO-1?token={token}"
        )
    finally:
        app.dependency_overrides.pop(get_inventory_client, None)

    assert response.status_code == 404
