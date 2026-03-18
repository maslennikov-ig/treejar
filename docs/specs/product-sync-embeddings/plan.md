# Product Sync Pipeline: Auto-Embeddings & Lifecycle Management — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Zoho product sync pipeline fully automated: generate embeddings for new products, reset embeddings for changed products, and deactivate disappeared products.

**Architecture:** Extend the existing `sync_products_from_zoho()` ARQ job with two new phases after the upsert loop: (1) deactivate stale products, (2) generate embeddings for all products with `embedding IS NULL`. The `_upsert_items_batch` will be modified to always set `embedding = NULL` on upsert to ensure changed products get re-embedded. `ProductSyncResponse` gains `deactivated` and `embeddings_generated` fields.

**Tech Stack:** Python, SQLAlchemy 2.0, PostgreSQL (pgvector), ARQ (background jobs), sentence-transformers (BAAI/bge-m3)

---

## Relevant Files

| File | Role |
|---|---|
| `src/integrations/inventory/sync.py` | Main sync logic — **primary modification target** |
| `src/rag/embeddings.py` | `generate_product_embeddings()` — called after sync |
| `src/schemas/product.py` | `ProductSyncResponse` schema — add new counters |
| `src/models/product.py` | `Product` model (read-only reference) |
| `src/worker.py` | ARQ cron config (read-only reference) |
| `tests/test_inventory_sync.py` | Existing unit tests — **extend** |

---

### Task 1: Extend `ProductSyncResponse` Schema

**Files:**
- Modify: `src/schemas/product.py:47-51`
- Test: `tests/test_inventory_sync.py`

**Step 1: Write the failing test**

Add to `tests/test_inventory_sync.py`:

```python
def test_sync_response_has_new_fields() -> None:
    resp = ProductSyncResponse(synced=0, created=0, updated=0, errors=0, deactivated=0, embeddings_generated=0)
    assert resp.deactivated == 0
    assert resp.embeddings_generated == 0
```

**Step 2: Run test to verify it fails**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_sync_response_has_new_fields -v
```
Expected: FAIL — `deactivated` and `embeddings_generated` are unexpected keyword arguments.

**Step 3: Write minimal implementation**

In `src/schemas/product.py`, modify `ProductSyncResponse`:

```python
class ProductSyncResponse(BaseModel):
    synced: int
    created: int
    updated: int
    errors: int
    deactivated: int = 0
    embeddings_generated: int = 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_sync_response_has_new_fields -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/schemas/product.py tests/test_inventory_sync.py
git commit -m "feat(sync): add deactivated and embeddings_generated counters to ProductSyncResponse"
```

---

### Task 2: Reset Embeddings in Upsert

**Files:**
- Modify: `src/integrations/inventory/sync.py:146-160` (the `set_dict` in `_upsert_items_batch`)
- Test: `tests/test_inventory_sync.py`

**Step 1: Write the failing test**

Add to `tests/test_inventory_sync.py`:

```python
@pytest.mark.asyncio
@patch("src.integrations.inventory.sync.async_session_factory")
async def test_upsert_resets_embedding(mock_session_factory: AsyncMock) -> None:
    """Verify that the upsert sets embedding = NULL so changed products get re-embedded."""
    items = [{"sku": "SKU_1", "status": "active", "name": "Updated Item"}]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)

    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    class MockResult:
        def all(self) -> list[tuple[str, int]]:
            return [("uuid-1", 1)]  # xmax > 0 = UPDATE

    mock_session.execute.return_value = MockResult()

    await _upsert_items_batch(items, stats)

    # Inspect the statement that was executed
    call_args = mock_session.execute.call_args
    stmt = call_args[0][0]
    # The ON CONFLICT SET clause must include embedding = None
    compiled = stmt.compile()
    set_clause_str = str(compiled)
    assert "embedding" in set_clause_str, "Upsert must reset embedding on conflict"
```

**Step 2: Run test to verify it fails**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_upsert_resets_embedding -v
```
Expected: FAIL — `embedding` not in set clause.

**Step 3: Write minimal implementation**

In `src/integrations/inventory/sync.py`, in the `_upsert_items_batch` function, add `embedding` to the `set_dict`:

```python
set_dict = {
    "zoho_item_id": stmt.excluded.zoho_item_id,
    "name_en": stmt.excluded.name_en,
    "description_en": stmt.excluded.description_en,
    "category": stmt.excluded.category,
    "price": stmt.excluded.price,
    "stock": stmt.excluded.stock,
    "image_url": stmt.excluded.image_url,
    "is_active": stmt.excluded.is_active,
    "embedding": None,  # Reset embedding so product gets re-embedded
}
```

**Step 4: Run test to verify it passes**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_upsert_resets_embedding -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/integrations/inventory/sync.py tests/test_inventory_sync.py
git commit -m "feat(sync): reset embedding on upsert to trigger re-embedding for changed products"
```

---

### Task 3: Deactivate Stale Products

**Files:**
- Modify: `src/integrations/inventory/sync.py` — add `_deactivate_stale_products()` function and call from `sync_products_from_zoho()`
- Test: `tests/test_inventory_sync.py`

**Step 1: Write the failing test**

Add to `tests/test_inventory_sync.py`:

```python
from src.integrations.inventory.sync import _deactivate_stale_products

@pytest.mark.asyncio
@patch("src.integrations.inventory.sync.async_session_factory")
async def test_deactivate_stale_products(mock_session_factory: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    # Mock the execute result to return rowcount = 3
    mock_result = AsyncMock()
    mock_result.rowcount = 3
    mock_session.execute.return_value = mock_result

    from datetime import datetime, timezone
    sync_start = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
    
    count = await _deactivate_stale_products(sync_start)
    
    assert count == 3
    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_deactivate_stale_products -v
```
Expected: FAIL — `_deactivate_stale_products` does not exist.

**Step 3: Write minimal implementation**

Add to `src/integrations/inventory/sync.py`:

```python
from datetime import datetime

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
            
            deactivated = result.rowcount
            if deactivated:
                logger.info("Deactivated %d stale products", deactivated)
            return deactivated
        except Exception as e:
            await session.rollback()
            logger.error("Error deactivating stale products: %s", e)
            return 0
```

**Step 4: Run test to verify it passes**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_deactivate_stale_products -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/integrations/inventory/sync.py tests/test_inventory_sync.py
git commit -m "feat(sync): add _deactivate_stale_products to mark disappeared products inactive"
```

---

### Task 4: Wire Everything Together in `sync_products_from_zoho`

**Files:**
- Modify: `src/integrations/inventory/sync.py:34-80` — add Phase 2 (deactivate + embed) after the upsert loop
- Test: `tests/test_inventory_sync.py`

**Step 1: Write the failing test**

Add to `tests/test_inventory_sync.py`:

```python
@pytest.mark.asyncio
async def test_sync_calls_deactivate_and_embed() -> None:
    ctx = {"redis": AsyncMock()}

    mock_client_instance = AsyncMock()
    mock_client_instance.get_items.return_value = {
        "items": [{"sku": "ITEM_1", "status": "active", "name": "Item 1"}],
        "page_context": {"has_more_page": False},
    }

    with (
        patch("src.integrations.inventory.sync._upsert_items_batch", new_callable=AsyncMock) as mock_upsert,
        patch("src.integrations.inventory.sync._zoho_client") as mock_cm,
        patch("src.integrations.inventory.sync._deactivate_stale_products", new_callable=AsyncMock, return_value=2) as mock_deactivate,
        patch("src.integrations.inventory.sync._generate_missing_embeddings", new_callable=AsyncMock, return_value=5) as mock_embed,
    ):
        mock_cm.return_value.__aenter__.return_value = mock_client_instance

        result = await sync_products_from_zoho(ctx)

        mock_deactivate.assert_awaited_once()
        mock_embed.assert_awaited_once()
        assert result["deactivated"] == 2
        assert result["embeddings_generated"] == 5
```

**Step 2: Run test to verify it fails**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py::test_sync_calls_deactivate_and_embed -v
```
Expected: FAIL — `_generate_missing_embeddings` does not exist, `deactivated` not in result.

**Step 3: Write minimal implementation**

Modify `sync_products_from_zoho` in `src/integrations/inventory/sync.py`:

```python
async def sync_products_from_zoho(ctx: dict[str, Any]) -> dict[str, int]:
    """ARQ background job to synchronize products from Zoho Inventory to the database."""
    from datetime import datetime, timezone
    
    logger.info("Starting Zoho Inventory product sync...")

    redis = ctx["redis"]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
    sync_started_at = datetime.now(timezone.utc)

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

            await _upsert_items_batch(items, stats)
            page += 1

    # --- Phase 2: Lifecycle management (only if sync had no errors) ---
    if stats.errors == 0 and stats.synced > 0:
        stats.deactivated = await _deactivate_stale_products(sync_started_at)
        stats.embeddings_generated = await _generate_missing_embeddings()

    logger.info(
        "Zoho sync completed. Synced: %d, Created: %d, Updated: %d, "
        "Deactivated: %d, Embeddings: %d, Errors: %d",
        stats.synced, stats.created, stats.updated,
        stats.deactivated, stats.embeddings_generated, stats.errors,
    )

    return stats.model_dump()
```

Add the `_generate_missing_embeddings` wrapper:

```python
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
```

**Step 4: Run all tests to verify everything passes**

```bash
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py -v
```
Expected: ALL PASS

**Step 5: Run the full test suite**

```bash
cd /home/me/code/treejar && uv run pytest --tb=short -q
```
Expected: No regressions

**Step 6: Commit**

```bash
git add src/integrations/inventory/sync.py tests/test_inventory_sync.py
git commit -m "feat(sync): wire up stale deactivation and auto-embedding in sync pipeline"
```

---

### Task 5: Dockerfile — Copy `docs/` Into Container

**Files:**
- Modify: `Dockerfile` — add `COPY docs/ docs/` before the CMD
- Test: manual (build and verify)

The knowledge base indexer (`src/rag/indexer.py`) reads from `/app/docs/`. Currently the `Dockerfile` does not copy the `docs/` directory.

**Step 1: Add COPY to Dockerfile**

Find the appropriate location in the `Dockerfile` (after `COPY src/ src/`) and add:

```dockerfile
COPY docs/ docs/
```

**Step 2: Verify by building the image**

```bash
cd /home/me/code/treejar && docker build --target production -t treejar-test . 2>&1 | tail -5
```
Expected: Build succeeds

**Step 3: Commit**

```bash
git add Dockerfile
git commit -m "fix(docker): copy docs/ directory into container for knowledge base indexer"
```

---

## Verification Plan

### Automated Tests

```bash
# Run all sync-related tests
cd /home/me/code/treejar && uv run pytest tests/test_inventory_sync.py tests/test_zoho_sync.py -v

# Run full suite to check for regressions
cd /home/me/code/treejar && uv run pytest --tb=short -q

# Type checking
cd /home/me/code/treejar && uv run mypy src/integrations/inventory/sync.py src/schemas/product.py

# Linting
cd /home/me/code/treejar && uv run ruff check src/integrations/inventory/sync.py src/schemas/product.py
```

### Manual Verification on VPS (after deploy)

1. SSH into VPS and manually trigger the sync job:
```bash
ssh -i .tmp/id_ed25519 root@136.243.71.213 "cd /opt/treejar-prod && docker compose -p treejar-prod exec -T app python -c '
import asyncio, sys
sys.path.insert(0, \"/app\")
from src.integrations.inventory.sync import sync_products_from_zoho
from unittest.mock import AsyncMock
import redis.asyncio as redis_lib

async def main():
    r = redis_lib.from_url(\"redis://redis:6379\")
    ctx = {\"redis\": r}
    result = await sync_products_from_zoho(ctx)
    print(result)
    await r.aclose()

asyncio.run(main())
'"
```

2. Verify the output contains `deactivated` and `embeddings_generated` keys with numeric values.
