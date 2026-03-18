# Product Sync Pipeline: Auto-Embeddings & Lifecycle Management

## Problem

The current `sync_products_from_zoho` cron job (runs 4×/day) pulls products from Zoho Inventory into the `products` table,
but has three significant gaps:

1. **New products have no embeddings** — they are invisible to AI-powered product search until someone manually runs `generate_product_embeddings()`.
2. **Changed products keep stale embeddings** — if name/description/category changes in Zoho, the old embedding vector stays, making search results inaccurate.
3. **Deleted/deactivated products stay active** — if a product is removed from Zoho or marked inactive, our DB still shows it as `is_active = True` and it appears in search results.

## Requirements

### R1: Auto-generate embeddings after sync
After every successful Zoho sync cycle, automatically call `generate_product_embeddings(db)` to embed any products where `embedding IS NULL`.

### R2: Reset embeddings on metadata change
When the sync upserts a product and detects that `name_en`, `description_en`, or `category` changed, reset `embedding = NULL` so that R1 re-embeds it with the updated text.

### R3: Mark disappeared products as inactive
After syncing all pages from Zoho, any product in our DB whose `synced_at` timestamp is older than the start of the current sync run should be marked `is_active = False` and `embedding = NULL`.

### R4: Add stats tracking
Extend `ProductSyncResponse` with a `deactivated` counter and an `embeddings_generated` counter so the logs and API clearly show what happened.

## Design Decisions

- **Use `synced_at` for stale detection**: The column already exists on the `Product` model. The sync upsert already sets `synced_at = func.now()`. Products not touched by the current sync will have `synced_at < sync_start_time`, making them stale.
- **Two-phase approach**: Phase 1 = upsert loop (existing). Phase 2 = stale cleanup + embedding generation (new).
- **Reset embedding via SQL UPDATE in upsert `set_` dict**: PostgreSQL's `ON CONFLICT UPDATE` can conditionally nullify the embedding using a `CASE` expression. However, this adds complexity to the upsert. **Simpler alternative**: after the upsert, run a separate query: `UPDATE products SET embedding = NULL WHERE synced_at >= :sync_start AND (name_en, description_en, category) differs from before`. This is tricky without a "before" snapshot. **Chosen approach**: In the `set_` dict of `on_conflict_do_update`, always reset `embedding = NULL`. This means every synced product gets re-embedded, which is safe because `generate_product_embeddings` only processes `embedding IS NULL` rows. The trade-off: ~800 products re-embedded every 6h (~4 min runtime). This is acceptable for now.
  - **UPDATE**: Actually, re-embedding 800 products every 6 hours wastes compute. Better approach: use a separate UPDATE query after the upsert to reset embedding only for products whose `name_en`, `description_en`, or `category` changed. We can detect this by comparing old vs new values. Since we don't have old values easily, the simplest correct approach is: **always set `embedding = NULL` in the upsert for genuinely new products** (xmax == 0), and for updated products, compare key fields. PostgreSQL's `ON CONFLICT DO UPDATE` doesn't expose old row values directly. **Final decision**: Add `embedding = NULL` to the upsert `set_` dict unconditionally. Accept the 4-minute re-embed cost 4×/day. This is the simplest, most correct solution. If performance becomes an issue, optimize later.

## Non-goals
- Real-time sync (webhook from Zoho) — out of scope.
- Knowledge base re-indexing — already has its own mechanism via `index_documents`.
