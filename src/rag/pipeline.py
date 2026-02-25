from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_upsert
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.vector.base import VectorStore
from src.models.knowledge_base import KnowledgeBase
from src.models.product import Product
from src.rag.embeddings import EmbeddingEngine
from src.schemas.product import ProductRead, ProductSearchQuery, ProductSearchResult

logger = logging.getLogger(__name__)


class PgVectorStore(VectorStore):
    """VectorStore implementation using PostgreSQL with pgvector."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search products based on vector similarity and SQL filters.

        This implements the protocol but is tailored for products specifically.
        For general generic usage, it would need a table param. We use specific
        functions for products and knowledge base below instead of relying heavily
        on this generic interface for complex queries.
        """
        stmt = select(Product)

        # Apply filters
        if filters:
            if filters.get("category"):
                stmt = stmt.where(Product.category == filters["category"])
            if filters.get("min_price") is not None:
                stmt = stmt.where(Product.price >= filters["min_price"])
            if filters.get("max_price") is not None:
                stmt = stmt.where(Product.price <= filters["max_price"])
            if filters.get("in_stock_only"):
                stmt = stmt.where(Product.stock > 0)
            if filters.get("is_active") is not None:
                stmt = stmt.where(Product.is_active == filters["is_active"])

        # Order by cosine distance (nearest neighbor)
        # Using pgvector <=> operator mapped by SQLAlchemy
        stmt = stmt.order_by(Product.embedding.cosine_distance(query_embedding))

        # Limit results
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        products = result.scalars().all()

        # Convert to expected dictionaries
        return [
            {
                "id": str(p.id),
                "sku": p.sku,
                "name": p.name_en,
                "category": p.category,
                "price": float(p.price),
                "stock": p.stock,
            }
            for p in products
        ]

    async def upsert(
        self,
        id: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """Upsert a vector for the knowledge base."""
        # This generic upsert is usually better served by the specialized
        # scripts in indexer.py, but we provide a basic KnowledgeBase upsert.
        stmt = pg_upsert(KnowledgeBase).values(
            id=id,
            embedding=embedding,
            title=metadata.get("title", ""),
            source=metadata.get("source", "generic"),
            content=metadata.get("content", ""),
            category=metadata.get("category"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "embedding": stmt.excluded.embedding,
                "content": stmt.excluded.content,
                "title": stmt.excluded.title,
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()


async def search_products(
    db: AsyncSession,
    query: ProductSearchQuery,
    embedding_engine: EmbeddingEngine,
) -> ProductSearchResult:
    """Perform hybrid search (vector + SQL filters) for products."""

    # 1. Generate text embedding for the search query
    query_vector = await embedding_engine.embed_async(query.query)

    # 2. Start building SQLAlchemy select (filter out products without embeddings)
    stmt = select(Product).where(
        Product.is_active.is_(True),
        Product.embedding.is_not(None),
    )

    # 3. Apply exact match filters
    if query.category:
        stmt = stmt.where(Product.category == query.category)
    if query.min_price is not None:
        stmt = stmt.where(Product.price >= query.min_price)
    if query.max_price is not None:
        stmt = stmt.where(Product.price <= query.max_price)
    if query.in_stock_only:
        stmt = stmt.where(Product.stock > 0)

    # We could filter by colors if they are stored in Product.attributes
    # but the schema says attributes is JSON. We skip it for now unless needed.

    # 4. Apply vector similarity ordering pgvector <=>
    stmt = stmt.order_by(Product.embedding.cosine_distance(query_vector))
    stmt = stmt.limit(query.limit)

    # 5. Execute query
    result = await db.execute(stmt)
    products = result.scalars().all()

    # 6. Map to ProductRead schema models
    product_responses = [
        ProductRead.model_validate(p)
        for p in products
    ]

    # We can interpret the query somehow if we wanted,
    # but for now we just return the raw text
    return ProductSearchResult(
        products=product_responses,
        query_interpreted=query.query,
        total_found=len(product_responses)
    )


async def search_knowledge(
    db: AsyncSession,
    query: str,
    embedding_engine: EmbeddingEngine,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Search knowledge base for relevant chunks."""

    # 1. Embed user question/query
    query_vector = await embedding_engine.embed_async(query)

    # 2. Build select (filter out records without embeddings)
    stmt = select(KnowledgeBase).where(KnowledgeBase.embedding.is_not(None))

    # 3. Order by cosine distance
    stmt = stmt.order_by(KnowledgeBase.embedding.cosine_distance(query_vector))
    stmt = stmt.limit(limit)

    # 4. Execute
    result = await db.execute(stmt)
    records = result.scalars().all()

    # 5. Build response dict
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "category": r.category,
            "title": r.title,
            "content": r.content,
        }
        for r in records
    ]
