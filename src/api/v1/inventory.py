from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from src.schemas import (
    SaleOrderCreate,
    SaleOrderRead,
    StockLevel,
)

router = APIRouter()


@router.get("/stock/{sku}", response_model=StockLevel)
async def get_stock_level(
    sku: str,
) -> StockLevel:
    """Get stock level for a specific SKU."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/stock/", response_model=list[StockLevel])
async def get_stock_levels(
    skus: list[str] = Query(...),
) -> list[StockLevel]:
    """Get stock levels for multiple SKUs."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/sale-orders/", response_model=SaleOrderRead)
async def create_sale_order(
    body: SaleOrderCreate,
) -> SaleOrderRead:
    """Create a sale order in Zoho Inventory."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/sale-orders/{order_id}", response_model=SaleOrderRead)
async def get_sale_order(
    order_id: uuid.UUID,
) -> SaleOrderRead:
    """Get sale order details."""
    raise HTTPException(status_code=501, detail="Not implemented")
