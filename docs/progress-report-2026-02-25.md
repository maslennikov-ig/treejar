# Treejar AI Sales Bot -- Progress Report

**Date:** February 25, 2026
**Version:** 0.2.7+
**Repository:** Private GitHub (`maslennikov-ig/treejar`)
**Status:** Active development -- Week 2 of 6 completed

---

## Executive Summary

Development of the AI-powered sales assistant for Treejar is progressing on schedule. In the first 5 days of active development (Feb 21-25), we have completed the full project foundation (Week 1) and the entire Zoho Inventory integration with the RAG search pipeline (Week 2). The system can now synchronize the full product catalog from Zoho Inventory EU and perform semantic search across products using a multilingual embedding model.

**Key metrics:**

| Metric | Value |
|--------|-------|
| Source code files | 58 Python modules |
| Lines of production code | 2,449 |
| Lines of test code | 1,309 |
| Automated tests | 53 (all passing) |
| Database migrations | 2 |
| API endpoints | 25 |
| Database models | 6 |
| Integration protocols | 4 |
| Documentation files | 30+ |
| Git commits | 28 |
| Code quality gates | ruff + mypy strict + pytest (all green) |

---

## 1. Architecture & Technology Stack

The system is built as a production-grade Python backend with the following stack, chosen for cost efficiency and performance in the MENA B2B market:

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Web framework | FastAPI (async) | High-performance async API, auto-generated OpenAPI docs |
| Database | PostgreSQL + pgvector (Supabase) | Relational data + vector similarity search in one DB |
| ORM | SQLAlchemy 2.0 (async) | Type-safe, modern Python ORM with full async support |
| Migrations | Alembic | Version-controlled schema migrations |
| Vector embeddings | fastembed (BAAI/bge-m3) | Multilingual (EN/AR/RU), runs locally, zero API cost |
| LLM | DeepSeek V3.2 via OpenRouter | $0.27/M input, $1.10/M output -- ~$20-40/mo projected |
| Cache / Queue | Redis + ARQ | Async job queue for background sync, token caching |
| WhatsApp gateway | Wazzup24 API | Certified WhatsApp Business provider |
| CRM | Zoho CRM v7 (EU) | Client's existing CRM system |
| Inventory | Zoho Inventory v1 (EU) | Client's existing inventory system (856+ SKUs) |
| Admin panel | SQLAdmin | Built-in web admin with zero frontend code |
| HTTP client | httpx (async) | Modern async HTTP with connection pooling |

### Architecture Diagram

```
WhatsApp (Wazzup)                Zoho CRM EU
       |                              |
       v                              v
+----------------------------------------------+
|              FastAPI Application              |
|                                               |
|  Webhook  -->  LLM Engine  -->  CRM Client   |
|     |            |    |                       |
|     v            v    v                       |
|  Messages    Products  Knowledge Base         |
|     |            |         |                  |
|     v            v         v                  |
|  PostgreSQL + pgvector (Supabase Cloud)       |
+----------------------------------------------+
       |                              |
       v                              v
  Redis + ARQ                  Zoho Inventory EU
  (job queue)                  (product sync)
```

---

## 2. What Has Been Built (Week 1 + Week 2)

### 2.1. Project Foundation (Week 1) -- COMPLETE

The entire application skeleton was implemented in a single commit, establishing the architecture for all future work:

**6 Database Models** with UUID primary keys, automatic timestamps, and proper constraints:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `Product` | Product catalog from Zoho | SKU, names (EN/AR), price, stock, vector embedding (1024D) |
| `Conversation` | WhatsApp conversation threads | Phone, status, language, sentiment, CRM deal link |
| `Message` | Individual messages in conversations | Role (user/assistant/system), content, token usage |
| `Escalation` | Human handoff tracking | Reason, priority, assigned manager |
| `KnowledgeBase` | FAQ, rules, company values | Source, content, vector embedding (1024D), unique constraint |
| `QualityReview` | AI response quality scoring | Score (0-30), criteria breakdown, reviewer notes |

**4 Integration Protocols** (abstract interfaces) enabling vendor swaps without code changes:

| Protocol | Purpose | Implementation |
|----------|---------|---------------|
| `InventoryProvider` | Product & stock operations | `ZohoInventoryClient` |
| `CRMProvider` | Contact & deal management | (Week 3) |
| `MessagingProvider` | WhatsApp send/receive | (Week 3) |
| `VectorStore` | Embedding search operations | `PgVectorStore` |

**25 REST API Endpoints** organized by domain:

| Group | Endpoints | Description |
|-------|-----------|-------------|
| Products | `GET /`, `POST /search`, `POST /sync` | Catalog, semantic search, sync trigger |
| Conversations | `GET /`, `GET /:id`, `PATCH /:id` | Conversation management |
| Inventory | `GET /stock`, `GET /stock/:sku`, Sale orders | Real-time stock & orders |
| CRM | Contacts CRUD, Deals CRUD | Zoho CRM integration |
| Quality | Reviews CRUD, Reports | AI quality monitoring |
| Admin | Metrics, Prompts, Settings | Admin panel APIs |
| Webhook | `POST /wazzup` | WhatsApp webhook receiver |
| Health | `GET /health` | System health check |

**Pydantic Schemas** for every model with full validation, including:
- Paginated response generic (`PaginatedResponse[T]`)
- Separate Read/Create/Update schemas per model
- Strict field validation (price >= 0, limit 1-50, etc.)

**Infrastructure:**
- Alembic migration system with 2 versioned migrations
- Redis connection management with proper cleanup
- Async database session factory with `expire_on_commit=False`
- `.env`-based configuration with production secrets enforcement
- Comprehensive `.gitignore` (no secrets, no PDFs, no CSV data in repo)

---

### 2.2. Zoho Inventory Integration (Week 2) -- COMPLETE

A production-grade Zoho Inventory connector with enterprise-level reliability:

**`ZohoInventoryClient`** -- Full OAuth2 client (220+ lines):
- OAuth2 token refresh with Redis-based distributed locking (prevents thundering herd)
- Automatic retry with exponential backoff (3 attempts: 2s, 4s)
- Handles 401 (expired token) -- deletes cached token, retries with fresh one
- Handles 429 (rate limit) -- backs off exponentially
- Handles network errors and timeouts -- retries with backoff
- Connection pooling via `httpx.AsyncClient` (single connection pool per job)
- Safe resource cleanup via `async with` context manager (even under task cancellation)
- Concurrent stock lookup with `Semaphore(5)` to respect rate limits
- All EU URLs correctly configured (`zohoapis.eu`, `accounts.zoho.eu`)

**Product Sync Job** -- ARQ background worker:
- Full catalog sync from Zoho Inventory (all pages, 200 items/page)
- PostgreSQL bulk upsert (`INSERT ... ON CONFLICT DO UPDATE`) -- single SQL statement per batch
- Tracks created vs. updated counts via `RETURNING xmax` (PostgreSQL internal)
- Maps Zoho fields to our Product model (SKU, name, price, stock, category, image)
- Automatic `synced_at` and `updated_at` timestamps on every sync
- Errors re-raised to ARQ for automatic retry
- Scheduled via cron: runs every 6 hours (00:00, 06:00, 12:00, 18:00)
- Job timeout: 10 minutes (accommodates catalogs of 856+ SKUs)

---

### 2.3. RAG Pipeline -- Semantic Product Search (Week 2) -- COMPLETE

The core intelligence layer enabling the AI assistant to find products by natural language:

**`EmbeddingEngine`** -- Singleton embedding service:
- Loads BAAI/bge-m3 model (multilingual: English + Arabic + Russian)
- 1024-dimensional vectors for high-quality semantic matching
- Thread-safe lazy loading with double-checked locking (`threading.Lock`)
- Non-blocking async methods (`embed_async`, `embed_batch_async`) via `asyncio.to_thread`
- Batch processing (32 items) to prevent memory spikes on large catalogs
- Zero API cost -- model runs locally via ONNX runtime

**`PgVectorStore`** -- PostgreSQL vector search:
- Hybrid search: vector similarity + SQL filters (category, price range, stock)
- Uses pgvector `<=>` cosine distance operator for nearest-neighbor search
- Filters out products without embeddings (prevents undefined ordering)
- Supports both product search and knowledge base search

**Knowledge Base Indexer** -- Automated document ingestion:
- Parses FAQ (20 Q&A pairs), sales rules (17 bilingual rules), company values (14 values)
- Bilingual content preservation (Russian + English)
- Empty content guard (skips chunks without meaningful text)
- Defensive logging when parsers produce 0 chunks
- `__file__`-relative path resolution (works correctly in Docker/ARQ workers)
- Upsert with unique constraint on `(source, title)` -- safe for repeated runs

---

### 2.4. Code Quality & Testing

Every commit passes a mandatory triple quality gate:

| Check | Tool | Configuration |
|-------|------|--------------|
| Linting | ruff | E, W, F, I, UP, B, SIM, TCH rules enabled |
| Type checking | mypy | `strict = true` with Pydantic plugin |
| Tests | pytest | 53 tests, all async, zero I/O (fully mocked) |

**Test Coverage by Component:**

| Component | Tests | What Is Tested |
|-----------|-------|----------------|
| Zoho OAuth & Token Lock | 4 | Cached token, lock timeout, mid-wait appearance, full refresh |
| Zoho HTTP Retry (401) | 2 | Token refresh on 401, exhausted retries propagation |
| Zoho HTTP Retry (429) | 2 | Exponential backoff timing (2s, 4s), exhausted retries |
| Zoho Sync Job | 2 | Full sync flow, API response handling |
| EmbeddingEngine | 3 | Singleton pattern, single embed, batch embed |
| Embedding Async | 6 | Commit counts per batch, text formatting, None handling |
| Singleton Isolation | 4 | Identity, reset, class-level patch, lazy loading |
| RAG Product Search | 1 | Hybrid search with filters + vector ordering |
| RAG Knowledge Search | 1 | Knowledge base retrieval with embedding |
| Markdown Parsers | 25 | FAQ, sales rules, company values parsing (empty/valid/edge cases) |
| Health Endpoint | 1 | API health check response |
| Index Documents | 2 | Missing docs dir, DB error rollback |

**Security measures implemented:**
- Production secrets enforcement (startup fails if default passwords used in production)
- No hardcoded credentials in source code
- Sensitive files purged from git history
- OAuth token stored in Redis with TTL (auto-expiry)
- Redis distributed lock prevents token refresh races
- Input validation on all API endpoints (Pydantic + Field constraints)

---

## 3. Documentation Prepared

Comprehensive documentation has been produced beyond the code itself:

| Document | Contents |
|----------|----------|
| Technical Specification (tz.md) | Full project requirements |
| Extended Specification (tz-extended.md) | Detailed technical requirements |
| AI Agent Requirements | Behavior rules, personality, escalation logic |
| Sales Dialogue Guidelines | 17 rules with bilingual examples |
| Company Values | 14 values prioritized for AI behavior |
| Dialogue Evaluation Checklist | 15-point quality scoring system |
| Knowledge Base Spec | RAG pipeline specification |
| FAQ | 20 Q&A pairs for the knowledge base |
| Metrics | 17 KPIs for measuring bot performance |
| Architecture Analysis | Deep analysis of 3 architecture variants |
| Technology Research | Comprehensive LLM & framework comparison |
| Code Review Report | 740-line detailed review with 24 issues found & fixed |
| Dialogue Examples | 13 classified real conversations with analysis |
| Sample Quotations | 4 PDF quotation structures analyzed |
| Client Action Items | Tracking of all received materials |

---

## 4. Client Materials Received & Integrated

| # | Material | Status | Integrated Into |
|---|----------|--------|-----------------|
| 1 | Zoho CRM API keys | Received | `.env` configuration |
| 2 | Zoho Inventory API keys + Org ID | Received | `.env` + ZohoInventoryClient |
| 3 | Wazzup API Key | Received | `.env` configuration |
| 4 | Bazara.ae API credentials | Received | `.env` (Week 4) |
| 5 | Sales dialogue rules (17, RU+EN) | Received | Knowledge base indexer |
| 6 | Company values (14 priorities) | Received | Knowledge base indexer |
| 7 | FAQ (20 Q&A) | Received | Knowledge base indexer |
| 8 | Quality evaluation checklist | Received | QualityReview model |
| 9 | Metrics (17 KPIs) | Received | docs/metrics.md |
| 10 | 20 months of statistics | Received | Architecture decisions |
| 11 | 59 dialogue screenshots | Received | Training data analysis |
| 12 | 4 sample quotations (PDF) | Received | Quotation structure spec |
| 13 | Checklist answers (20 questions) | Received | docs/checklist-answers.md |
| 14 | Sales team contacts (7 managers) | Received | Escalation routing |

---

## 5. LLM Strategy: DeepSeek V3.2

After thorough analysis, we selected DeepSeek V3.2 via OpenRouter as the primary LLM:

| Parameter | DeepSeek V3.2 | Claude Haiku (alternative) |
|-----------|---------------|---------------------------|
| Input cost | $0.27/M tokens | $0.25/M tokens |
| Output cost | $1.10/M tokens | $1.25/M tokens |
| Context window | 128K tokens | 200K tokens |
| Projected monthly cost | **$20-40** | **$200-400** |
| Languages | EN/AR/RU excellent | EN/AR/RU excellent |
| Sales dialogue quality | Very strong | Strong |

The 5-10x cost difference is significant for a B2B operation handling hundreds of daily conversations. DeepSeek V3.2 provides excellent multilingual performance at a fraction of the cost. If needed, the model can be switched to any OpenRouter-compatible model with a single environment variable change.

---

## 6. Roadmap & Next Steps

| Week | Scope | Status |
|------|-------|--------|
| **Week 1** | Project skeleton: models, schemas, API stubs, config, migrations | **DONE** |
| **Week 2** | Zoho Inventory sync + RAG pipeline + embeddings + tests | **DONE** |
| **Week 3** | WhatsApp webhook (Wazzup) + Zoho CRM integration + LLM engine | Next |
| **Week 4** | AI sales dialogue logic + quotation generation | Planned |
| **Week 5** | Admin panel + quality monitoring + Telegram alerts | Planned |
| **Week 6** | Load testing, production deployment, handoff | Planned |

**Immediate next steps (Week 3):**
1. Wazzup webhook receiver -- receive WhatsApp messages
2. DeepSeek V3.2 LLM engine -- process messages with context
3. Zoho CRM connector -- create contacts and deals
4. Conversation manager -- maintain dialogue state
5. Response pipeline -- RAG context + LLM generation + quality check

---

## 7. Repository Statistics

```
Language:         Python 3.12
Framework:        FastAPI + SQLAlchemy 2.0 (async)
Source files:     58 modules
Test files:       7 test modules
Production code:  2,449 lines
Test code:        1,309 lines
Migration code:   283 lines
Total:            4,041 lines
Tests:            53 (all passing)
Quality gates:    ruff (linter) + mypy strict (types) + pytest (tests)
CI status:        All green
Git commits:      28
Version:          0.2.7
```

---

*Report generated on February 25, 2026.*
*Noor AI Sales Assistant -- Treejar Office Furniture (Dubai, UAE).*
