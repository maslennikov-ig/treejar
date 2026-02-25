from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_upsert
from sqlalchemy.sql import func

from src.core.database import async_session_factory
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.models.product import Product
from src.schemas.product import ProductSyncResponse

logger = logging.getLogger(__name__)


async def sync_products_from_zoho(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ background job to synchronize products from Zoho Inventory to the database.

    Args:
        ctx: The ARQ context dictionary containing the Redis pool.

    Returns:
        A dictionary with the sync stats matching ProductSyncResponse schema.
    """
    logger.info("Starting Zoho Inventory product sync...")

    redis = ctx["redis"]
    client = ZohoInventoryClient(redis_client=redis)

    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)

    try:
        page = 1
        has_more = True

        while has_more:
            logger.info(f"Fetching Zoho products page {page}...")

            try:
                response_data = await client.get_items(page=page, per_page=200)
            except Exception as e:
                logger.error(f"Error fetching page {page} from Zoho: {e}")
                stats.errors += 1
                break

            items = response_data.get("items", [])
            page_context = response_data.get("page_context", {})
            has_more = page_context.get("has_more_page", False)

            if not items:
                break

            # Upsert items into the database
            await _upsert_items_batch(items, stats)

            page += 1

    finally:
        await client.close()
        logger.info(
            f"Zoho sync completed. "
            f"Synced: {stats.synced}, Errors: {stats.errors}"
        )

    return stats.model_dump()


async def _upsert_items_batch(items: list[dict[str, Any]], stats: ProductSyncResponse) -> None:
    """Upsert a batch of items into the PostgreSQL database using SQLAlchemy 2.0.

    Args:
        items: List of item dictionaries from Zoho API.
        stats: The statistics object to update with results.
    """
    if not items:
        return

    # Prepare the values for the bulk insert
    values = []
    for item in items:
        if item.get("status") != "active":
            continue

        # Parse fields mapping Zoho semantics to our Product model
        sku = item.get("sku")
        if not sku:
            continue

        item_id = item.get("item_id")
        name = item.get("name")
        description = item.get("description")
        category = item.get("group_name")
        rate = float(item.get("rate", 0.0))
        stock_on_hand = int(item.get("stock_on_hand", 0))

        image_doc_id = item.get("image_document_id")
        image_url = f"https://inventory.zoho.eu/api/v1/documents/{image_doc_id}" if image_doc_id else None

        values.append({
            "sku": sku,
            "zoho_item_id": item_id,
            "name_en": name or "Unknown",
            "description_en": description,
            "category": category,
            "price": rate,
            "stock": stock_on_hand,
            "image_url": image_url,
            "is_active": True,
        })

    if not values:
        return

    # Use a new async session to perform the database operations
    async with async_session_factory() as session:
        try:
            # Create PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert) statement
            stmt = pg_upsert(Product).values(values)

            # Update columns corresponding to the values mapping, excluding sku on conflict
            set_dict = {
                "zoho_item_id": stmt.excluded.zoho_item_id,
                "name_en": stmt.excluded.name_en,
                "description_en": stmt.excluded.description_en,
                "category": stmt.excluded.category,
                "price": stmt.excluded.price,
                "stock": stmt.excluded.stock,
                "image_url": stmt.excluded.image_url,
                "is_active": stmt.excluded.is_active,
            }

            set_dict["synced_at"] = func.now()  # type: ignore[assignment]

            stmt = stmt.on_conflict_do_update(
                index_elements=[Product.sku],
                set_=set_dict
            )

            # Execute the statement
            # RETURNING could be used to precisely track created vs updated,
            # but for simple sync we just execute and add all to synced count.
            await session.execute(stmt)
            await session.commit()

            stats.synced += len(values)

        except Exception as e:
            await session.rollback()
            logger.error(f"Database error during upsert batch: {e}")
            stats.errors += len(values)
