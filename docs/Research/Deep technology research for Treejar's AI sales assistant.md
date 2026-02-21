# Deep technology research for Treejar's AI sales assistant

**No 70–80% ready-made solution exists for this project.** The optimal path is a custom build atop **PydanticAI** (agent orchestration), **Meta WhatsApp Cloud API** (messaging), **Qdrant + BGE-M3** (product search), and **Zoho direct REST APIs** (CRM/inventory), all orchestrated through your confirmed FastAPI stack. This architecture delivers roughly 55–60% infrastructure out of the box via the **benavlabs/FastAPI-boilerplate**, with the remaining 40% being sales-specific domain logic. The single most impactful finding across all 10 research areas: **Wazzup should be replaced with Meta's Cloud API or 360dialog** — Wazzup lacks catalog messages, list messages, WhatsApp Flows, and interactive buttons, which are game-changing features for a B2B conversational commerce bot.

---

## Area 1: No turnkey sales bot framework — build custom

Every existing framework falls short of the 70–80% threshold. **SalesGPT** (GitHub, ~2.4k stars, MIT) provides the closest conceptual match with its sales funnel stage machine (Introduction → Qualification → Value Proposition → Needs Analysis → Solution Presentation → Close), but it's semi-abandoned since mid-2024 with no WhatsApp, CRM, multilingual, or quotation features. **Botpress** (~13k stars) is cloud-first TypeScript — wrong stack entirely. **Rasa** OSS (~19k stars) is in maintenance mode; all innovation requires Rasa Pro at **$35k+/year**. **Chatwoot** (~22k stars, MIT, Ruby/Vue) is actively maintained and valuable as a human agent handoff/inbox layer via its REST APIs, but it's not an AI framework.

Commercial platforms like Kore.ai, Yellow.ai, and WATI target enterprise buyers at $100k+/year or offer too-basic chatbot builders. **WATI** and **Gallabox** both have native Zoho CRM marketplace extensions and could serve as WhatsApp middleware, but their chatbot capabilities are rudimentary compared to what a custom PydanticAI agent delivers. The B2B furniture sales vertical with WhatsApp + AI + Zoho integration is genuinely underserved — no existing SaaS covers it.

| Framework | Stars | Status | Stack fit | Verdict |
|-----------|-------|--------|-----------|---------|
| SalesGPT | 2.4k | Stale (2024) | Python, LangChain | **CONSIDER** as design reference |
| Chatwoot | 22k | Active | Ruby (REST API) | **CONSIDER** for human handoff |
| Botpress | 13k | Active | TypeScript | **SKIP** — wrong stack |
| Rasa OSS | 19k | Maintenance mode | Python | **SKIP** — dead-end |
| WATI/Gallabox | N/A | Active | SaaS | **SKIP** — too basic |

**Recommendation:** Fork SalesGPT's sales stage definitions and prompt templates as architectural reference. Build the agent on PydanticAI + FastAPI. Optionally deploy Chatwoot (Docker, MIT) for human escalation inbox.

---

## Area 2: PydanticAI wins the orchestration layer

For managing multi-stage sales conversations that persist across WhatsApp messages over days and weeks, **PydanticAI** (v1.62.0, Feb 2026, ~15k stars, MIT) is the clear winner. It offers **native first-class OpenRouter support** (`'openrouter:model-name'`), decorator-based tool calling with dependency injection via `RunContext`, Pydantic-validated structured outputs with automatic retry, and full async-first design. Its `pydantic-graph` module provides FSM-style graph nodes with state persistence for modeling sales stages. The "FastAPI feeling" makes it a natural fit for your stack.

The critical pattern for WhatsApp persistence: load `message_history` from PostgreSQL on each incoming message, run `agent.run(user_message, message_history=loaded_history, deps=deps)`, then save `result.all_messages()` back. This requires roughly **20 lines of custom SQLAlchemy code** — trivial compared to LangGraph's heavier ecosystem.

**LangGraph** (v1.0.7+, ~9.5k stars, MIT core) offers the best built-in persistence via `AsyncPostgresSaver` with automatic checkpointing at every node, thread-based conversation management, and purpose-built human-in-the-loop patterns. Its killer feature — conversations that pause indefinitely and resume exactly — is perfect for multi-day WhatsApp workflows. However, it pulls in the entire LangChain ecosystem, has a steeper learning curve, and requires LangChain wrappers for OpenRouter. LangGraph Platform uses **Elastic 2.0 license** (not MIT).

**Burr** (v0.28.0, ~2.1k stars, Apache 2.0, now Apache Incubator) explicitly models conversation stages as state machine nodes with pluggable PostgreSQL/Redis persisters and a self-hosted monitoring UI. It pairs naturally with PydanticAI for LLM calls. However, PydanticAI's own `pydantic-graph` makes Burr somewhat redundant.

| Framework | OpenRouter | State persistence | Tool calling | Async | Verdict |
|-----------|-----------|-------------------|-------------|-------|---------|
| **PydanticAI** | ✅ Native | Via message_history + pydantic-graph | ✅✅ Best (DI, type-safe) | ✅ Native | **USE** |
| **LangGraph** | Via wrapper | ✅✅✅ Best (AsyncPostgresSaver) | ✅ Good | ✅ | **CONSIDER** |
| **Burr** | LLM-agnostic | ✅✅ Excellent (PG/Redis) | N/A (BYO) | ✅ | **CONSIDER** |
| AutoGen/AG2 | Via config | Limited | ✅ | ✅ | **SKIP** — in transition |
| CrewAI | Via LiteLLM | Limited | ✅ | Partial | **SKIP** — wrong paradigm |
| Instructor | Via openai SDK | None | None | ✅ | **SKIP** — subsumed by PydanticAI |
| Mirascope | Via LiteLLM | None | ✅ | ✅ | **SKIP** — no state mgmt |
| Magentic | Via OpenAI base_url | None | ✅ | ✅ | **SKIP** — single maintainer |

**Recommendation:** Use PydanticAI as the primary framework. Build a thin state persistence layer with SQLAlchemy async + PostgreSQL for message history, Redis for session caching. Use `pydantic-graph` for explicit FSM control over sales stages if needed.

---

## Area 3: Qdrant hybrid search with BGE-M3 handles bilingual product retrieval

For ~1,000–1,500 SKUs with bilingual EN/AR queries, the optimal architecture is **Qdrant 1.16.3 hybrid search** (dense + sparse vectors with RRF fusion, payload filtering) powered by **BAAI/bge-m3** embeddings. This avoids the need for a separate search engine.

**BGE-M3** is the decisive embedding choice because it generates both **dense embeddings (1024-d) and sparse vectors in a single forward pass** — no other production model does this. It supports 100+ languages including Arabic via its XLM-RoBERTa backbone, carries an MIT license, and runs on CPU via ONNX/FastEmbed at ~10ms per query. For Gulf Arabic dialect queries, the LLM (via OpenRouter) normalizes Gulf → MSA before embedding, handling the dialect gap elegantly.

Qdrant 1.16.3 (~23k stars, Apache 2.0) provides everything needed in a single system: **hybrid search** via the Query API (prefetch sparse + dense queries, fuse server-side with RRF/DBSF), **payload filtering** on price ranges, categories, brands, stock status during HNSW traversal (not post-filter), **faceting** for category browsing, **sparse vectors** (BM25 via FastEmbed for keyword/SKU matching), and a **Recommendation API** for "similar products." The new ACORN algorithm in v1.16 improves filtered search for complex multi-filter queries.

At 1,500 products, adding Typesense or Meilisearch alongside Qdrant is unnecessary complexity. Meilisearch has excellent Arabic tokenization (via Charabia) but only adds value if you need a sub-50ms instant-search UI with Arabic typo tolerance — irrelevant for a bot interface. **pgvector** performs identically at this scale but lacks hybrid search, sparse vectors, fusion, faceting, and the Recommendation API.

**Concrete search pipeline:** Each user query is first classified by the LLM (SKU lookup → Qdrant payload filter; semantic search → hybrid dense+sparse; filtered browse → filter + vector; comparison → multi-point lookup). Products are stored as single points with bilingual embedding text (`name_en | name_ar | brand | category | description`) and structured payloads indexed on `sku` (keyword), `brand` (keyword), `category` (keyword), `price_usd` (float), `in_stock` (bool). PostgreSQL remains the source of truth, with a sync job pushing updates to Qdrant.

**Estimated performance:** ~5–15ms Qdrant search, ~10ms embedding generation on CPU, ~200–500ms LLM classification. Total ~300–700ms end-to-end, dominated by LLM latency. Infrastructure: Qdrant needs ~512MB RAM for 1,500 × 1,024-d vectors.

---

## Area 4: Direct Zoho REST APIs via httpx beat the official SDK

**Skip the official Zoho Python SDK** (`zohocrmsdk7-0`). It's synchronous only (uses `requests` internally), lists Python support only up to 3.8, and has a verbose nested class hierarchy. For Python 3.13 + FastAPI + httpx 0.28.1, build a **thin async wrapper** (~200–300 lines) against Zoho's REST APIs directly.

**Unified OAuth2 is confirmed working.** A single OAuth2 self-client token can access both CRM and Inventory with combined scopes: `ZohoCRM.modules.ALL,ZohoInventory.salesorders.CREATE,ZohoInventory.items.READ`. Access tokens expire in **1 hour**; refresh tokens are permanent (max 20 per user). For GCC deployment, verify the correct API domain (`zohoapis.com` vs `.eu` vs `.in`) based on the Zoho org's data center.

**Zoho CRM API v8** offers generous rate limits: 50k + (users × 500–2000) credits per 24 hours depending on plan. Most calls cost 1 credit. COQL provides SQL-like queries. **Zoho Inventory API v1** has a simpler 100 req/min/org limit. The critical workflow — create SaleOrder → download PDF — is **two API calls**: POST to create with `template_id`, then GET with `Accept: application/pdf`.

**Zoho Flow** (webhook automation) and **Zoho Catalyst** (serverless functions) are **not suitable** for real-time bot interactions due to latency (5–15 min polling) and GCC data center restrictions. Use them only for background tasks (post-sale email notifications, sync monitoring). **Zoho SalesIQ** can serve as a WhatsApp channel gateway via its webhook-based Zobot, but direct WABA integration provides more control. **Deluge scripts** are useful for supplementary automation inside Zoho (auto-assign leads, send emails on stage change) but are too limited for complex logic (75 function calls max, no external libraries, 10-second timeout).

| Zoho Component | Role | Verdict |
|---------------|------|---------|
| CRM API v8 (direct) | Lead/contact/deal CRUD | **USE** |
| Inventory API v1 (direct) | Stock check, sales orders, PDF | **USE** |
| Unified OAuth2 (self-client) | Single token for all apps | **USE** |
| Custom httpx wrapper | Async API client | **BUILD** (~200 LOC) |
| Flow | Background sync/monitoring | **CONSIDER** |
| Catalyst | Serverless functions | **SKIP** — Python 3.9, DC restrictions |
| SalesIQ | WhatsApp channel | **CONSIDER** — only if avoiding direct WABA |
| Deluge | In-Zoho automation | **CONSIDER** — for simple triggers only |

---

## Area 5: Replace Wazzup with Meta Cloud API — the features gap is critical

This is the highest-impact finding in the entire research. **Wazzup should not be used** for this project. It lacks catalog messages, list messages, WhatsApp Flows, free-form interactive buttons, and typing indicators — features that transform a basic text bot into a full conversational commerce platform.

**Meta WhatsApp Cloud API** provides direct access to every WhatsApp Business feature at zero markup on Meta's per-message rates. The commerce features are substantial: **product catalog messages** (showcase products with images, prices, descriptions within WhatsApp), **multi-product messages** (curated selections of up to 30 items), **cart** (customers build orders without leaving WhatsApp), **WhatsApp Flows** (multi-step forms with text inputs, dropdowns, date pickers — perfect for lead qualification and quotation requests), **list messages** (up to 10 items for category navigation), and **interactive buttons** (up to 3 reply buttons for quick actions). Since July 2025, pricing is per-message, with **all service (customer-initiated) conversations free**. UAE marketing messages cost approximately $0.008–0.012 per message.

**360dialog** (€49/mo, official Meta BSP) mirrors Meta's API surface identically while adding managed hosting, sandbox testing, and 24/7 support. It's the best option if you want slightly less operational burden than going fully direct.

| Gateway | Monthly fee | Msg markup | Interactive messages | Catalogs | Flows | Verdict |
|---------|------------|-----------|---------------------|----------|-------|---------|
| **Meta Cloud API** | $0 | Meta only | ✅ Full | ✅ | ✅ | **USE** |
| **360dialog** | €49–99 | Meta only | ✅ Full | ✅ | ✅ | **USE** (alt) |
| Gupshup | Varies | +$0.001 | ✅ Full | ✅ | ✅ | **CONSIDER** |
| Twilio | $0 | +$0.005–0.01 | ✅ Partial | Limited | Limited | **CONSIDER** |
| **Wazzup** | $30–120 | +Wazzup layer | Template buttons only | ❌ | ❌ | **SKIP** |

**Template for sending quotation PDFs:** Header (document/PDF attachment) + body with dynamic variables (customer name, total, validity) + footer + quick reply buttons ("Confirm Order" / "Request Changes"). Categorize as Utility for lower cost.

---

## Area 6: Zoho native PDF is the simplest quotation path

**Start with Zoho Inventory's native PDF generation** — it requires zero additional dependencies. The workflow is three API calls: create SaleOrder (POST with `template_id` and line items) → download PDF (GET with `Accept: application/pdf`) → send via WhatsApp as document attachment. Templates are customizable through Zoho's visual editor (logo, branding, colors, layout), and non-developers can update them without code deploys.

If Zoho's template customization proves insufficient or Arabic RTL rendering has issues, fall back to **Jinja2 + WeasyPrint** (v68.1, BSD-3, ~100MB Docker deps). WeasyPrint renders Arabic text visually correctly with proper `@font-face` Arabic font embedding and `dir="rtl"` attributes, though it has known issues with text selectability in generated PDFs. Wrap rendering in `asyncio.to_thread()` for FastAPI compatibility.

The nuclear option for pixel-perfect Arabic RTL is **Jinja2 + Playwright** (Apache 2.0), which uses headless Chromium for flawless CSS rendering. The trade-off is ~400–500MB added to your Docker image and 1–3 second rendering latency. **FPDF2** has a critical bug (#901) where RTL multi-line text renders lines in reversed order — a dealbreaker for Arabic quotations. **ReportLab** v4.4.0 introduced experimental Arabic support but the API is explicitly marked unstable. **PandaDoc** and **Proposify** are designed for human-in-the-loop proposal workflows at $41–59/user/month and are overkill for automated bot PDF generation.

| Option | Arabic RTL | Complexity | Extra Docker deps | Verdict |
|--------|-----------|-----------|-------------------|---------|
| **Zoho Inventory PDF** | Good (verify) | Very low | None | **USE** (primary) |
| Jinja2 + WeasyPrint | Partial (visual OK) | Medium | ~100MB | **CONSIDER** (fallback) |
| Jinja2 + Playwright | Perfect | Medium | ~400MB | **CONSIDER** (nuclear) |
| FPDF2 | Broken (bug #901) | High | None | **SKIP** |
| ReportLab | Experimental | High | Minimal | **SKIP** |
| PandaDoc/Proposify | Unknown | Medium | None | **SKIP** ($$$) |

---

## Area 7: Custom LLM judge at $1/week beats every analytics platform

The best approach for automatically scoring conversations on a 15-rule rubric is a **custom LLM-as-a-Judge** via OpenRouter, paired with **Langfuse** for observability. At roughly **$0.001 per conversation** using GPT-4o-mini, scoring 1,000 conversations per week costs approximately **$1.20**. No third-party platform matches this cost-effectiveness or customizability.

The pattern: store complete conversations in PostgreSQL → batch process nightly (or on conversation end) with a structured scoring prompt containing all 15 rules → parse JSON response with per-rule scores (0–10) + reasoning → store in `conversation_scores` table → push scores to Langfuse traces. Weekly reports aggregate via SQL (AVG/MIN/P50 per rule, per agent, week-over-week trends) and render through Jinja2 HTML templates distributed via email or Slack.

**Langfuse** (v3.x, ~19k stars, MIT, self-hosted via Docker Compose) is the observability backbone. Its `@observe()` decorator and drop-in `langfuse.openai` wrapper auto-instrument every LLM call with zero latency impact. It provides trace logging, cost tracking, session grouping (multi-turn WhatsApp conversations), prompt versioning, built-in LLM-as-a-Judge managed evaluators, and a Scores API for attaching rubric scores to traces. Self-hosted Langfuse is completely free.

**DeepEval** (~4k stars, Apache 2.0) provides development-time evaluation with 50+ built-in metrics including **GEval** (custom rubric evaluation with Chain-of-Thought) and `ConversationalTestCase` for multi-turn chat. Use it for regression testing when modifying scoring prompts. **Guardrails AI** (Apache 2.0) complements the scoring pipeline with real-time output validation — preventing hallucinated prices, blocking competitor mentions, and enforcing response format before messages reach customers. Skip Symbl.ai and Observe.ai (voice-call focused, enterprise-priced, less flexible than custom LLM scoring).

---

## Area 8: Google Cloud STT is the only option with Gulf Arabic dialect codes

**Google Cloud Speech-to-Text** is the sole provider offering dedicated locale codes for Gulf Arabic: **ar-AE** (UAE), **ar-SA** (Saudi), **ar-QA** (Qatar), **ar-OM** (Oman). Backed by Google's "Cross-Dialect Arabic Voice Search" research covering these exact markets, it achieves substantially better accuracy on Gulf dialects than any Whisper variant. The Enhanced/Chirp model costs **$0.036/minute**.

For English voice messages, **Groq's Whisper Large V3 Turbo** runs at **164–216× real-time speed** (30-second audio transcribed in under 0.2 seconds) at $0.04/hour — roughly **90% cheaper than OpenAI's Whisper API**. It uses the same Whisper weights, so English quality is identical.

The recommended hybrid architecture: detect language in the first seconds of audio → route Arabic to Google Cloud STT (ar-AE locale) → route English to Groq Whisper Turbo. For 1,000 mixed voice messages per month (average 30 seconds, 70% Arabic / 30% English), total cost is approximately **$12.70/month**. Both services have async Python SDKs.

**Faster-Whisper** (v1.2.1, ~14k stars, MIT) is the optimal self-hosted engine — up to 4× faster than vanilla Whisper with INT8 quantization, Docker-friendly, no FFmpeg dependency. Use it if data sovereignty is required or volume exceeds 500 hours/month. However, Gulf Arabic WER remains **40–55%** out of the box for all Whisper variants. Fine-tuning on Gulf Arabic datasets (MASC) can bring this to ~25–30%.

| Provider | Gulf Arabic quality | Cost/min | Latency (30s) | Verdict |
|----------|-------------------|---------|---------------|---------|
| **Google Cloud STT** (Chirp) | ★★★★★ Dialect-specific | $0.036 | <2s | **USE** (Arabic) |
| **Groq Whisper Turbo** | ★★☆ Generic | $0.0007 | <0.2s | **USE** (English) |
| Faster-Whisper (self-hosted) | ★★☆ → ★★★ fine-tuned | ~$0.001* | 1–3s GPU | **CONSIDER** (self-hosted) |
| OpenAI Whisper API | ★★☆ Generic | $0.006 | 2–5s | **CONSIDER** |
| Deepgram Nova-2 | ★★☆ Tier 2 | $0.0043 | <1s | **CONSIDER** |

---

## Area 9: SQLAdmin + Langfuse + Grafana covers all admin needs in 5 days

The fastest path to a working admin panel follows three layers, deployable within a single week.

**SQLAdmin** (v0.23.0, ~2.6k stars, BSD-3) mounts directly onto FastAPI with `Admin(app, engine)`, supports SQLAlchemy 2.0 async natively, and provides instant CRUD for all models. Custom `BaseView` with `@expose()` decorator enables Jinja2 template-based dashboards and conversation viewers. For a chat conversation viewer, create a custom view rendering messages in chat-bubble format with Chart.js metrics. Authentication is BYOA — implement `AuthenticationBackend` to reuse your JWT system.

**Langfuse** (self-hosted Docker Compose, detailed in Area 7) handles LLM cost tracking, prompt versioning, and trace exploration. **Grafana + Prometheus** (industry-standard, Docker Compose) with `prometheus-fastapi-instrumentator` (3-line setup) provides bot health monitoring, custom metrics (conversations/day, conversion rates, response times), and pre-built FastAPI dashboards.

**Streamlit** (~40k stars) excels for rapid prototyping — build a conversation viewer and metrics dashboard in hours using `st.chat_message` and `st.plotly_chart` — but runs as a separate process and isn't suitable for production multi-user admin. **Chainlit** (~9k stars, Apache 2.0) offers a beautiful chat debugging UI but carries risk: the original team stepped back May 2025, leaving community maintenance. **FastAPI-Admin** requires TortoiseORM (incompatible) and is inactive. **Starlette-Admin** (~700 stars, MIT) has richer widgets (JSON editor, TinyMCE) but a smaller community.

| Phase | Need | Tool | Timeline |
|-------|------|------|----------|
| MVP (Week 1) | CRUD, conversations, prompts | **SQLAdmin** | Day 1–2 |
| MVP (Week 1) | LLM costs, traces, prompt mgmt | **Langfuse** | Day 2–3 |
| Monitoring (Week 2) | Bot health, custom metrics | **Grafana + Prometheus** | Day 4–5 |
| Enhanced (Month 2) | Rich chat viewer, dashboards | SQLAdmin custom views or Streamlit | As needed |

---

## Area 10: benavlabs boilerplate provides 55–60% infrastructure

**benavlabs/FastAPI-boilerplate** (1.8k stars, MIT) is the clear winner for the starting template. It's the only option matching the confirmed stack with **pure SQLAlchemy 2.0 async** (not SQLModel), full Redis integration (caching + ARQ job queue + rate limiting store), Alembic migrations, Pydantic v2, JWT auth with refresh tokens, FastCRUD for pagination, three Docker Compose deployment configs (local/staging/production with NGINX), and API versioning. Python version needs bumping from 3.11 to 3.13, and FastAPI from its current version to 0.129 — both trivial upgrades.

The official `fastapi/full-stack-fastapi-template` (41.3k stars) uses **SQLModel** instead of pure SQLAlchemy 2.0, lacks Redis integration and background jobs, but has excellent deployment patterns (Traefik, CI/CD) worth borrowing. `jonra1993/fastapi-alembic-sqlmodel-async` (1.3k stars) is lower maintenance with SQLModel lock-in and sync Celery.

For the AI layer, **agent-service-toolkit** (JoshuaC215, ~4k stars) provides excellent LangGraph + FastAPI patterns for multi-agent architecture, streaming responses, and content moderation — borrow these patterns for the LLM service layer.

**ARQ** is the correct background job solution for this stack: async-native, Redis-only (matches your stack), simple API with cron support, already integrated in the boilerplate. **Taskiq** (v0.12.1) is a viable alternative with official FastAPI integration and DI reuse. Skip Celery — its sync-first design creates friction with async SQLAlchemy.

**What the boilerplate provides (~55–60%):** JWT auth with token blacklist, SQLAlchemy 2.0 async + Alembic, Redis caching (endpoint + client-side), ARQ worker, rate limiting, FastCRUD + pagination, Docker Compose (3 configs), NGINX, API versioning, pre-commit hooks, pytest.

**What you build (~40–45%):** LLM service layer (PydanticAI + OpenRouter), RAG pipeline (Qdrant + BGE-M3), WhatsApp webhook handler, Zoho API client, conversation persistence, sales FSM, quotation generation, voice transcription, quality scoring pipeline.

---

## Consolidated recommended stack

The table below shows every component, why it beats alternatives, and how they connect.

| Layer | Component | Version | Why it wins | License | Risk |
|-------|-----------|---------|-------------|---------|------|
| **Base framework** | FastAPI + benavlabs boilerplate | 0.129 | 55–60% infra out of box, pure async SA 2.0 | MIT | Low |
| **Agent orchestration** | PydanticAI | 1.62.0 | Native OpenRouter, best tool calling DI, async-first | MIT | Low |
| **Database** | PostgreSQL 17 | 17 | Source of truth, ACID, mature | PostgreSQL | Low |
| **ORM** | SQLAlchemy 2.0 async + Alembic | 2.0.46 | Industry standard, full async | MIT | Low |
| **Cache/queue** | Redis 8.0 + ARQ | 8.0 | Session cache, rate limiting, async job queue | BSD | Low |
| **Vector search** | Qdrant | 1.16.3 | Hybrid search, payload filtering, faceting, recs | Apache 2.0 | Low |
| **Embeddings** | BAAI/bge-m3 via FastEmbed | v2 | Dense + sparse from one model, bilingual EN/AR, MIT | MIT | Low |
| **WhatsApp** | Meta Cloud API (or 360dialog) | v23.0 | Full commerce features, zero markup, all interactive types | N/A | Medium — business verification |
| **CRM** | Zoho CRM API v8 (direct httpx) | v8 | Generous rate limits, unified OAuth, well-documented | N/A | Low |
| **Inventory** | Zoho Inventory API v1 (direct httpx) | v1 | Stock check + SaleOrder + native PDF in 2 calls | N/A | Low |
| **PDF quotations** | Zoho Inventory native PDF | v1 | Zero extra deps, template via UI, 3 API calls total | N/A | Low |
| **PDF fallback** | Jinja2 + WeasyPrint | 68.1 | Full CSS, Arabic visual OK, BSD | BSD | Medium — Arabic text extraction |
| **Voice (Arabic)** | Google Cloud STT (Chirp) | v2 | Only provider with ar-AE/ar-SA/ar-QA/ar-OM locales | Proprietary | Low |
| **Voice (English)** | Groq Whisper Turbo | LV3-Turbo | 216× real-time, $0.04/hr, 90% cheaper than OpenAI | Proprietary | Low |
| **LLM observability** | Langfuse (self-hosted) | v3.x | MIT, Docker Compose, cost tracking, prompt mgmt, scores | MIT | Low |
| **Quality scoring** | Custom LLM judge (GPT-4o-mini) | N/A | $1.20/week for 1k conversations, fully customizable | N/A | Low |
| **Admin panel** | SQLAdmin | 0.23.0 | Native FastAPI mount, SA 2.0 async, custom views | BSD | Low |
| **Monitoring** | Grafana + Prometheus | Latest | Industry standard, 3-line FastAPI integration | Apache 2.0/AGPL | Low |
| **LLM access** | OpenRouter via openai SDK | Latest | Multi-model, single API, cost optimization | N/A | Medium — vendor dependency |
| **Containerization** | Docker Compose v28 | v28 | Already confirmed, all services compose cleanly | Apache 2.0 | Low |

### How they connect

```
Customer (WhatsApp)
    ↕ Meta Cloud API webhooks
FastAPI (benavlabs boilerplate)
    ├─→ PydanticAI Agent (sales FSM via pydantic-graph)
    │       ├─ Tool: Qdrant search (BGE-M3 dense+sparse, payload filters)
    │       ├─ Tool: Zoho CRM (httpx async client, unified OAuth2)
    │       ├─ Tool: Zoho Inventory (stock check, create SO, PDF)
    │       ├─ Tool: Google STT / Groq Whisper (voice → text)
    │       └─ LLM: OpenRouter (Claude/GPT via openai SDK)
    ├─→ PostgreSQL 17 (conversations, products, scores, state)
    ├─→ Redis 8.0 (session cache, rate limits, ARQ queue)
    ├─→ Qdrant 1.16.3 (product vectors, hybrid search)
    ├─→ SQLAdmin (/admin, mounted on same app)
    └─→ ARQ Worker (background: quality scoring, Zoho sync, reports)

Observability:
    Langfuse (self-hosted) ← @observe() decorator on all LLM calls
    Grafana ← Prometheus ← prometheus-fastapi-instrumentator
```

### Dependency count and complexity

The total Python dependency footprint is moderate: **~15 direct dependencies** (FastAPI, SQLAlchemy, Alembic, Pydantic, httpx, pydantic-ai, qdrant-client, fastembed, redis, arq, sqladmin, weasyprint, langfuse, prometheus-fastapi-instrumentator, google-cloud-speech). Docker Compose runs **8 services** (FastAPI app, ARQ worker, PostgreSQL, Redis, Qdrant, Langfuse web+worker+ClickHouse, Prometheus, Grafana). This is manageable for a small team and deploys on a single **8-core / 32GB server** with no GPU required (BGE-M3 runs on CPU via ONNX).

### Anti-patterns to avoid

- **Don't use Wazzup** — it blocks access to WhatsApp's most powerful commerce features
- **Don't use the Zoho Python SDK** — it's synchronous, blocks the event loop, and targets Python ≤3.8
- **Don't add Typesense/Meilisearch** alongside Qdrant at 1,500 SKUs — adds operational complexity for marginal search gain in a bot interface
- **Don't use Celery** with async FastAPI — sync-first design creates blocking issues; use ARQ or Taskiq instead
- **Don't use Rasa OSS** — effectively abandoned for new features; all innovation behind the $35k+ paywall
- **Don't build a custom evaluation platform** — Langfuse (self-hosted, free) + custom LLM judge provides equivalent capability at near-zero cost
- **Don't use FPDF2 for Arabic** — critical RTL multi-line rendering bug (#901) renders lines bottom-to-top
- **Don't use generic Whisper for Gulf Arabic** — 40–55% WER without fine-tuning; Google Cloud STT's dialect-specific models are dramatically better

---

## Conclusion

The research reveals a clear architectural path: **custom-build on PydanticAI + FastAPI, not platform adoption**. No existing framework covers more than 30% of requirements, but the combination of PydanticAI (orchestration), Qdrant + BGE-M3 (bilingual product search), Meta Cloud API (rich WhatsApp commerce), and Zoho direct APIs (CRM/inventory/PDF) delivers a system where each component is best-in-class for its role. The two most consequential decisions are replacing Wazzup with Meta's Cloud API (unlocking catalog messages, Flows, and interactive buttons that fundamentally change the bot's capabilities) and choosing PydanticAI over LangGraph (better OpenRouter support, lighter ecosystem, sufficient state persistence with minimal custom code). Total estimated monthly operational cost for LLM inference, voice transcription, quality scoring, and WhatsApp messaging for a moderate-volume B2B operation is **under $200** — excluding infrastructure hosting. The benavlabs boilerplate saves roughly 6–8 weeks of infrastructure development, letting the team focus immediately on the high-value sales domain logic.