# Code Review: Week 2 Implementation — Treejar AI Sales Bot

**Date**: 2026-02-25
**Reviewer**: Code Review Agent (Claude Sonnet 4.6 via Context7-augmented analysis)
**Scope**: Week 2 new files — Zoho integration, RAG pipeline, product API, ARQ worker, models, tests, migration
**Context7 Libraries Checked**: httpx, SQLAlchemy 2.1, arq

---

## 1. Summary

The Week 2 implementation establishes the three core subsystems: Zoho Inventory sync, RAG (embeddings + vector search), and the products API. The code demonstrates a solid architectural foundation — protocols are defined and implemented correctly, SQLAlchemy 2.0 async patterns are mostly followed, and the separation of concerns is clear. The singleton embedding engine, Redis-based token locking, and hybrid search approach show good design awareness.

However, there are several issues that will cause real failures in production if unaddressed, plus a cluster of important issues around event-loop blocking, resource lifetime, and incomplete error handling. The test suite covers the happy path but has meaningful gaps on error paths and realistic integration scenarios.

**Overall assessment**: Good foundation, not production-ready as-is. The critical and important issues must be fixed before the first staging deployment.

---

## 2. Critical Issues

Issues that will cause failures in production.

---

### CRIT-01 — fastembed blocks the event loop on every call

**File**: `src/rag/embeddings.py`, lines 37–51; `src/rag/pipeline.py`, lines 113, 163; `src/rag/indexer.py`, line 62
**Severity**: CRITICAL

**Description**: `fastembed.TextEmbedding.embed()` is a synchronous CPU-bound operation (it runs a ONNX model via numpy). Both `embed()` and `embed_batch()` are called directly on the asyncio event loop without any thread offloading. In a production FastAPI server handling concurrent WhatsApp messages, this blocks all other coroutines for the duration of inference — typically 50–500 ms per call depending on batch size and hardware.

The code even acknowledges this in a comment (`# For production with many products, this might block the event loop`) but the fix was not applied.

**Impact**: Every `/search` API call will freeze the entire server for hundreds of milliseconds. Under any real concurrency this becomes a total availability problem.

**Suggested fix**: Wrap both `embed()` and `embed_batch()` with `asyncio.to_thread()`:

```python
# src/rag/embeddings.py

import asyncio

class EmbeddingEngine:

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text (sync — use embed_async in async contexts)."""
        model = self._get_model()
        generator = model.embed([text])
        for result in generator:
            return list(float(x) for x in result)
        return []

    async def embed_async(self, text: str) -> list[float]:
        """Non-blocking version for use in async contexts."""
        return await asyncio.to_thread(self.embed, text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Sync batch embed."""
        model = self._get_model()
        return [vec.tolist() for vec in model.embed(texts)]

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Non-blocking batch embed for use in async contexts."""
        return await asyncio.to_thread(self.embed_batch, texts)
```

Then in `pipeline.py` and `indexer.py`, use the `_async` variants:

```python
# pipeline.py search_products()
query_vector = await embedding_engine.embed_async(query.query)

# embeddings.py generate_product_embeddings()
embeddings = await asyncio.to_thread(engine.embed_batch, texts)
```

---

### CRIT-02 — ZohoInventoryClient is never closed when an exception occurs early in sync

**File**: `src/integrations/inventory/sync.py`, lines 29–60
**Severity**: CRITICAL

**Description**: `client = ZohoInventoryClient(redis_client=redis)` creates an `httpx.AsyncClient` internally. The `finally` block calls `await client.close()`, but only if the `try` block is entered. If `ZohoInventoryClient.__init__` itself raises (e.g., `settings` misconfiguration, Redis connection issue during creation), the `finally` block still executes — that part is correct. However, the httpx client is created unconditionally in `__init__`, not lazily, so a partially-initialised client with an open connection pool will exist and will be closed by the `finally`. This is correct for the `sync.py` function.

The real issue is in `zoho_inventory.py` lines 62–72 inside `_ensure_token()`: a **second** `httpx.AsyncClient` is created as a plain `async with` context manager for the OAuth token refresh call. This is correct usage and does close itself. No issue here.

The actual lifecycle problem: the long-lived `self.client` (line 26–29) is used as a module-level instance-per-ARQ-job. If the ARQ job is cancelled mid-execution (e.g., job timeout, worker SIGTERM), the `finally` block is not guaranteed to run in all cancellation scenarios. This can leak connection pool resources.

More concretely: `httpx` docs state that for long-lived clients not used as context managers, you must ensure `aclose()` is called. The current pattern is correct for the happy path but fragile under cancellation.

**Suggested fix**: Use `asyncio.shield` or restructure as a context manager in the sync job:

```python
# sync.py — use async with for guaranteed cleanup

async def sync_products_from_zoho(ctx: dict[str, Any]) -> dict[str, int]:
    redis = ctx["redis"]
    stats = ProductSyncResponse(synced=0, created=0, updated=0, errors=0)

    # Guarantee cleanup even under task cancellation
    client = ZohoInventoryClient(redis_client=redis)
    try:
        async with asyncio.timeout(540):  # 9 min — within ARQ 5 min default timeout
            await _run_sync(client, stats)
    finally:
        await client.close()

    return stats.model_dump()
```

Alternatively, add an `async def __aenter__` / `__aexit__` to `ZohoInventoryClient` and use `async with ZohoInventoryClient(redis) as client:`.

---

### CRIT-03 — Upsert conflict target uses `Product.sku` column object, not a string

**File**: `src/integrations/inventory/sync.py`, line 136; `src/rag/indexer.py`, line 74
**Severity**: CRITICAL

**Description**: The `on_conflict_do_update()` call passes a SQLAlchemy column object as the `index_elements` value:

```python
stmt = stmt.on_conflict_do_update(
    index_elements=[Product.sku],   # <-- column object, not string
    set_=set_dict
)
```

The PostgreSQL dialect's `on_conflict_do_update` `index_elements` parameter accepts either a list of column names (strings), a list of `Column` objects, or a constraint name. Passing `Product.sku` (a mapped `InstrumentedAttribute`) works in SQLAlchemy 2.0 in practice because it resolves to the column, but it is not the documented safe form and behaves differently from the ORM mapped attribute vs. the `Table.c.sku` column.

Same issue in `indexer.py` line 74 with `KnowledgeBase.source` and `KnowledgeBase.title`.

**Suggested fix**: Use string column names, which is unambiguous:

```python
stmt = stmt.on_conflict_do_update(
    index_elements=["sku"],
    set_=set_dict
)

# indexer.py
stmt = stmt.on_conflict_do_update(
    index_elements=["source", "title"],
    set_={...}
)
```

---

### CRIT-04 — Vector search does not filter out NULL embeddings

**File**: `src/rag/pipeline.py`, lines 116, 166; `src/integrations/vector/base.py` impl in `pipeline.py` lines 38–58
**Severity**: CRITICAL

**Description**: Both `search_products()` and `search_knowledge()` apply `ORDER BY embedding <=> query_vector` without first filtering out rows where `embedding IS NULL`. Products and knowledge base records can have NULL embeddings (newly synced from Zoho before the embedding job runs, or if the embedding job fails).

pgvector throws a runtime error when comparing NULL vectors with the cosine distance operator:

```
ERROR: operator does not exist: vector <=> vector
```

Actually, pgvector silently returns NULL for the distance when comparing against a NULL column, which means all un-embedded products will sort to the end — but this also means the query returns a mix of relevant and completely random results (any product with a NULL embedding can appear after products with real embeddings, depending on the NULL sort order which is NULLS LAST by default in pgvector). More dangerously, if ALL products have NULL embeddings (fresh deployment, embedding job hasn't run), the entire result set is un-ordered and the "semantic search" silently degrades to a full table scan with undefined ordering.

**Suggested fix**:

```python
# pipeline.py — search_products()
stmt = select(Product).where(
    Product.is_active.is_(True),
    Product.embedding.is_not(None),  # exclude un-embedded products
)

# pipeline.py — search_knowledge()
stmt = select(KnowledgeBase).where(
    KnowledgeBase.embedding.is_not(None),
)
```

Same fix needed in `PgVectorStore.search()` (line 38).

---

### CRIT-05 — EmbeddingEngine singleton is not thread-safe during lazy model loading

**File**: `src/rag/embeddings.py`, lines 22–35
**Severity**: CRITICAL

**Description**: The singleton uses a class-level `_instance` and `_model`. The `_get_model()` lazy load (lines 29–35) has a TOCTOU race: two concurrent coroutines can both see `self._model is None` and both call `TextEmbedding(model_name=...)`, triggering two model loads simultaneously. With `asyncio.to_thread` (the fix for CRIT-01), this becomes a real concurrent race because the model loading happens in separate threads.

`TextEmbedding.__init__` downloads ONNX files if not cached, which is both slow and non-idempotent if two downloads race to write the same cache files.

**Suggested fix**: Use an `asyncio.Lock` for the async context, or a `threading.Lock` when running in threads:

```python
import threading

class EmbeddingEngine:
    _instance: EmbeddingEngine | None = None
    _model: TextEmbedding | None = None
    _lock: threading.Lock = threading.Lock()

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            with self._lock:
                if self._model is None:  # double-checked locking
                    logger.info("Loading embedding model %s...", settings.embedding_model)
                    self._model = TextEmbedding(model_name=settings.embedding_model)
                    logger.info("Embedding model loaded successfully.")
        return self._model
```

---

## 3. Important Issues

Issues that should be fixed before the service handles real traffic.

---

### IMP-01 — f-strings used in logging calls throughout (should use lazy % formatting)

**Files**: `sync.py` lines 38, 43, 62–64; `embeddings.py` lines 32, 73, 104; `indexer.py` lines 26, 50; `pipeline.py` (none, uses logger correctly); `api/v1/products.py` lines 76, 101
**Severity**: IMPORTANT

**Description**: Python's `logging` module is designed for lazy string interpolation using `%` formatting, specifically to avoid formatting cost when the log level is not active. Using f-strings eagerly evaluates the string even if the log message is never emitted. This matters for high-volume log calls (e.g., per-batch progress in embedding loops).

Additionally, `ruff` rule `G004` (flake8-logging-format) flags f-strings in logging — if `G` rules are ever added to the ruff config this will become a lint error.

**Suggested fix**:

```python
# Instead of:
logger.info(f"Fetching Zoho products page {page}...")
logger.error(f"Error fetching page {page} from Zoho: {e}")

# Use:
logger.info("Fetching Zoho products page %d...", page)
logger.error("Error fetching page %d from Zoho: %s", page, e)
```

---

### IMP-02 — `get_stock_bulk` sends N concurrent requests with no rate limiting

**File**: `src/integrations/inventory/zoho_inventory.py`, lines 176–187
**Severity**: IMPORTANT

**Description**: `get_stock_bulk` fires one request per SKU with `asyncio.gather(*tasks)` — no concurrency limit. If called with 50+ SKUs, 50+ concurrent requests hit the Zoho API simultaneously. Zoho Inventory enforces rate limits (the code already handles 429 in `_request`), but the retry introduces exponential back-off that degrades the gather's total latency and can cascade errors.

**Suggested fix**: Use `asyncio.Semaphore` to cap concurrency:

```python
async def get_stock_bulk(self, skus: list[str]) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(5)  # max 5 concurrent SKU requests

    async def _fetch(sku: str) -> dict[str, Any] | None:
        async with sem:
            return await self.get_stock(sku)

    results = await asyncio.gather(*[_fetch(sku) for sku in skus])
    return [r for r in results if r is not None]
```

---

### IMP-03 — `_upsert_items_batch` silently counts errors as all items when DB fails

**File**: `src/integrations/inventory/sync.py`, lines 148–151
**Severity**: IMPORTANT

**Description**: When the entire batch fails, `stats.errors += len(values)` adds the full batch count to errors. But the session is rolled back and no items were persisted. On the next run the same items will be re-fetched and attempted again — so the error count per item is inflated on every failed sync rather than reflecting a per-item state. This makes the `errors` count in `ProductSyncResponse` misleading.

More seriously: if Zoho returns the data correctly but the DB upsert fails (e.g., connection error), `stats.synced` stays at zero but the function returns `stats.model_dump()` with `errors = N`. The ARQ job does not raise, so the error is silently swallowed and the cron will retry in 6 hours. There is no alerting or re-queue mechanism.

**Suggested fix**: Re-raise the exception from `_upsert_items_batch` after recording the stats, so ARQ marks the job as failed and applies its own retry logic:

```python
except Exception as e:
    await session.rollback()
    logger.error("Database error during upsert batch: %s", e)
    stats.errors += len(values)
    raise  # let ARQ handle retry
```

---

### IMP-04 — `sync_products_from_zoho` creates a new `async_session_factory` per batch call

**File**: `src/integrations/inventory/sync.py`, lines 116–151; `src/core/database.py`
**Severity**: IMPORTANT

**Description**: `_upsert_items_batch` calls `async with async_session_factory() as session:` directly, bypassing the FastAPI `get_db` dependency. This is correct for an ARQ worker, but it means one new session (and one DB connection from the pool) is acquired per batch of 200 items. For a large catalog this is fine. However, `async_session_factory` is defined at module level in `database.py` with `expire_on_commit=False` missing — wait, checking: it is NOT set in `database.py` line 21–25. The SQLAlchemy docs confirm that for asyncio you want `expire_on_commit=False` to avoid lazy-loading expired attributes after a commit in an async context.

For the sync job this doesn't matter (objects aren't accessed after commit). But the same session factory is used by the FastAPI `get_db`, where `expire_on_commit=True` (the default) causes any ORM object returned from a request handler and accessed after `commit()` to raise `MissingGreenlet` errors in async context.

**Suggested fix** in `src/core/database.py`:

```python
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # required for asyncio — prevents MissingGreenlet on post-commit access
)
```

---

### IMP-05 — `image_url` built from Zoho internal document ID is not a public URL

**File**: `src/integrations/inventory/sync.py`, lines 97–98
**Severity**: IMPORTANT

**Description**: The image URL is constructed as:

```python
image_url = f"https://inventory.zoho.eu/api/v1/documents/{image_doc_id}"
```

This is the Zoho Inventory API endpoint for document access, which requires OAuth authentication. This URL cannot be served to end-users or used in WhatsApp messages — it will return 401 for anyone without a valid Zoho OAuth token.

**Suggested fix**: Either:
1. Proxy the image through a server-side endpoint that attaches the OAuth token before forwarding to Zoho.
2. Store the `image_document_id` separately and resolve the URL on demand via the Zoho API.
3. Store the raw `image_document_id` as a separate column and build the URL only server-side when serving API responses.

At minimum, add a comment documenting this limitation so it is not accidentally passed to the WhatsApp API.

---

### IMP-06 — `ProductSyncResponse` fields `created` and `updated` are never populated

**File**: `src/integrations/inventory/sync.py`, line 31 + lines 143–146; `src/schemas/product.py` lines 47–51
**Severity**: IMPORTANT

**Description**: `ProductSyncResponse` has `created: int` and `updated: int` fields. The sync job initialises them to zero and never sets them — only `synced` and `errors` are used. The schema implies precision (created vs. updated) that the implementation does not deliver.

The comment on lines 141–142 acknowledges this (`RETURNING could be used...`) but treats it as optional. For a sync job that can run 4× per day, having accurate created/updated counts matters for monitoring.

**Suggested fix**: Use `INSERT ... ON CONFLICT DO UPDATE ... RETURNING xmax` to distinguish inserts from updates (xmax = 0 for new rows):

```python
result = await session.execute(stmt.returning(Product.id, text("xmax")))
rows = result.all()
for row in rows:
    if row[1] == 0:   # xmax == 0 means this was an INSERT
        stats.created += 1
    else:
        stats.updated += 1
stats.synced += len(rows)
```

---

### IMP-07 — `/sync` endpoint creates and destroys a Redis pool on every request

**File**: `src/api/v1/products.py`, lines 91–95
**Severity**: IMPORTANT

**Description**: Every call to `POST /sync` does:

```python
redis_settings = RedisSettings.from_dsn(settings.redis_url)
pool = await create_pool(redis_settings)
await pool.enqueue_job("sync_products_from_zoho")
await pool.aclose()
```

Creating and tearing down a Redis connection pool per HTTP request is wasteful (adds ~10–50 ms latency, consumes Redis connections). The pool should be created once at application startup and stored in app state.

**Suggested fix**: Create the ARQ pool in the FastAPI lifespan and inject it via dependency:

```python
# main.py lifespan
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.arq_pool.aclose()

# products.py
from fastapi import Request

@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(body: ProductSyncRequest, request: Request) -> ProductSyncResponse:
    pool = request.app.state.arq_pool
    await pool.enqueue_job("sync_products_from_zoho")
    return ProductSyncResponse(synced=0, created=0, updated=0, errors=0)
```

---

### IMP-08 — `_parse_sales_rules` is brittle against markdown table formatting variations

**File**: `src/rag/indexer.py`, lines 125–171
**Severity**: IMPORTANT

**Description**: The table parser relies on very specific markdown formatting:
- Line must start with `|`
- Must NOT start with `| -` (to skip separator rows)
- `cols[0].isdigit()` to detect data rows

This will silently produce zero chunks if:
- The markdown has trailing spaces (`| - ` instead of `| -`)
- The rule number has a leading space: `| 1 |` vs `|1|`
- The separator row uses `|---|` instead of `| - |`

There is also a hardcoded string scan for specific Russian phrases in lines 159–161 that will break if those lines change in the source document.

**Suggested fix**: Use a proper markdown table parser (e.g., the `marko` or `mistletoe` library), or add defensive logging when zero chunks are extracted so failures are visible rather than silent.

---

### IMP-09 — `docs_dir = Path("docs")` is a relative path — breaks when CWD != project root

**File**: `src/rag/indexer.py`, line 24
**Severity**: IMPORTANT

**Description**: `Path("docs")` resolves relative to the current working directory at runtime. When the ARQ worker is launched via Docker or from a different directory, this path will not resolve correctly and `index_documents()` will silently return 0 with a warning log that may go unnoticed.

**Suggested fix**: Use `__file__`-relative path resolution:

```python
from pathlib import Path

# Resolve relative to project root, not CWD
_PROJECT_ROOT = Path(__file__).parent.parent.parent  # src/rag/indexer.py → project root
_DOCS_DIR = _PROJECT_ROOT / "docs"

async def index_documents(db: AsyncSession) -> int:
    if not _DOCS_DIR.exists():
        logger.warning("Docs directory %s does not exist.", _DOCS_DIR)
        return 0
    ...
```

---

### IMP-10 — `worker.py` startup/shutdown hooks are empty and don't initialise dependencies

**File**: `src/worker.py`, lines 12–17
**Severity**: IMPORTANT

**Description**: The `startup` and `shutdown` hooks exist as stubs but do nothing. The `sync_products_from_zoho` job accesses `ctx["redis"]` — this works because ARQ automatically sets `ctx["redis"]` before calling the function. However, if other jobs are added that need a DB session or the embedding model, there is no initialisation pathway.

More importantly, the ARQ worker's default `job_timeout` is 300 seconds (5 minutes). A full Zoho sync of a large catalog could easily exceed this. There is no explicit timeout configured.

**Suggested fix**:

```python
from arq.connections import RedisSettings
from arq.cron import cron

class WorkerSettings:
    functions: list[Any] = [sync_products_from_zoho]
    cron_jobs = [
        cron(sync_products_from_zoho, hour={0, 6, 12, 18}, run_at_startup=False),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 600      # 10 minutes — accommodate large catalogs
    max_jobs = 2           # limit concurrent sync jobs
    keep_result = 3600     # keep results for 1 hour for debugging
```

---

## 4. Improvements

Code quality, minor issues, and nice-to-haves.

---

### IMPR-01 — Singleton `__new__` pattern is unconventional; prefer a module-level instance

**File**: `src/rag/embeddings.py`, lines 19–35
**Severity**: IMPROVEMENT

**Description**: The `__new__`-based singleton is valid Python but surprising and harder to test (requires manually resetting `_instance = None` in tests, which the tests do). A module-level instance is idiomatic, easier to understand, and simpler to mock.

```python
# embeddings.py
_embedding_engine: EmbeddingEngine | None = None

def get_embedding_engine() -> EmbeddingEngine:
    global _embedding_engine
    if _embedding_engine is None:
        _embedding_engine = EmbeddingEngine()
    return _embedding_engine
```

FastAPI's `Depends(get_embedding_engine)` already follows this factory pattern. The API layer (`products.py` line 62–63) already has a `get_embedding_engine` function that instantiates `EmbeddingEngine()` — make it use the module-level singleton instead.

---

### IMPR-02 — `ProductSearchQuery.limit` has no maximum bound

**File**: `src/schemas/product.py`, line 34
**Severity**: IMPROVEMENT

**Description**: `limit: int = 5` has no upper bound validator. An API caller can request `limit=10000`, triggering a full table scan with vector sort and returning a very large response payload.

```python
from pydantic import Field

class ProductSearchQuery(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
```

---

### IMPR-03 — `get_db` generator commits on every successful request, even reads

**File**: `src/core/database.py`, lines 28–35
**Severity**: IMPROVEMENT

**Description**: The `get_db` dependency commits on successful yield exit even for pure read operations (GET endpoints). While PostgreSQL makes read-only transactions very cheap, this is unnecessary overhead and slightly misleading.

A common pattern is to only auto-commit for write transactions, or to rely on the application code to commit explicitly. For a read-heavy AI bot this matters less, but it sets an incorrect pattern for future endpoint authors.

---

### IMPR-04 — `_parse_company_values` may produce empty `content` chunks

**File**: `src/rag/indexer.py`, lines 175–219
**Severity**: IMPROVEMENT

**Description**: The parser adds a chunk whenever it encounters a section marker (`️⃣` in line or `*1`/`*2` prefix). If the section has no body lines that pass the filter condition, `current_body` will be empty, resulting in chunks with empty `content`. These get embedded and indexed as zero-information vectors, polluting the knowledge base.

```python
# Add a guard before appending
body_text = "\n".join(current_body).strip(" *")
if body_text:
    chunks.append({...})
```

---

### IMPR-05 — `updated_at` is not updated by the upsert in `sync.py`

**File**: `src/integrations/inventory/sync.py`, lines 122–133
**Severity**: IMPROVEMENT

**Description**: The `set_dict` for the upsert includes `synced_at = func.now()` but does not include `updated_at`. The `TimestampMixin` uses `onupdate=func.now()` on the ORM level, but this only fires for ORM `UPDATE` statements, not for raw `INSERT ... ON CONFLICT DO UPDATE` SQL statements. As a result, `updated_at` will never be updated by the sync job, always showing the original insert time.

```python
set_dict["updated_at"] = func.now()
set_dict["synced_at"] = func.now()
```

---

### IMPR-06 — `zoho_item_id` has `unique=True` but is nullable — will fail on second NULL

**File**: `src/models/product.py`, line 19
**Severity**: IMPROVEMENT

**Description**: `zoho_item_id: Mapped[str | None] = mapped_column(String, unique=True, default=None)`. In PostgreSQL, a `UNIQUE` constraint treats multiple NULL values as distinct (not equal), so multiple NULL `zoho_item_id` rows are allowed. This is the correct PostgreSQL behaviour and means the constraint won't error.

However, if Zoho returns an item without an `item_id` (which shouldn't happen but defensive coding helps), the sync will insert a row with `zoho_item_id=NULL`. On re-sync, the upsert conflicts on `sku` (correct), so this is fine in practice. The `unique=True` on a nullable column is misleading though — add a comment or use a partial unique index instead.

---

### IMPR-07 — `PgVectorStore.upsert()` commits inside the method, violating unit-of-work pattern

**File**: `src/rag/pipeline.py`, lines 76–102
**Severity**: IMPROVEMENT

**Description**: `PgVectorStore.upsert()` calls `await self.db.commit()` on line 102. This commits the session mid-flow and breaks the unit-of-work pattern — any caller using this method as part of a larger transaction will have their transaction committed prematurely. The `VectorStore` protocol does not specify commit behaviour, so this is an implementation detail violation.

```python
async def upsert(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None:
    stmt = pg_upsert(KnowledgeBase).values(...)
    stmt = stmt.on_conflict_do_update(...)
    await self.db.execute(stmt)
    # Remove: await self.db.commit()
    # Let the caller decide when to commit
```

---

### IMPR-08 — `get_items` passes `cf_end_product` as a string "true", not boolean

**File**: `src/integrations/inventory/zoho_inventory.py`, line 153
**Severity**: IMPROVEMENT

**Description**: Zoho custom field filters are URL query parameters. `cf_end_product=true` is the correct string representation for Zoho's API (it doesn't use JSON booleans in query params). However, this is a custom field that may or may not exist in every Zoho Inventory configuration — if the customer's Zoho account doesn't have this field, the API may ignore it or error. A comment should document that this is a project-specific custom field.

---

### IMPR-09 — `admin_password` default "change-me-admin-password" has no production enforcement

**File**: `src/core/config.py`, line 61
**Severity**: IMPROVEMENT

**Description**: The `admin_password` and `app_secret_key` have insecure defaults with no runtime enforcement when `is_production=True`. A startup check should raise if production is running with default credentials.

```python
@model_validator(mode="after")
def validate_production_secrets(self) -> Settings:
    if self.is_production:
        if self.app_secret_key == "change-me-in-production":
            raise ValueError("app_secret_key must be changed in production")
        if self.admin_password == "change-me-admin-password":
            raise ValueError("admin_password must be changed in production")
    return self
```

---

## 5. Test Coverage Gaps

---

### TCG-01 — No test for `_ensure_token` lock timeout path

**File**: `tests/test_zoho_sync.py`

The Redis lock wait loop (lines 47–52 of `zoho_inventory.py`) has a 10-second timeout. There is no test for the `RuntimeError("Timeout waiting for Zoho token refresh lock")` path, nor for the case where the lock is held by another worker and the token becomes available during the wait.

---

### TCG-02 — No test for 401 response triggering token refresh and retry

**File**: `tests/test_zoho_sync.py`

The retry logic for 401 responses (lines 117–120 of `zoho_inventory.py`) that deletes the cached token and retries is not tested. This is a critical production path — stale tokens in Redis will trigger this path on every deployment if the token isn't refreshed.

---

### TCG-03 — No test for 429 rate limit backoff

**File**: `tests/test_zoho_sync.py`

The 429 exponential back-off retry (lines 127–129) is untested. A mock that returns 429 on attempt 1 and 200 on attempt 2 would verify this works correctly.

---

### TCG-04 — `test_generate_product_embeddings` does not assert commit is called per batch

**File**: `tests/test_embeddings.py`, lines 66–96

The test asserts `mock_db.commit.called` but not `mock_db.commit.call_count`. With a batch_size of 32 and 2 products, only one commit should occur. The test passes even if commit is called 100 times or not at all after the function returns. Use `assert mock_db.commit.call_count == 1`.

---

### TCG-05 — No test for `index_documents` with missing/malformed markdown files

**File**: No test file exists for `indexer.py`

`index_documents()` in `indexer.py` has no tests at all. The parsing functions `_parse_faq`, `_parse_sales_rules`, `_parse_company_values` are brittle (see IMP-08) and completely untested. At minimum, unit tests with fixture markdown files should verify:
- Empty file returns 0 chunks
- File with correctly formatted sections returns expected chunks
- File with no matching sections returns 0 chunks without errors

---

### TCG-06 — `test_search_products_pipeline` does not test the case where embedding is None for some products

**File**: `tests/test_rag.py`

The search pipeline test uses a mock DB that always returns results. There is no test for the case where `embedding IS NULL` for all products — which (before CRIT-04 is fixed) would result in an unordered result set. After CRIT-04 is fixed, there should be a test confirming that NULL-embedding products are excluded from results.

---

### TCG-07 — No integration test for the full sync → embed → search pipeline

**File**: No test file

The end-to-end flow "Zoho sync → upsert to DB → generate embeddings → vector search returns correct product" is not tested. This is the core value proposition of the system. An integration test using a test database (real or SQLite with pgvector mock) would catch the CRIT-03 conflict target issue, CRIT-04 NULL embedding issue, and IMPR-05 `updated_at` issue automatically.

---

### TCG-08 — Singleton state leaks between tests

**File**: `tests/test_embeddings.py`, lines 31–35

The singleton is correctly reset in `mock_embedding_engine` fixture: `EmbeddingEngine._instance = None` before and after. However, `test_generate_product_embeddings` (line 66) does NOT use the `mock_embedding_engine` fixture and patches `EmbeddingEngine` at the class level instead. If tests run in a certain order, a previously loaded `_instance` from another test could satisfy the `if cls._instance is None` check and bypass the patch entirely, causing test pollution. The fixture's `yield` + teardown reset is the correct approach and should be consistently applied.

---

## 6. Positive Observations

The following aspects of the implementation are done well and reflect good engineering judgment.

**Solid protocol design**: `InventoryProvider` and `VectorStore` in `base.py` are clean, minimal Python `Protocol` definitions. The `ZohoInventoryClient` and `PgVectorStore` correctly implement the protocols. Swapping to Qdrant or a different inventory system requires only a new class, not changes to the consumers.

**Redis-based distributed lock for token refresh**: The `_ensure_token` implementation in `zoho_inventory.py` correctly uses `SET ... NX EX` for distributed locking and double-checks after acquiring the lock (lines 56–59). This is the correct thundering-herd prevention pattern for multi-worker deployments.

**Correct use of PostgreSQL upsert**: Using `INSERT ... ON CONFLICT DO UPDATE` (PostgreSQL `pg_upsert`) instead of SELECT + INSERT/UPDATE is the right choice for high-volume sync jobs. This avoids N+1 round trips and is safe under concurrent access.

**`expire_on_commit=False` on `async_sessionmaker`**: Wait — this is actually NOT set (see IMP-04). Marking this as something to fix, not a positive.

**Pagination in Zoho client**: The `get_items` method with `page` + `has_more_page` loop in `sync.py` handles catalog pagination correctly, including the break condition when `items` is empty as a fallback even if `has_more_page` is incorrect.

**Hybrid search architecture**: The `search_products()` function correctly combines SQL filters (category, price, stock) with vector ordering, which is the right approach for e-commerce — pure vector search without price/stock filters is not useful in a sales context.

**ARQ cron with `unique=True` (default)**: The cron job for sync benefits from ARQ's default `unique=True`, meaning even if multiple workers are running, only one sync job is enqueued per time slot. This is correct.

**Batch embedding to bound memory**: Both `generate_product_embeddings` and `index_documents` process embeddings in batches of 32. This prevents OOM for large catalogs even though the blocking issue (CRIT-01) still needs addressing.

**Clean model separation**: Product, KnowledgeBase, and Base/mixin classes are properly separated. The `UUIDMixin`, `TimestampMixin`, and `Base` pattern is clean and reusable. The `KnowledgeBase` model correctly uses `UniqueConstraint` at the `__table_args__` level for the composite source+title constraint.

**Migration matches model**: The `2026_02_25_0002` migration exactly corresponds to the `UniqueConstraint` in `knowledge_base.py` with the same constraint name `uq_knowledge_base_source_title`. Both `upgrade()` and `downgrade()` are implemented.

**Test fixture for ZohoInventoryClient uses real `httpx.Response`**: Unlike many test suites that mock at too high a level, `test_zoho_client_get_items` constructs a real `httpx.Response(200, json=..., request=...)` and patches only the underlying `client.request` method. This means the actual response parsing code in `get_items()` is exercised by the test.

---

## Appendix: File-by-File Issue Index

| File | Issues |
|---|---|
| `src/integrations/inventory/zoho_inventory.py` | CRIT-02, IMP-01, IMP-02, IMPR-08 |
| `src/integrations/inventory/sync.py` | CRIT-02, CRIT-03, IMP-01, IMP-03, IMP-04, IMP-05, IMP-06, IMPR-05 |
| `src/rag/embeddings.py` | CRIT-01, CRIT-05, IMP-01, IMPR-01 |
| `src/rag/indexer.py` | CRIT-01, CRIT-03, IMP-01, IMP-08, IMP-09, IMPR-04 |
| `src/rag/pipeline.py` | CRIT-01, CRIT-04, IMPR-07 |
| `src/api/v1/products.py` | IMP-01, IMP-07, IMPR-02 |
| `src/worker.py` | IMP-10 |
| `src/models/product.py` | IMPR-05, IMPR-06 |
| `src/models/knowledge_base.py` | (clean) |
| `src/schemas/product.py` | IMP-06, IMPR-02 |
| `src/core/config.py` | IMPR-09 |
| `src/core/database.py` | IMP-04, IMPR-03 |
| `src/integrations/inventory/base.py` | (clean) |
| `src/integrations/vector/base.py` | (clean) |
| `tests/test_embeddings.py` | TCG-04, TCG-08 |
| `tests/test_rag.py` | TCG-06 |
| `tests/test_zoho_sync.py` | TCG-01, TCG-02, TCG-03 |
| `migrations/versions/2026_02_25_0002_*` | (clean) |

---

*Review complete. Priority order for fixes: CRIT-01 → CRIT-04 → CRIT-05 → CRIT-02 → CRIT-03 → IMP-04 → IMP-07 → IMP-03 → remaining IMPs → IMPRs.*
