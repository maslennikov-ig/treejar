"""Product recommendations service.

Provides two types of recommendations:
1. Similar products via pgvector cosine similarity on embeddings
2. Cross-sell rules loaded from SystemConfig
"""
from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


class RecommendationItem(BaseModel):
    """A recommended product."""

    id: UUID
    name: str
    price: float
    stock: int
    similarity_score: float | None = None
    recommendation_type: str = "similar"  # similar | cross_sell


async def get_similar_products(
    db: AsyncSession,
    product_id: UUID,
    limit: int = 5,
) -> list[RecommendationItem]:
    """Find similar products using pgvector cosine similarity.

    Args:
        db: Database session.
        product_id: Source product ID to find similar items for.
        limit: Maximum number of results.

    Returns:
        List of similar products ordered by similarity.
    """
    # Get the source product's embedding
    source = await db.get(Product, product_id)
    if not source or source.embedding is None:
        return []

    # Use pgvector cosine distance operator (<=>)
    sql = text("""
        SELECT id, name_en, price, stock,
               1 - (embedding <=> :embedding) as similarity
        FROM products
        WHERE id != :product_id
          AND is_active = true
          AND embedding IS NOT NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "embedding": "[" + ",".join(str(x) for x in source.embedding) + "]",
            "product_id": str(product_id),
            "limit": limit,
        },
    )

    return [
        RecommendationItem(
            id=row[0],
            name=row[1],
            price=float(row[2]),
            stock=row[3],
            similarity_score=round(float(row[4]), 4) if row[4] else None,
            recommendation_type="similar",
        )
        for row in result.all()
    ]


async def get_cross_sell(
    db: AsyncSession,
    category: str,
    limit: int = 3,
) -> list[RecommendationItem]:
    """Get cross-sell recommendations based on category rules.

    Rules are stored in SystemConfig with key 'cross_sell_rules'.
    Format: {"desk": ["chair", "shelf"], "chair": ["cushion", "armrest"]}

    Args:
        db: Database session.
        category: Source product category.
        limit: Maximum number of results.

    Returns:
        List of cross-sell products.
    """
    # Load rules from SystemConfig
    rules_stmt = select(SystemConfig).where(
        SystemConfig.key == "cross_sell_rules"
    )
    result = await db.execute(rules_stmt)
    config = result.scalar_one_or_none()

    if not config or not isinstance(config.value, dict):
        return []

    rules: dict[str, list[str]] = config.value
    target_categories = rules.get(category.lower(), [])

    if not target_categories:
        return []

    # Find products in target categories
    prod_stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.category.in_(target_categories),
        )
        .order_by(Product.stock.desc())
        .limit(limit)
    )
    prod_result = await db.execute(prod_stmt)
    products = prod_result.scalars().all()

    return [
        RecommendationItem(
            id=p.id,
            name=p.name_en,
            price=float(p.price),
            stock=p.stock,
            recommendation_type="cross_sell",
        )
        for p in products
    ]
