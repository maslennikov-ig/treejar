from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.api.deps import get_redis
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.services.public_media import verify_signed_product_image_token

router = APIRouter()
PRODUCT_MEDIA_TOKEN_TTL_SECONDS = 300


async def get_inventory_client(
    redis: aioredis.Redis = Depends(get_redis),
) -> AsyncGenerator[ZohoInventoryClient, None]:
    async with ZohoInventoryClient(redis) as client:
        yield client


@router.get("/products/{zoho_item_id}")
async def get_product_image(
    zoho_item_id: str,
    token: str = Query(..., min_length=1),
    inventory: ZohoInventoryClient = Depends(get_inventory_client),
) -> Response:
    if not verify_signed_product_image_token(
        token=token,
        zoho_item_id=zoho_item_id,
        ttl_seconds=PRODUCT_MEDIA_TOKEN_TTL_SECONDS,
    ):
        raise HTTPException(status_code=403, detail="Invalid or expired media token")

    image_result = await inventory.get_item_image(zoho_item_id)
    if image_result is None:
        raise HTTPException(status_code=404, detail="Media not found")

    content, content_type = image_result
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
