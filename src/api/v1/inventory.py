from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_redis
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.schemas import (
    StockLevel,
)

router = APIRouter()


async def get_inventory_client(
    redis: aioredis.Redis = Depends(get_redis),
) -> AsyncGenerator[ZohoInventoryClient, None]:
    """Dependency to get an authenticated Zoho Inventory client."""
    async with ZohoInventoryClient(redis) as client:
        yield client


@router.get("/stock/{sku}", response_model=StockLevel)
async def get_stock_level(
    sku: str,
    inventory: ZohoInventoryClient = Depends(get_inventory_client),
) -> StockLevel:
    """Get stock level for a specific SKU."""
    item = await inventory.get_stock(sku)
    if not item:
        raise HTTPException(status_code=404, detail="SKU not found in inventory")

    return StockLevel(
        sku=item.get("sku", sku),
        name=item.get("name", "Unknown Item"),
        stock=int(item.get("available_stock", 0)),
        price=float(item.get("rate", 0.0) or 0.0),
        currency="AED",
    )


@router.get("/stock/", response_model=list[StockLevel])
async def get_stock_levels(
    skus: list[str] = Query(...),
    inventory: ZohoInventoryClient = Depends(get_inventory_client),
) -> list[StockLevel]:
    """Get stock levels for multiple SKUs."""
    items = await inventory.get_stock_bulk(skus)

    return [
        StockLevel(
            sku=item.get("sku", "Unknown"),
            name=item.get("name", "Unknown Item"),
            stock=int(item.get("available_stock", 0)),
            price=float(item.get("rate", 0.0) or 0.0),
            currency="AED",
        )
        for item in items
    ]
