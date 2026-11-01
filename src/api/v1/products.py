from __future__ import annotations

import logging
import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.admin import (
    record_best_effort_admin_audit,
    record_catalog_sync_status,
    require_admin_session,
)
from src.core.config import settings
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
)
from src.schemas.admin import AdminProductSyncResponse as ProductSyncResponse

router = APIRouter()
logger = logging.getLogger(__name__)
SYNC_JOB_BY_SOURCE = {
    "treejar": "sync_products_from_treejar_catalog",
    "catalog": "sync_products_from_treejar_catalog",
    "treejar_catalog": "sync_products_from_treejar_catalog",
    "zoho": "sync_products_from_zoho",
}


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
        logger.error("Error during product search: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


async def enqueue_product_sync(
    body: ProductSyncRequest,
    request: Request,
) -> tuple[ProductSyncResponse, str, str]:
    """Validate sync source and enqueue the ARQ catalog sync job."""
    source = body.source.strip().lower()
    job_name = SYNC_JOB_BY_SOURCE.get(source)
    if job_name is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported sync source. Use 'treejar' for the canonical catalog "
                "sync or 'zoho' for the legacy operational path. "
                f"Catalog source of truth is '{settings.catalog_api_url}'."
            ),
        )

    try:
        pool = request.app.state.arq_pool
        await pool.enqueue_job(job_name)
    except Exception as e:
        logger.error("Error triggering sync: %s", e)
        raise HTTPException(status_code=500, detail="Could not enqueue sync job") from e

    source_key = "zoho" if source == "zoho" else "treejar"
    response = ProductSyncResponse(
        synced=0,
        created=0,
        updated=0,
        errors=0,
        status="queued",
    )
    return response, source_key, job_name


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    body: ProductSyncRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_session),
) -> ProductSyncResponse:
    """Queue product sync, defaulting to the canonical Treejar catalog path."""
    response, source_key, job_name = await enqueue_product_sync(body, request)
    await record_catalog_sync_status(
        source_key=source_key,
        last_status="queued",
        job_name=job_name,
        detail=f"Queued {source_key} sync job",
    )
    await record_best_effort_admin_audit(
        db,
        action="catalog.sync",
        entity_type="product_sync",
        entity_id=source_key,
        after={"source": source_key, "job_name": job_name, "status": "queued"},
        request=request,
    )
    return response


@router.get("/{product_id}/similar")
async def get_similar(
    product_id: UUID,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Get similar products via pgvector cosine similarity."""
    from src.services.recommendations import get_similar_products

    items = await get_similar_products(db, product_id, limit=limit)
    return [item.model_dump() for item in items]


@router.get("/{product_id}/cross-sell")
async def get_cross_sell_products(
    product_id: UUID,
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Get cross-sell recommendations based on product's category."""
    from src.models.product import Product
    from src.services.recommendations import get_cross_sell

    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    items = await get_cross_sell(db, product.category or "", limit=limit)
    return [item.model_dump() for item in items]
