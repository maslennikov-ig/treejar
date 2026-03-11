from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.product import Product
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products as rag_search_products
from src.schemas import (
    PaginatedResponse,
    ProductRead,
    ProductSearchQuery,
    ProductSearchResult,
    ProductSyncRequest,
    ProductSyncResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=PaginatedResponse[ProductRead])
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProductRead]:
    """List products with optional category filter."""
    stmt = select(Product).where(Product.is_active.is_(True))
    count_stmt = (
        select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    )

    if category:
        stmt = stmt.where(Product.category == category)
        count_stmt = count_stmt.where(Product.category == category)

    # Get total
    total = await db.scalar(count_stmt) or 0

    # Get paginated data
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    products = result.scalars().all()

    return PaginatedResponse(
        items=[ProductRead.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


def get_embedding_engine() -> EmbeddingEngine:
    return EmbeddingEngine()


@router.post("/search", response_model=ProductSearchResult)
async def search_products(
    body: ProductSearchQuery,
    db: AsyncSession = Depends(get_db),
    embedding_engine: EmbeddingEngine = Depends(get_embedding_engine),
) -> ProductSearchResult:
    """Semantic product search (for AI assistant)."""
    try:
        return await rag_search_products(db, body, embedding_engine)
    except Exception as e:
        logger.error(f"Error during product search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    body: ProductSyncRequest,
    request: Request,
) -> ProductSyncResponse:
    """Trigger product sync from external source."""
    if body.source != "zoho":
        raise HTTPException(
            status_code=400, detail="Only 'zoho' sync is currently supported."
        )

    try:
        pool = request.app.state.arq_pool
        await pool.enqueue_job("sync_products_from_zoho")

        # We return a 0-filled response to indicate queued
        # (Could also just return a generic queued status, but adhering to the schema)
        return ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail="Could not enqueue sync job") from e


@router.get("/{product_id}/similar")
async def get_similar(
    product_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Get similar products via pgvector cosine similarity."""
    from uuid import UUID

    from src.services.recommendations import get_similar_products

    try:
        pid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format") from None

    items = await get_similar_products(db, pid, limit=limit)
    return [item.model_dump() for item in items]


@router.get("/{product_id}/cross-sell")
async def get_cross_sell_products(
    product_id: str,
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Get cross-sell recommendations based on product's category."""
    from uuid import UUID

    from src.models.product import Product
    from src.services.recommendations import get_cross_sell

    try:
        pid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format") from None

    product = await db.get(Product, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    items = await get_cross_sell(db, product.category or "", limit=limit)
    return [item.model_dump() for item in items]
