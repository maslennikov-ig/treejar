"""Product recommendations service.

Provides two types of recommendations:
1. Similar products via pgvector cosine similarity on embeddings
2. Cross-sell rules loaded from SystemConfig
"""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

_CROSS_SELL_CATEGORY_FAMILIES: dict[str, tuple[str, ...]] = {
    "chair": ("chairs",),
    "monitor_arm": ("accessories",),
    "cable_management": ("accessories",),
    "cushion": ("accessories",),
    "footrest": ("accessories",),
    "armrest": ("accessories",),
    "shelf": ("storage",),
    "filing_cabinet": ("storage",),
    "organizer": ("accessories", "storage"),
    "coffee_table": ("desks & tables",),
    "side_table": ("desks & tables",),
    "lighting": ("accessories",),
    "acoustic_panel": ("accessories",),
    "planter": ("accessories",),
}


class RecommendationItem(BaseModel):
    """A recommended product."""

    id: UUID
    name: str
    sku: str | None = None
    price: float
    currency: str = "AED"
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
    rules_stmt = select(SystemConfig).where(SystemConfig.key == "cross_sell_rules")
    result = await db.execute(rules_stmt)
    config = result.scalar_one_or_none()

    if not config or not isinstance(config.value, dict):
        return []

    rules: dict[str, list[str]] = config.value
    target_categories = rules.get(category.casefold(), [])

    if not target_categories:
        return []

    catalog_categories: list[str] = []
    for target in target_categories:
        normalized_target = str(target).strip().casefold()
        aliases = _CROSS_SELL_CATEGORY_FAMILIES.get(
            normalized_target,
            (normalized_target.replace("_", " "),),
        )
        for alias in aliases:
            if alias and alias not in catalog_categories:
                catalog_categories.append(alias)

    products: list[Product] = []
    seen_ids: set[UUID] = set()
    for catalog_category in catalog_categories:
        if len(products) >= limit:
            break
        prod_stmt = (
            select(Product)
            .where(
                Product.is_active.is_(True),
                func.lower(Product.category) == catalog_category,
                Product.stock > 0,
                Product.price > 0,
            )
            .order_by(Product.stock.desc(), Product.price.asc())
            .limit(1)
        )
        prod_result = await db.execute(prod_stmt)
        for product in prod_result.scalars().all():
            if product.id in seen_ids:
                continue
            seen_ids.add(product.id)
            products.append(product)
            break

    return [
        RecommendationItem(
            id=p.id,
            name=p.name_en,
            sku=p.sku,
            price=float(p.price),
            currency=p.currency,
            stock=p.stock,
            recommendation_type="cross_sell",
        )
        for p in products
    ]
