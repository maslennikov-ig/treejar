from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, text
from sqlalchemy.dialects.postgresql import insert as pg_upsert

from src.core.config import settings
from src.core.database import async_session_factory
from src.integrations.catalog.treejar_catalog import TreejarCatalogClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.models.product import Product
from src.schemas.product import ProductSyncResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _zoho_client(redis: Any) -> AsyncIterator[ZohoInventoryClient]:
    """Create a ZohoInventoryClient that is reliably closed on exit.

    Using an explicit context manager here ensures the underlying httpx
    connection pool is released even when the ARQ task is cancelled.
    """
    client = ZohoInventoryClient(redis_client=redis)
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def _treejar_catalog_client() -> AsyncIterator[TreejarCatalogClient]:
    client = TreejarCatalogClient()
    try:
        yield client
    finally:
        await client.close()


def _as_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_image_url(item: dict[str, Any]) -> str | None:
    images = item.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                continue
            url = _as_str(image.get("url"))
            if url:
                return url

    return _as_str(item.get("image"))


def _treejar_dedupe_key(item: dict[str, Any]) -> str | None:
    sku = _as_str(item.get("sku"))
    if sku:
        return sku

    slug = _as_str(item.get("slug"))
    if slug:
        return f"treejar-slug::{slug}"

    return None


def _normalize_treejar_product(item: dict[str, Any]) -> dict[str, Any] | None:
    dedupe_key = _treejar_dedupe_key(item)
    slug = _as_str(item.get("slug"))
    if dedupe_key is None or slug is None:
        return None

    list_price = _as_float(item.get("price"))
    sale_price = _as_float(item.get("salePrice"))
    price = sale_price if sale_price is not None else (list_price or 0.0)

    stock_quantity = _as_int(item.get("stockQuantity"))
    raw_in_stock = item.get("inStock")
    in_stock = raw_in_stock if isinstance(raw_in_stock, bool) else None
    if stock_quantity is not None:
        stock = max(stock_quantity, 0)
    else:
        stock = 1 if in_stock else 0

    leaf_category = _as_str(item.get("category"))
    parent_category = _as_str(item.get("parentCategory"))
    category = parent_category or leaf_category
    subcategory = leaf_category if parent_category else None
    currency = _as_str(item.get("currency")) or "AED"

    normalized_raw = {key: value for key, value in item.items() if value is not None}

    return {
        "sku": dedupe_key,
        "zoho_item_id": None,
        "name_en": _as_str(item.get("name")) or slug,
        "description_en": _as_str(item.get("description"))
        or _as_str(item.get("shortDescription")),
        "category": category,
        "subcategory": subcategory,
        "price": price,
        "currency": currency,
        "stock": stock,
        "image_url": _resolve_image_url(item),
        "attributes": {
            "source": settings.catalog_source_name,
            "treejar_slug": slug,
            "treejar_url": _as_str(item.get("url")),
            "treejar_category_slug": _as_str(item.get("categorySlug")),
            "treejar_parent_category": parent_category,
            "treejar_parent_category_slug": _as_str(item.get("parentCategorySlug")),
            "brand": _as_str(item.get("brand")),
            "manufacturer": _as_str(item.get("manufacturer")),
            "features": item.get("features")
            if isinstance(item.get("features"), list)
            else [],
            "specifications": item.get("specifications")
            if isinstance(item.get("specifications"), dict)
            else {},
            "images": item.get("images")
            if isinstance(item.get("images"), list)
            else [],
            "availability": {
                "in_stock": bool(in_stock) if in_stock is not None else stock > 0,
                "stock_quantity": stock_quantity,
                "price_excludes_vat": bool(item.get("priceExclVAT")),
            },
            "raw_source": normalized_raw,
        },
        "is_active": True,
    }


def _embedding_reset_expression(stmt: Any) -> Any:
    return case(
        (
            Product.name_en.is_distinct_from(stmt.excluded.name_en)
            | Product.description_en.is_distinct_from(stmt.excluded.description_en)
            | Product.category.is_distinct_from(stmt.excluded.category),
            None,
        ),
        else_=Product.embedding,
    )


async def sync_products_from_treejar_catalog(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ background job for the canonical Treejar catalog sync."""
    logger.info("Starting canonical Treejar catalog sync...")

    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
    sync_started_at = datetime.now(UTC)

    try:
        async with _treejar_catalog_client() as client:
            batch: list[dict[str, Any]] = []

            async for item in client.iter_all_products(
                limit=settings.catalog_api_page_size
            ):
                batch.append(item)
                if len(batch) >= settings.catalog_api_page_size:
                    await _upsert_treejar_products_batch(batch, stats)
                    batch.clear()

            if batch:
                await _upsert_treejar_products_batch(batch, stats)

    except Exception as exc:
        logger.error("Error syncing products from Treejar catalog: %s", exc)
        stats.errors += 1

    if stats.errors == 0 and stats.synced > 0:
        stats.deactivated = await _deactivate_stale_products(sync_started_at)
        stats.embeddings_generated = await _generate_missing_embeddings()

    logger.info(
        "Treejar catalog sync completed. Synced: %d, Created: %d, Updated: %d, "
        "Deactivated: %d, Embeddings: %d, Errors: %d",
        stats.synced,
        stats.created,
        stats.updated,
        stats.deactivated,
        stats.embeddings_generated,
        stats.errors,
    )

    return stats.model_dump()


async def sync_products_from_zoho(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ background job for the remaining Zoho operational product sync.

    The canonical source of truth for customer-facing catalog data is the
    Treejar catalog API. This job remains only for the operational Zoho path
    until product runtime is fully cut over.

    Args:
        ctx: The ARQ context dictionary containing the Redis pool.

    Returns:
        A dictionary with the sync stats matching ProductSyncResponse schema.
    """
    from datetime import datetime

    logger.info("Starting legacy Zoho Inventory operational sync...")

    redis = ctx["redis"]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
    sync_started_at = datetime.now(UTC)

    # --- Phase 1: Fetch and upsert from Zoho ---
    async with _zoho_client(redis) as client:
        page = 1
        has_more = True

        while has_more:
            logger.info("Fetching Zoho products page %d...", page)

            try:
                response_data = await client.get_items(page=page, per_page=200)
            except Exception as e:
                logger.error("Error fetching page %d from Zoho: %s", page, e)
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

    # --- Phase 2: Lifecycle management (only if sync had no errors) ---
    if stats.errors == 0 and stats.synced > 0:
        stats.deactivated = await _deactivate_stale_products(sync_started_at)
        stats.embeddings_generated = await _generate_missing_embeddings()

    logger.info(
        "Zoho sync completed. Synced: %d, Created: %d, Updated: %d, "
        "Deactivated: %d, Embeddings: %d, Errors: %d",
        stats.synced,
        stats.created,
        stats.updated,
        stats.deactivated,
        stats.embeddings_generated,
        stats.errors,
    )

    return stats.model_dump()


async def _upsert_items_batch(
    items: list[dict[str, Any]], stats: ProductSyncResponse
) -> None:
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
        # NOTE: This URL requires OAuth authentication and is not publicly accessible.
        # For WhatsApp/client-facing use, images must be proxied through our API.
        image_url = (
            f"https://inventory.zoho.eu/api/v1/documents/{image_doc_id}"
            if image_doc_id
            else None
        )

        values.append(
            {
                "sku": sku,
                "zoho_item_id": item_id,
                "name_en": name or "Unknown",
                "description_en": description,
                "category": category,
                "price": rate,
                "stock": stock_on_hand,
                "image_url": image_url,
                "is_active": True,
            }
        )

    if not values:
        return

    # Use a new async session to perform the database operations
    async with async_session_factory() as session:
        try:
            # Create PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert) statement
            stmt = pg_upsert(Product).values(values)

            # Only reset embedding when content that feeds it actually changed.
            # This avoids regenerating embeddings for 800 unchanged products every sync.
            conditional_embedding = _embedding_reset_expression(stmt)

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
                "embedding": conditional_embedding,
            }

            set_dict["synced_at"] = func.now()
            set_dict["updated_at"] = func.now()

            stmt = stmt.on_conflict_do_update(index_elements=["sku"], set_=set_dict)

            # Use RETURNING with xmax to distinguish inserts from updates:
            # xmax == 0 means a new INSERT, xmax > 0 means an UPDATE (conflict)
            result = await session.execute(stmt.returning(Product.id, text("xmax")))
            rows = result.all()
            await session.commit()

            for row in rows:
                if row[1] == 0:
                    stats.created += 1
                else:
                    stats.updated += 1
            stats.synced += len(rows)

        except Exception as e:
            await session.rollback()
            logger.error("Database error during upsert batch: %s", e)
            stats.errors += len(values)
            raise


async def _upsert_treejar_products_batch(
    items: list[dict[str, Any]], stats: ProductSyncResponse
) -> None:
    if not items:
        return

    values = []
    for item in items:
        normalized = _normalize_treejar_product(item)
        if normalized is None:
            continue
        values.append(normalized)

    if not values:
        return

    async with async_session_factory() as session:
        try:
            stmt = pg_upsert(Product).values(values)

            set_dict = {
                "zoho_item_id": func.coalesce(
                    Product.zoho_item_id, stmt.excluded.zoho_item_id
                ),
                "name_en": stmt.excluded.name_en,
                "description_en": stmt.excluded.description_en,
                "category": stmt.excluded.category,
                "subcategory": stmt.excluded.subcategory,
                "price": stmt.excluded.price,
                "currency": stmt.excluded.currency,
                "stock": stmt.excluded.stock,
                "image_url": stmt.excluded.image_url,
                "attributes": stmt.excluded.attributes,
                "is_active": stmt.excluded.is_active,
                "embedding": _embedding_reset_expression(stmt),
                "synced_at": func.now(),
                "updated_at": func.now(),
            }

            stmt = stmt.on_conflict_do_update(index_elements=["sku"], set_=set_dict)

            result = await session.execute(stmt.returning(Product.id, text("xmax")))
            rows = result.all()
            await session.commit()

            for row in rows:
                if row[1] == 0:
                    stats.created += 1
                else:
                    stats.updated += 1
            stats.synced += len(rows)

        except Exception:
            await session.rollback()
            logger.exception("Database error during Treejar upsert batch")
            stats.errors += len(values)
            raise


async def _deactivate_stale_products(sync_started_at: datetime) -> int:
    """Mark products as inactive if they were not updated during this sync cycle.

    Any product whose synced_at is older than the sync start time was not
    present in the Zoho response, meaning it was deleted or deactivated there.

    Returns:
        Number of products deactivated.
    """
    async with async_session_factory() as session:
        try:
            stmt = (
                text(
                    "UPDATE products SET is_active = false, embedding = NULL "
                    "WHERE is_active = true AND (synced_at IS NULL OR synced_at < :cutoff)"
                )
            ).bindparams(cutoff=sync_started_at)

            result = await session.execute(stmt)
            await session.commit()

            deactivated = result.rowcount  # type: ignore[attr-defined]
            if deactivated:
                logger.info("Deactivated %d stale products", deactivated)
            return deactivated  # type: ignore[no-any-return]
        except Exception as e:
            await session.rollback()
            logger.error("Error deactivating stale products: %s", e)
            return 0


async def _generate_missing_embeddings() -> int:
    """Generate embeddings for all products that lack them."""
    from src.rag.embeddings import generate_product_embeddings

    async with async_session_factory() as session:
        try:
            count = await generate_product_embeddings(session)
            logger.info("Generated embeddings for %d products", count)
            return count
        except Exception as e:
            logger.error("Error generating embeddings: %s", e)
            return 0
