# Treejar Full Project Audit — 2026-11-01

- **Audited baseline**: `origin/main` @ `712a905`
- **Audit & delivery branch**: `codex/tj-audit-20261101` (`.worktrees/tj-audit-20261101`)
- **Beads Epic**: `tj-id6m` (`tj-id6m.1` .. `tj-id6m.17`)
- **Baseline gates at audit entry**:
  - `uv run ruff check src/ tests/` — pass
  - `uv run ruff format --check src/ tests/` — pass (445 files)
  - `uv run mypy src/` — pass (198 source files)
  - `uv run pytest tests/` — 4,869 passed, 20 skipped (env-gated live tests)
  - `frontend/admin`: `tsc --noEmit` pass, `npm test` 15/15 pass, `vite build` pass (with >500 kB chunk warning)
- **Post-remediation gates on `codex/tj-audit-20261101` (16/17 tasks closed; `tj-id6m.17` owner decisions open)**:
  - Net diff vs `origin/main`: **-23,705 lines** overall (`+12,446 / -36,151`), **-13,154 lines in `src/`** (`75,500` -> `62,346` LOC, `-17.4%`)
  - `uv run ruff check src/ tests/` & `uv run ruff format --check src/ tests/` — pass (438 files)
  - `uv run mypy src/` — pass (195 source files, 0 errors)
  - `uv run deptry .` — pass (309 files, 0 issues; unused `langgraph` stack removed)
  - `uvx pip-audit` on frozen export — **0 known vulnerabilities** (down from 299 across 35 packages)
  - `uv run pytest tests/` — **4,411 passed, 20 skipped, 0 failed** (including `PINNED_RETRIEVAL_CONTRACT_SHA` and traceability manifests)
  - Web cold import (`import src.main`): **1.21 s** without loading `torch` or `sentence_transformers` (down from ~7.3 s / +387 MB RSS)
  - `frontend/admin`: `tsc --noEmit` pass, `npm test` **16/16** pass, `vite build` entry chunk **57.32 kB** (`16.57 kB` gzip, down from `514 kB`, 0 chunk warnings), `npm audit` **0 vulnerabilities**
  - `frontend/landing`: `npm run lint` pass, `npm run build` pass, `npm audit` **0 vulnerabilities** (down from 22 advisories; 49 packages)

## Detailed Evidence Reports

1. **[Admin Dashboard Wiring Audit](./admin-wiring.md)** — Per-view end-to-end inventory (`App.tsx` -> FastAPI routes -> runtime readers) and 38 prioritized defects (`AD-01` .. `AD-38`).
2. **[Runtime Performance Audit](./performance.md)** — Customer chat hot path, ARQ worker concurrency, `bge-m3` embeddings, Zoho stock snapshot parsing, DB query patterns, SPA delivery, and Docker startup (`P1-1` .. `P3-10`).
3. **[Legacy, Dead Code & Repo Hygiene Audit](./legacy-dead-code.md)** — Vulture + AST reachability analysis across 75,500 LOC in `src/`, config drift, helper duplication, stale scripts, and test-only legacy layers (`F1` .. `F14`).

## Executive Summary by Domain

### 1. Security & Dependencies (`tj-id6m.1`, `tj-id6m.16`)
- **Critical path traversal (`AD-01` / `tj-id6m.1`)**: Public routes `/client-self-test/{full_path:path}` and `/{full_path:path}` in `src/main.py` joined raw paths onto `dist_dir` without `os.path.realpath` containment, allowing encoded `..` (`%2F`, `%2E%2E`) to read arbitrary readable files outside `dist`. Fixed in `0afc09f` with `_serve_spa_file` containment + parametrized regression tests.
- **Dependency vulnerabilities (`tj-id6m.16`)**:
  - `frontend/landing` carried unused AI Studio boilerplate dependencies (`@google/genai`, `better-sqlite3`, `express`, `dotenv`, `tsx`) with 22 npm advisories (2 critical, 10 high). Cleaned to 49 total packages and 0 advisories.
  - `frontend/admin` `vite` 8.0.16 had 3 high dev-server advisories; upgraded to `vite` 8.3.5 (0 advisories).
  - Python `uv.lock` carried 299 advisories across 35 packages (`urllib3`, `weasyprint`, `cryptography`, `pyjwt`, `starlette`, `requests`, `aiohttp`, `pillow`, `python-multipart`, `authlib`, `transformers`, `setuptools`, `torch`, etc.) plus the unused `langgraph` stack; removed `langgraph` and upgraded `uv.lock` to **0 advisories** and **0 `deptry` issues** (`ed34a91`).

### 2. Admin Dashboard Wiring (`tj-id6m.2` .. `tj-id6m.7`)
- **Authentication**: All `/api/v1/admin/*` routers enforce `Depends(require_admin_session)`.
- **Broken / misleading UI & API wiring**:
  - `AD-02`: Infinite refetch loop in `QueuesQualityView` after clicking header Refresh (`managerQa` hook returned a non-memoized object in `useEffect` deps).
  - `AD-03`: Escalations `"All"` filter sent `status=all`, which backend matched literally (`Escalation.status == 'all'`), always returning empty.
  - `AD-04`: CRM drawer `PATCH /crm/conversations/{id}` overwrote all 5 fields from a potentially stale snapshot without enum validation.
  - `AD-05`: AI Quality model dropdown hard-coded legacy models (`gemini-3.1-flash-lite`, `gpt-5.4-mini`, `glm5-20260211`), omitting active backend default `openai/gpt-6.1-terra` and `z-ai/glm-5.2`.
  - `AD-06`: Bot-rule `scope` (`global`/`stage`/`language`/`segment`/`conversation`) was a dead switch — runtime only checked nullable columns, causing `conversation` or empty-condition rules to apply **globally**.
  - `AD-07` & `AD-08`: Canonical rule badge matched stale hard-coded titles (always showing `"Manual"`), and Bot QA 15-criterion rubric drawer was mock text contradicting `src/quality/evaluator.py`.
  - `AD-10`..`AD-17`: `bool("false") == True` bug on `SystemConfig` string values, dead `/settings/` fields (`default_language`, `follow_up_enabled`, `max_messages_per_conversation`), missing `AdminAuditLog` entries on 8 mutation endpoints, `/system/health` swallowing DB exceptions as healthy, placeholder zero counts on async product sync enqueue, and writable SQLAdmin views bypassing embeddings/soft-delete/audit.
  - `AD-18`: `/crm/customers` loaded the entire `conversations` table (with JSON `metadata`) into Python for grouping/pagination plus `2 * N` message queries per page.

### 3. Speed & Runtime Efficiency (`tj-id6m.8` .. `tj-id6m.12`)
- **Worker slot starvation (`P1-1`)**: `WorkerSettings.max_jobs = 2` shared one queue across 35–40s customer LLM turns, 5-minute Zoho full stock refreshes, summary LLM jobs, and two webhook reconcilers accidentally running **every minute** (`cron()` with `minute=None`).
- **Inflated `queue_wait` telemetry (`P1-2` / `tj-1baw`)**: Computed from minute-truncated Wazzup `dateTime` (adding up to 60s of phantom latency). Fixed by stamping `received_at` at webhook `rpush` and recording ARQ `enqueue_time -> start`.
- **Stranded batch edge case (`P2-4`)**: 10s-windowed `wazzup_batch_{ref}_{ts//10}` job IDs combined with `keep_result = 3600` caused ARQ to skip scheduling a second message arriving in the same 10s window if an earlier batch finished fast.
- **Per-turn redundant work (`P1-4`, `P2-1`, `P2-2`)**: Uncached `GET /channels` to Wazzup on every turn, uncached negative Zoho CRM contact lookups, duplicate `BAAI/bge-m3` CPU embeddings of identical `masked_text` (FAQ + behavior rules), and full 2,400-item Zoho stock JSON re-parse + index rebuild on every SKU lookup.
- **Startup, Docker & SPA delivery (`P2-5`, `P2-6`, `P3-7`)**: Web process eagerly imported `sentence_transformers`/`torch` (+7.3 s, +387 MB RSS); `Dockerfile` shipped `build-essential`/`libpq-dev` and 403 `docs/` files (6.8 MB) in runtime without bytecode compilation; `docker-compose.yml` lacked a persistent HuggingFace cache volume; admin SPA lacked route-level `React.lazy` splitting and `Cache-Control` headers.

### 4. Legacy & Dead Code (`tj-id6m.13` .. `tj-id6m.15`)
- **~11,530 lines of unreachable `src/` functions/classes** once never-invoked compatibility shims are cut:
  - `F1`: Never-invoked `order_quote_route` (`src/llm/order_quote_routes.py`, 1,180 lines) and `_pending_reference_route_for_turn` adapters (`message_processor.py` docstring: *"accepted only for API compatibility and are never invoked"*).
  - `F2`: Disconnected LangGraph `run_dialogue_kernel` (`src/dialogue/runner.py`) + no-op `record_legacy_route` + unread `dialogue_kernel_*` settings (leaving `langgraph` with zero runtime importers).
  - `F3`: Unreachable `_run_customer_facts_layer` + `extract_customer_facts` fast-extractor chain + unread `customer_facts_*` flags.
  - `F4`–`F6`: Unreachable `_turn_runtime_directives` consultation directives, dead `verified_answers` policy functions, dead `catalog_planning` planners.
  - `F7`–`F10`, `F12`, `F13`: Zero-reference helpers (`PgVectorStore` + `src/integrations/vector/`, `src/core/security.py`, `src/rag/indexer.py`, `run_payment_reminders` wrapper, dead schemas, unread settings, duplicate docs, 9 stale one-off scripts) and duplicated Zoho OAuth / text-normalization helpers.

## Open Product & Operational Decisions (`tj-id6m.17`)

Items intentionally NOT changed autonomously because they alter customer-facing behavior, operator authority, or repo operational policy:

1. **LLM reasoning effort & extra agent runs (`P1-5`)**: Whether to test `reasoning_effort="low"` on intermediate tool steps / cap repair retries to cut ~35s LLM turn latency (requires benchmark round).
2. **Overlapping customer messages (`P1-3`)**: Whether to cancel in-flight supersedable LLM runs early when a new message lands in Redis or extend adaptive debounce.
3. **Duplicate current message in prompt (`P3-1`)**: Current batch messages are committed before `build_message_history` and also passed as `user_prompt`. Removing the duplicate saves tokens but alters prompt shape.
4. **Conversation `paused` / `closed` status (`AD-09`)**: Should setting status to `paused`/`closed` in CRM drawer halt Noor replies, or is status purely reporting/follow-up metadata?
5. **CRM drawer `escalation_status` editing (`AD-04`)**: May operators manually change `escalation_status` in the CRM card (syncing `Escalation` rows), or should escalation transitions happen exclusively via Escalate / Close Escalation actions?
6. **Dashboard kill-switch & `bot_enabled` default (`AD-10`)**: Missing `bot_enabled` row means enabled in `chat.py` (`default="true"`) vs blocked in `outbound_safety.py`; also whether to expose `bot_enabled` / `telegram_test_mode_enabled` toggles in Settings UI.
7. **Payment reminders UI & `"manual"` mode (`AD-12`)**: Whether to expose `payment_reminder_controls` in Settings UI and wire or drop `"manual"` mode.
8. **Public `/api/v1/client-self-test/submit` (`AD-19`)**: Keep public (with rate limit / token) or retire now that client self-test rounds finished.
9. **KB `language` filtering (`AD-25`) & `"target"` conversation definition (`AD-34`)**: Whether `search_knowledge` should filter by KB entry `language`, and what `target_only` should match (`'completed'` is not a valid `ConversationStatus`).
10. **One-time GitHub workflows (`F12`)**: Confirm deleting `.github/workflows/check-logs.yml` and `set-wazzup-channel.yml` and legacy `docker-compose.dev.yml`.
