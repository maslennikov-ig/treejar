from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.schemas import (
    PaginatedResponse,
    ProductRead,
    ProductSearchQuery,
    ProductSearchResult,
    ProductSyncRequest,
    ProductSyncResponse,
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ProductRead])
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
) -> PaginatedResponse[ProductRead]:
    """List products with optional category filter."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/search", response_model=ProductSearchResult)
async def search_products(
    body: ProductSearchQuery,
) -> ProductSearchResult:
    """Semantic product search (for AI assistant)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    body: ProductSyncRequest,
) -> ProductSyncResponse:
    """Trigger product sync from external source."""
    raise HTTPException(status_code=501, detail="Not implemented")
