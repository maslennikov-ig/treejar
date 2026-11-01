# Treejar runtime performance audit (read-only, origin/main @712a905)

Scope: code reading in .worktrees/tj-audit-20261101 plus one local measurement (import time). No live access.
Live context taken into account: handoff says live runs TEST_CHANNEL_RESTORE_MODE=true. In that mode only inbound, quotation_retry, refresh_conversation_summary, the stock jobs and the webhook reconcilers are registered. Quality/follow-up/metrics crons do NOT run live, and embedding warmup is skipped.
tj-1baw note: queue_wait is computed from Wazzup dateTime (chat.py:1106-1118), and that value is truncated to the minute. So the 64 s figure includes up to 60 s of measurement error.

## Measured / certain
- Import cost (local, warm pycache): `import sentence_transformers` 7.3 s / 387 MB RSS; `import src.llm.engine` 6.8 s / 495 MB; `import src.worker` 6.6 s / 511 MB.
- Everything else below is established from code. The latency numbers are estimates unless marked measured.

## Prioritized findings

### P1-1 Worker concurrency: max_jobs=2 shared by customer turns and background jobs
- Evidence: src/worker.py:258 `max_jobs = 2`; one queue for everything (worker.py:132-163). In restore mode these share the 2 slots:
  - refresh_zoho_stock_snapshot: cron at minute set(range(1,60,5)) when delta is not eligible, i.e. a full 12-page Zoho download every 5 min (worker.py:172-180; handoff: delta activation stays off).
  - reconcile_telegram_webhook and reconcile_wazzup_webhook: cron() with no minute, so arq's default second=0 makes them run EVERY MINUTE (worker.py:188-197; arq cron.py:128-146). Each is bounded at 30 s (wazzup_webhook.py:111).
  - refresh_conversation_summary: enqueued after every turn once a conversation has more than 8 messages (chat.py:628-646; conversation_summary.py:72-77). That is one fast-model LLM call per turn (45 s timeout x 2 attempts).
  - Customer turns themselves take about 35-40 s of LLM time each.
- Why it is slow: at minute 1/6/11… three jobs start in the same second. Two parallel tester chats already fill both slots. A third turn waits up to a full turn (~35 s+), and a summary job right after a reply blocks the customer's next message.
- Fix: (a) raise max_jobs to 8-10 (turns are I/O-bound; DB pool is 10+20, Redis pool 20); (b) better: put customer turns on their own queue/worker (arq `queue_name`, `_queue_name=` on enqueue), with crons, summaries and stock on a background worker; (c) give the reconcilers an explicit minute set (e.g. every 5 min) or `second={…}` offsets so they never collide with stock at :x1.
- Size S (a) / M (b). Risk: low; no reply-content change. Watch CPU contention from parallel bge-m3 embeddings (see P1-4).
- Certainty: the mechanism is certain. Its share of the 64 s needs a log of job start times (arq logs "… ●" lines) plus webhook-receipt stamps.

### P1-2 queue_wait metric is wrong, so tj-1baw cannot be measured
- Evidence: chat.py:1106-1118 uses min(message dateTime). The tj-1baw note confirms the minute truncation. On continuation loops (chat.py:1029-1037), and when a superseded reply is re-queued (chat.py:1662-1681), the oldest message also carries the time of the previous LLM run.
- Fix: stamp `received_at=time.time()` into the queued JSON in the webhook (webhook.py:~353 rpush). Compute queue_wait from that stamp. Split it into defer, arq-pickup and lock-wait. Also log the arq job's `enqueue_time` vs start (ctx["enqueue_time"]).
- Size S. Risk: none (telemetry only). Do this first.

### P1-3 Whole LLM re-run when the customer types during generation (superseded reply)
- Evidence: chat.py:1662-1681 (and :375-392). After the full LLM run (~35 s), if new messages are queued and the tools were "supersedable", the reply is thrown away and the loop continues (chat.py:1036). The next iteration runs the full LLM again on all messages.
- Why it is slow: a customer who sends "ok" + "4" 10 s apart pays 2x LLM, about 70 s+. This plausibly explains many 1.5-2 min tester observations.
- Fix: detect new messages DURING generation. Run process_message as a task, poll `LLEN` every ~1 s, and cancel early (only while supersedable tools ran, i.e. no side effects). Alternatively use a short adaptive debounce: extend defer by 2-3 s when a message arrives within N s of the previous one.
- Size M. Risk: behavior change (when replies are merged). Needs owner decision on the debounce value.

### P1-4 Embedding model (BAAI/bge-m3, ~568M params, CPU) on the hot path; cold start in restore mode
- Evidence: config.py:126 `embedding_model = "BAAI/bge-m3"`. Embeddings are computed per turn:
  - FAQ search embeds masked_text (rag/pipeline.py:162).
  - Behavior rules embed THE SAME text again (bot_behavior_rules.py:102-103, called from message_processor.py:1299).
  - Every search_products tool call embeds its query (rag/pipeline.py:117, engine.py:9178).
- Restore mode skips warmup (worker.py:90-94). No HF cache volume in docker-compose.yml, and the model is not baked into the Dockerfile. So after each container recreate, the first turn loads ~2.2 GB of weights, or downloads them if no cache exists. That happens inside the 120 s LLM_TIMEOUT.
- Impact (hypothesis, measure): ~150-500 ms of CPU per embed on a VPS. 2 duplicate embeds plus 1-3 search embeds per turn = 0.5-2 s. The cold first turn after a deploy costs 10 s to minutes.
- Fix: (a) embed masked_text once and pass the vector to both searches. Add a small LRU/Redis cache keyed by sha256(text) for search queries. (b) Warm up even in restore mode, or at least preload weights. (c) Bake the model into the image (`RUN python -c "SentenceTransformer('BAAI/bge-m3')"`) or mount a named volume at HF_HOME, and set HF_HUB_OFFLINE=1. (d) Run FAQ search, the behavior-rule hard query and the CRM lookup concurrently. They currently run serially (message_processor.py:1342-1362, 1265-1317). The DB session is shared, so do only the embedding and the HTTP concurrently with DB work. (e) Longer term: a smaller multilingual model (e.g. multilingual-e5-small / bge-small) or ONNX/int8. That needs re-embedding plus an owner quality check.
- Size S for (a)-(c), M for (d), L for (e). Risk: (a)-(d) none for reply content; (e) changes retrieval quality and needs owner sign-off.

### P1-5 Main-agent cost: reasoning effort "medium" on every agent step, plus up to 3 more full agent runs per turn
- Evidence:
  - safety.py:520-525: core paths on openai/gpt-6-luna get reasoning effort "medium". sales_agent has 12 tools, all sequential=True (engine.py:9071…11307), so every tool round trip is another reasoning call.
  - instructions are rebuilt on every step (engine.py:8915-9066).
  - Extra full agent runs per turn in message_processor.py:989-1096:
    - quotation completion rewrite (:961);
    - catalog-fact repair (:1031), which can retry once more inside _enforce_claim_contract (catalog_planning.py:2642-2700 → retried run_agent);
    - volunteered-claims verify when claim_contract_every_catalog_turn (:1069-1074, catalog_planning.py:2728-2780).
  - Then the repair judge: Terra, 20 s timeout, REPAIR_JUDGE_ATTEMPTS=2 (repair_judge.py:49, 370-380). Worst case it adds 40 s.
  - Each core run has its own 90 s deadline (safety.py:77-87); the outer cap is 120 s (chat.py:84).
- Why it is slow: ~35 s of LLM is consistent with 3-5 reasoning round trips at medium effort. Repair or claim-contract turns roughly double it.
- Fix (owner decision): try effort "low" for core_chat steps (or "low" for intermediate tool-call steps and "medium" only for the final text, via a per-step model_settings hook), and A/B on the eval set. Log per-turn count of run_agent calls, model requests (result.usage().requests) and repair-judge calls. Make REPAIR_JUDGE_ATTEMPTS=1 for timeouts (retry only on non-timeout errors). Consider letting the claim-contract retry fall back deterministically instead of making a third agent run.
- Size S (config) / M (per-step policy). Risk: changes reply quality, so it needs owner approval and an eval round.

### P2-1 Per-turn uncached HTTP calls before the LLM starts
- Wazzup GET /channels on EVERY turn (chat.py:1415-1430 → wazzup.py:428-444). It has no cache, a 30 s timeout and 3 retries with 2/4 s sleeps (wazzup.py:110-156). Typical cost ~0.2-0.6 s, worst case ~90 s. Fix: cache channelId→phone in Redis (TTL 1 h) or in process memory.
- Zoho CRM contact search per turn for customers NOT in CRM. Only positive results are cached (message_processor.py:1127-1145; cache.py). Most leads are new, so they pay ~0.3-2 s of Zoho latency every turn (30 s timeout, zoho_crm.py:78-80), plus OAuth refresh occasionally. Fix: negative cache (e.g. 10-15 min TTL), and run it concurrently with history/RAG.
- New httpx clients per batch: WazzupProvider, ZohoInventoryClient, ZohoCRMClient are created per turn (chat.py:1415, 1590-1591; wazzup.py:108, zoho_inventory.py:551, zoho_crm.py:78). Each turn pays a fresh TLS handshake per host (~50-200 ms each). Also per-call clients at engine.py:3746, wazzup.py:181/227, zoho_*.py token refresh, voxtral.py:175. Fix: process-wide shared clients created in worker startup and closed on shutdown.
- Size S each. Risk: low.

### P2-2 Full Zoho stock snapshot is re-parsed on every stock lookup
- Evidence: get_stock / get_stock_bulk → _stock_snapshot → stock_store.read() does a Redis GET of the whole state, json.loads, a validation loop over every item, and rebuilds the index (zoho_inventory.py:919-942, 1126-1180; stock_state.py:93-155, zoho_inventory.py:224-230). The snapshot holds about 2,400 items including `description` (zoho_inventory.py:78-90; handoff: 2397 rows). It is called per search_products call (engine.py:9201 → catalog_planning.py:4153) and per purchase-selection lookup (engine.py:4193).
- Impact (hypothesis): 1-3 MB of JSON → ~20-80 ms of event-loop-blocking CPU per call, several times per turn. Check with `redis-cli MEMORY USAGE zoho:inventory:stock_state:v2`.
- Fix: keep a per-process parsed snapshot keyed by `generation` (store generation in a tiny separate key, or use GETRANGE/hash). Drop `description` from _STOCK_SNAPSHOT_FIELDS if no reader needs it, or store a HASH by sku and HMGET only the needed SKUs.
- Size M. Risk: low (staleness semantics stay the same if keyed by generation).

### P2-3 Admin customers list loads the whole conversations table + N+1
- Evidence: admin_crm.py:361-407 runs `select(Conversation)` with no LIMIT, loading every row including the `metadata` JSON (runtime evidence, applied rules, etc.). It groups by phone in Python and paginates in Python, then makes 2 queries per page row (_message_summary, :276-294, which loads the full last Message row). list_admin_conversations (:452-477) also does N+1 (2 queries x 20 rows) and returns full `metadata` per row (:325). Conversation detail loads all messages and outbound audits with no limit (:488-519).
- Fix: SQL `DISTINCT ON (phone) … ORDER BY phone, updated_at DESC` (or a window function) with LIMIT/OFFSET and COUNT(DISTINCT phone). Use one aggregated subquery for message count and last message (LATERAL or GROUP BY plus a join on max(created_at)). Use load_only/defer for metadata. Drop `metadata` from list items. Paginate the timeline.
- Size M. Risk: none for customers; the admin UI contract may change (metadata field).

### P2-4 Duplicate-delivery / stranded-message edge: keep_result=3600 + 10 s windowed job ids
- Evidence: webhook.py:362-377 job_id=`wazzup_batch_{ref}_{time//10}`; worker.py:259 keep_result=3600; arq connections.py:158-160 returns None if the job OR its result key exists. If a batch finishes fast inside the same 10 s window (manager message, manual takeover, escalation fallback, bot disabled), a later client message in that window is pushed to Redis but no job is enqueued. It waits until the next message. Not a hot-path cost, but it is an unbounded delay.
- Fix: `func(process_incoming_batch, keep_result=0, …)` (or per-job `_expires`), or add a uuid to job_id while keeping dedup via the lock.
- Size S. Risk: low. Hypothesis-level frequency (needs a test).

### P2-5 Startup cost: bytecode never cached; torch/sentence-transformers imported by the web app
- Evidence: Dockerfile:28 sets PYTHONDONTWRITEBYTECODE=1 with no UV_COMPILE_BYTECODE / compileall, so every container start compiles all imported modules (engine.py alone is 400 KB). The web app imports sentence_transformers at module load through api/v1/router.py → admin_bot_rules/admin_knowledge_base → services → rag/embeddings.py:7. Measured locally: +7.3 s / +387 MB. Admin KB/rule (re)index endpoints then load bge-m3 inside the web container (admin_knowledge_base.py:240-531, admin_bot_rules.py:227-353).
- Fix: `ENV UV_COMPILE_BYTECODE=1` in the deps stage and `python -m compileall -q src` in runtime. Lazily import sentence_transformers inside EmbeddingEngine._get_model. Move admin reindexing to an arq job (worker already has the model).
- Size S. Risk: none.

### P2-6 SPA delivery: no cache headers, no route splitting
- Evidence:
  - /dashboard/assets is StaticFiles with no Cache-Control (main.py:163-167). index.html is a plain FileResponse (main.py:249) with no `no-cache`.
  - nginx has `gzip on` but no gzip_vary, no brotli, no proxy caching, and `gzip_proxied` defaults to off (nginx/nginx.conf). If the outer proxy adds `Via`, nothing is compressed (hypothesis; check with `curl -sI -H 'Accept-Encoding: gzip' https://noor.starec.ai/dashboard/assets/index-*.js`).
  - App.tsx:36-45 imports all 10 views statically (no React.lazy/Suspense anywhere). Charts are used only in OverviewView. GuideView + adminGuideData.ts (1.4k lines) + AcceptanceDemo + i18n (2.3k lines) all ship in the 514 kB main chunk. useMetrics at App level (App.tsx:28, :269) fetches all-time dashboard metrics + timeseries on every SPA load whatever the view.
  - No polling/setInterval found, so there are no refetch storms.
- Fix: `Cache-Control: public, max-age=31536000, immutable` for /dashboard/assets/* (and landing /assets/*), `no-cache` for index.html. React.lazy per view; move useMetrics into OverviewView. Optionally `gzip_vary on; gzip_proxied any;` plus pre-compressed assets.
- Size S. Risk: none.

### P3 items
- P3-1 Current user message sent twice to the model. Messages are committed (chat.py:1521) before build_message_history (context.py:83-160), so the history already contains them, and run_agent passes user_prompt=masked_text again (message_processor.py:626). Costs extra tokens and may confuse the model. Fix: drop trailing user rows that make up the current batch from the history. Owner check, because it is a behavior change.
- P3-2 Repeated per-turn DB config reads with no cache: get_system_config (config.py:209-229) is called for bot_enabled (chat.py:1350), the model name (message_processor.py:277), 3 config reads (:873-907), and webhook grace (inbound_batch.py:84-96, opens a DB session per client message). Prompt components are cached in Redis but only for bytes values (prompts.py:185); that works in the worker (ArqRedis bytes) but always misses with the web redis_client (decode_responses=True). Fix: a 30-60 s in-process TTL cache.
- P3-3 Full catalog scans per turn in some routes: catalog_planning.py:3001-3021, 3860-3886 (load_only, ~2k rows, fine); engine.py:3816-3825 LIKE '%anchor%' with select(Product) loads all columns including the 1024-d embedding. Fix: load_only and a pg_trgm index if this path is frequent.
- P3-4 DB indexes for admin/dashboard filters: no index on messages.created_at (dashboard period filters, dashboard_metrics.py:265-293), conversations.created_at / updated_at (admin list ORDER BY, dashboard period). The LATERAL response-time query scans all user messages for all_time (dashboard_metrics.py:296-314). Low volume today. Add a (conversation_id, role, created_at) index or cache the dashboard for 60 s in Redis.
- P3-5 Dashboard metrics: ~15 sequential aggregates per request with no caching (dashboard_metrics.py:150-428). Add a Redis cache with 60-120 s TTL keyed by period.
- P3-6 pgvector: products and knowledge_base have no ANN index (only bot_behavior_rules has HNSW, migrations 2026_05_08). At ~2k rows exact scan is fine and more accurate, so do NOT add one yet. Note HNSW + WHERE filters may return fewer than LIMIT rows (correctness, not speed).
- P3-7 Docker image: runtime inherits build-essential + libpq-dev (Dockerfile:30-36). Neither is needed at runtime (asyncpg wheels, no psycopg2 in uv.lock), roughly 250-300 MB. The entrypoint's psycopg2-based alembic preflight (scripts/entrypoint.sh) therefore always fails silently (`|| echo 0`). Use a slim runtime stage without build tools, and fix or remove the dead preflight.
- P3-8 Compose: no mem/cpu limits; worker + web both import torch. Postgres runs with untuned defaults. Uvicorn single process (fine at current load). nginx proxy_read_timeout defaults to 60 s, while admin endpoints that call LLMs inline (admin_crm.py:822-931 quality reviews, Terra 60 s x 2 attempts; /reports/generate) can exceed it → 504.
- P3-9 Dead code: _run_customer_facts_layer / LLM fact extractor (engine.py:6621) has no caller, so it costs nothing per turn. Only the import cost remains.
- P3-10 History is bounded (8 msgs / 3000 chars + summary, context.py:32-36), so prompt growth is under control. The system prompt is ~12.5 k chars of static text plus dynamic JSON appended at the end (good for provider prefix caching).

## Top 5 quick wins
1. Stamp webhook receipt time and log arq enqueue→start, so tj-1baw can be measured (S, no risk).
2. Raise max_jobs (e.g. 8) and stop the every-minute reconciler crons colliding with stock at :x1. Next step: a separate customer queue (S/M, no reply change).
3. Cache Wazzup channel phone + negative-cache the Zoho CRM lookup; share httpx clients process-wide (S, no reply change).
4. Embed the turn text once (shared by FAQ + behavior rules), warm up / bake bge-m3 into the image or an HF_HOME volume even in restore mode (S, no reply change).
5. Cache-Control immutable for hashed assets + no-cache for index.html; React.lazy views; UV_COMPILE_BYTECODE + lazy sentence_transformers import (S, no reply change).

Owner decisions needed: reasoning effort for core_chat (P1-5), early cancel/debounce for superseded replies (P1-3), smaller embedding model (P1-4e), duplicate current-message removal (P3-1).
