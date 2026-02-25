# Week 3: LLM Engine + Wazzup + Conversations

## Context

Weeks 1-2 complete: infrastructure, Zoho Inventory sync, RAG pipeline (BGE-M3 + pgvector), 53 tests passing. Week 3 is the core AI layer — the bot must answer WhatsApp messages using LLM with tool calling, receive/send messages via Wazzup, and manage conversations in DB. Milestone: bot answers test questions in WhatsApp on EN/AR.

---

## Step 0: Update All Dependencies to Latest Stable

**Modify**: `pyproject.toml`

Update version ranges to latest stable releases:

| Package | Current | Target | Notes |
|---------|---------|--------|-------|
| `pydantic-ai` | `>=0.1,<1.0` | `>=1.0,<2.0` | Breaking change: v1.0.5 has `OpenRouterProvider`, `OpenAIChatModel` |
| `fastapi` | `>=0.115,<1.0` | `>=0.115,<1.0` | Already good |
| `uvicorn` | `>=0.34,<1.0` | `>=0.34,<1.0` | Already good |
| `sqlalchemy` | `>=2.0.46,<3.0` | `>=2.0,<3.0` | Already good |
| `asyncpg` | `>=0.31,<1.0` | `>=0.31,<1.0` | Already good |
| `alembic` | `>=1.14,<2.0` | `>=1.14,<2.0` | Already good |
| `pgvector` | `>=0.3,<1.0` | `>=0.3,<1.0` | Already good |
| `redis` | `>=5.2,<6.0` | `>=5.2,<7.0` | Widen to include Redis 6.x client |
| `arq` | `>=0.26,<1.0` | `>=0.26,<1.0` | Already good |
| `httpx` | `>=0.28,<1.0` | `>=0.28,<1.0` | Already good |
| `pydantic` | `>=2.10,<3.0` | `>=2.10,<3.0` | Already good |
| `pydantic-settings` | `>=2.7,<3.0` | `>=2.7,<3.0` | Already good |
| `openai` | `>=1.60,<2.0` | `>=1.60,<2.0` | Already good |
| `fastembed` | `>=0.5,<1.0` | `>=0.5,<1.0` | Already good |
| `sqladmin` | `>=0.20,<1.0` | `>=0.20,<1.0` | Already good |

**Key change**: PydanticAI `>=0.1,<1.0` -> `>=1.0,<2.0`. This is the main breaking change affecting the LLM engine implementation. v1.0.5 introduces:
- `OpenRouterProvider` (built-in, no need for `OpenAIProvider` workaround)
- `OpenAIChatModel` (renamed from `OpenAIModel`)
- Stable tool/system_prompt decorator API

After updating pyproject.toml: `pip install -e ".[dev]"` to install updated deps, then run `pytest` to verify nothing breaks in existing code.

---

## Step 1: PII Masking Utility

**New file**: `src/llm/pii.py` (~40 lines)

- `mask_pii(text) -> (masked_text, pii_map)` — regex replace phone/email with `[PII-xxxx]` placeholders
- `unmask_pii(text, pii_map) -> text` — restore originals from map
- Patterns: international phone (`\+?\d{1,4}[\s\-]?...`), email (`[a-zA-Z0-9._%+-]+@...`)
- PII map is `dict[str, str]` (placeholder -> original)

---

## Step 2: Prompt Templates

**Rewrite stub**: `src/llm/prompts.py` (~150 lines)

- `BASE_SYSTEM_PROMPT` constant — Noor identity, anti-hallucination rules ("You are PHYSICALLY UNABLE to see prices. MUST use search_products tool"), language directives, Treejar value proposition
- `STAGE_RULES: dict[str, str]` — per-stage instructions keyed by `SalesStage` value:
  - `greeting` — greet, ask name, introduce Treejar, do NOT recommend products
  - `qualifying` — understand client (role, company, industry), show interest
  - `needs_analysis` — deep dive requirements, "drill and hole" principle, budget/timeline
  - `solution` — MUST use search_products, present multiple options at different price points
  - `company_details` — collect name/company/email for quotation naturally
  - `quoting` — confirm selection, create quotation
  - `closing` — confirm order, discuss delivery/payment, schedule follow-up if not ready
- `build_system_prompt(stage: str, language: str) -> str` — assembles base + stage rules with language instruction

---

## Step 3: Context Window Manager

**New file**: `src/llm/context.py` (~80 lines)

- `MAX_RAW_MESSAGES = 10` (5 user+assistant pairs)
- `build_message_history(db, conversation_id, pii_map) -> list[ModelMessage]`:
  1. Query `Message` table ordered by `created_at ASC`
  2. Convert each to `ModelRequest` (role=user with `UserPromptPart`) or `ModelResponse` (role=assistant with `TextPart`)
  3. Apply PII masking to user message content
  4. If total > `MAX_RAW_MESSAGES`: truncate older, prepend rule-based summary as `SystemPromptPart` (extract customer name, products discussed, key decisions — no LLM call for MVP)
  5. Return last `MAX_RAW_MESSAGES` entries (optionally prefixed with summary)

**PydanticAI message types** (v1.0.5):
```python
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart, SystemPromptPart
```

---

## Step 4: LLM Engine

**Rewrite stub**: `src/llm/engine.py` (~180 lines)

### Agent setup (PydanticAI v1.0.5 API):
```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

model = OpenAIChatModel(
    settings.openrouter_model_main,  # "deepseek/deepseek-chat"
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)
sales_agent = Agent(model=model, deps_type=SalesDeps, retries=2)
```

### Dependencies dataclass:
```python
@dataclass
class SalesDeps:
    db: AsyncSession
    conversation: Conversation
    embedding_engine: EmbeddingEngine
    zoho_inventory: ZohoInventoryClient
    pii_map: dict[str, str]
```

### Dynamic system prompt:
```python
@sales_agent.system_prompt
async def inject_system_prompt(ctx: RunContext[SalesDeps]) -> str:
    return build_system_prompt(
        stage=ctx.deps.conversation.sales_stage,
        language=ctx.deps.conversation.language,
    )
```

### Tools (3):

**search_products** — wraps `rag_search(db, ProductSearchQuery, embedding_engine)`, formats results as text for LLM
**get_stock** — wraps `ZohoInventoryClient.get_stock(sku)`, returns stock/price info
**advance_stage** — validates FSM transition via `ALLOWED_TRANSITIONS` dict, updates `conversation.sales_stage`, flushes to DB

FSM transitions:
```
greeting -> [qualifying]
qualifying -> [needs_analysis]
needs_analysis -> [solution, qualifying]
solution -> [company_details, needs_analysis]
company_details -> [quoting, solution]
quoting -> [closing, solution]
closing -> []
```

### Entry point:
```python
async def process_message(conversation_id: UUID, combined_text: str, db: AsyncSession, redis) -> LLMResponse:
```
1. Load conversation from DB
2. Mask PII in incoming text
3. Build message history from DB (with PII masking)
4. Create `SalesDeps`, run `sales_agent.run(user_prompt=masked_text, deps=deps, message_history=history)`
5. Unmask PII in response
6. Return `LLMResponse(text, tokens_in, tokens_out, cost, model)`

Error handling: try/except around `agent.run()`, fallback message "I apologize, I'm experiencing a temporary issue."

### LLMResponse dataclass:
```python
@dataclass
class LLMResponse:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    cost: float | None
    model: str
```

---

## Step 5: WazzupProvider

**New file**: `src/integrations/messaging/wazzup.py` (~120 lines)

- Implements `MessagingProvider` protocol
- Pattern: follows `ZohoInventoryClient` (httpx.AsyncClient, `_request()` with retry/backoff, `__aenter__`/`__aexit__`)
- Auth: `Authorization: Bearer {api_key}` in headers at client creation (static, not OAuth)
- `send_text(chat_id, text) -> str` — `POST /message` with channelId, chatId, chatType="whatsapp", text
- `send_media(chat_id, url, caption) -> str` — same endpoint with media.url
- `send_template(chat_id, template_name, params) -> str` — template message payload
- `channel_id` set at construction or per-call
- Retry: 3 attempts, exponential backoff on 429/timeout/network

---

## Step 6: Webhook Handler

**Rewrite**: `src/api/v1/webhook.py` (~60 lines)

Flow per incoming message:
1. `Depends(verify_wazzup_webhook)` — HMAC check (skips in dev)
2. **Idempotency**: `SET debounce:{messageId} NX EX 86400` — drop duplicates
3. **Debounce**: append message JSON to Redis list `chat:pending:{chatId}`
4. `SET debounce:chat:{chatId} NX EX 3` — if first in window, enqueue ARQ job with `_defer_by=timedelta(seconds=3)`
5. If not first: `EXPIRE debounce:chat:{chatId} 3` — reset silence timer
6. Return `WazzupWebhookResponse(ok=True)` immediately

### Redis key schema:
| Key | Type | TTL | Purpose |
|-----|------|-----|---------|
| `debounce:{messageId}` | STRING | 24h | Idempotency |
| `debounce:chat:{chatId}` | STRING | 3s | Silence timer |
| `chat:pending:{chatId}` | LIST | none | Accumulated messages |

---

## Step 7: ARQ Worker — process_incoming_batch

**Rewrite**: `src/worker.py` (~170 lines)

### startup/shutdown:
- `startup(ctx)`: store `async_session_factory` in `ctx["db_factory"]`, store `redis_client` in `ctx["redis_client"]`, create `WazzupProvider` in `ctx["wazzup"]`, eagerly load `EmbeddingEngine` model
- `shutdown(ctx)`: close WazzupProvider

### process_incoming_batch(ctx, chat_id, channel_id):
1. Check `debounce:chat:{chatId}` — if still exists, re-enqueue with `_defer_by=3` (silence not elapsed)
2. Drain `chat:pending:{chatId}` atomically (LRANGE + DEL pipeline)
3. Parse messages via `WazzupIncomingMessage.model_validate_json()`
4. Combine text: `"\n".join(m.text for m in messages if m.text)`
5. Find or create `Conversation` by phone (SELECT WHERE phone=chatId AND status!="closed")
6. Save user `Message` records (with `wazzup_message_id`)
7. Call `process_message(conversation_id, combined_text, db, redis)` from LLM engine
8. Save assistant `Message` (with tokens/cost/model)
9. `db.commit()`
10. Send reply via `WazzupProvider.send_text(chat_id, reply_text)` — OUTSIDE transaction
11. On Wazzup send failure: log error, don't re-raise (message saved in DB for manual resend)

### WorkerSettings:
- `functions = [sync_products_from_zoho, process_incoming_batch]`
- `max_jobs = 10` (up from 2 — concurrent chat processing is I/O-bound)

---

## Step 8: Conversations CRUD

**Rewrite**: `src/api/v1/conversations.py` (~100 lines)

### GET / — list with pagination:
- Filters: status, phone (ilike partial match), language
- Count via `select(func.count()).select_from(subquery)`
- Order by `updated_at DESC`
- Return `PaginatedResponse[ConversationRead]`

### GET /{id} — detail with messages:
- `selectinload(Conversation.messages)` for eager loading
- Sort messages by `created_at` in Python
- Return `ConversationDetail` (includes messages list + metadata)

### PATCH /{id} — update:
- `body.model_dump(exclude_unset=True)` — only update provided fields
- Fields: status, sales_stage, customer_name
- Return updated `ConversationRead`

All use `Depends(get_db)` from `src.core.database`.

---

## Step 9: Database Migration

**New migration**: `migrations/versions/XXXX_add_wazzup_message_id_index.py`

```sql
CREATE UNIQUE INDEX ix_messages_wazzup_message_id
    ON messages (wazzup_message_id)
    WHERE wazzup_message_id IS NOT NULL;
```

Partial unique index — allows NULL (assistant messages) while preventing duplicate incoming messages on retry.

---

## Step 10: Update __init__ exports

- `src/llm/__init__.py` — re-export `process_message`, `LLMResponse`

---

## Step 11: Tests

New test files (~600 lines total):
- `tests/test_pii.py` — mask/unmask phone/email, edge cases
- `tests/test_prompts.py` — build_system_prompt for each stage/language
- `tests/test_context.py` — message history building, truncation, PII masking
- `tests/test_llm_engine.py` — process_message with mocked PydanticAI agent
- `tests/test_wazzup_provider.py` — send_text/media/template with mocked httpx
- `tests/test_webhook.py` — idempotency, debouncing, ARQ enqueue
- `tests/test_conversations.py` — list/get/patch CRUD

---

## Implementation Order

```
Step 0:  pyproject.toml deps update + install    (FIRST — pydantic-ai v1.0 needed for engine)
Step 1:  src/llm/pii.py                         (no deps, standalone)
Step 2:  src/llm/prompts.py                      (no deps, constants)
Step 3:  src/llm/context.py                      (depends on models, pii)
Step 4:  src/llm/engine.py                       (depends on all above + pydantic-ai v1.0)
         src/llm/__init__.py                     (re-exports)
Step 5:  src/integrations/messaging/wazzup.py    (no deps on LLM)
Step 6:  migrations/versions/XXXX_...            (DB migration)
Step 7:  src/worker.py                           (depends on engine + wazzup)
Step 8:  src/api/v1/webhook.py                   (depends on worker registration)
Step 9:  src/api/v1/conversations.py             (independent, can parallel)
Step 10: tests/*                                 (after implementation)
```

Step 0 must be first. Steps 1-3 can be parallelized after Step 0. Steps 5, 6, 9 are independent of Steps 1-4.

---

## Key Files to Modify

| File | Action | Est. Lines |
|------|--------|-----------|
| `src/llm/pii.py` | CREATE | ~40 |
| `src/llm/prompts.py` | REWRITE | ~150 |
| `src/llm/context.py` | CREATE | ~80 |
| `src/llm/engine.py` | REWRITE | ~180 |
| `src/llm/__init__.py` | EDIT | ~5 |
| `src/integrations/messaging/wazzup.py` | CREATE | ~120 |
| `src/worker.py` | REWRITE | ~170 |
| `src/api/v1/webhook.py` | REWRITE | ~60 |
| `src/api/v1/conversations.py` | REWRITE | ~100 |
| `migrations/versions/XXXX_...py` | CREATE | ~25 |

### Existing code to reuse:
- `src/rag/pipeline.py:search_products()` and `search_knowledge()` — RAG search (used by LLM tools)
- `src/integrations/inventory/zoho_inventory.py:ZohoInventoryClient` — get_stock, pattern reference
- `src/core/database.py:async_session_factory`, `get_db` — DB session management
- `src/core/redis.py:redis_client` — Redis singleton
- `src/core/security.py:verify_wazzup_webhook` — webhook auth
- `src/rag/embeddings.py:EmbeddingEngine` — singleton for search_products tool
- `src/schemas/common.py:SalesStage`, `Language`, `ConversationStatus` — enums
- `src/schemas/product.py:ProductSearchQuery` — RAG search input
- `src/schemas/webhook.py:WazzupIncomingMessage` — message parsing in worker

---

## Verification

1. **Type check**: `pnpm type-check` (or `mypy src/`)
2. **Lint**: `ruff check src/`
3. **Tests**: `pytest tests/ -v`
4. **Manual test** (with `.env` configured):
   - Start worker: `arq src.worker.WorkerSettings`
   - Start app: `uvicorn src.main:app --reload`
   - Send POST to `/api/v1/webhook/wazzup` with test payload
   - Check Redis keys (`debounce:*`, `chat:pending:*`)
   - Check DB: new conversation + messages created
   - Check worker logs: LLM response generated
5. **Conversations API**:
   - `GET /api/v1/conversations/` — returns paginated list
   - `GET /api/v1/conversations/{id}` — returns detail with messages
   - `PATCH /api/v1/conversations/{id}` — updates fields
6. **CI**: GitHub Actions pipeline passes (ruff + mypy + pytest)
