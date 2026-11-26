# Orchestrator Handoff

Updated: 2026-11-26
Current branch: main (pending local commit for `tj-pdnm.3` / `tj-pdnm.4`; live runtime `988731df` / `tj-r62i` / `tj-4v2k`)
Current stage id: tj-pdnm (Post-Pilot Stabilization, Optimization & Backlog Consolidation; `tj-pdnm.3`, `tj-pdnm.4`, `tj-pdnm.5` closed locally)
Status: **LIVE PILOT ACTIVE (`2026-11-26`)** on `https://noor.starec.ai` (`anthropic/claude-sonnet-5.5`, `prose_guards_mode = "trust_model"`, `bot_enabled = true`): autonomous pilot monitor, Nikita QA report, Noor shift report, and `@adt_helper_bot` 1-tap approval daemon run on `80.74.28.160` (`/opt/adt-ops`) over SSH to `noor-server`.

## Master Epic `tj-pdnm` Consolidation (`2026-11-26`, local on `main`, awaiting push/deploy)
- **Stream 4 (`tj-pdnm.4`) — Closed**: Audited August 2026 pre-pilot eval backlog against live `anthropic/claude-sonnet-5.5` + `prose_guards_mode = "trust_model"`. Closed `tj-vz7o` (13/13 children complete), `tj-wvuk`, `tj-c58g`, `tj-2f1u`, `tj-gwg1`, and `tj-jlx4` as superseded with concrete code/doc evidence, and closed `tj-1786710875876-43-79ae060f` as duplicate of canonical externally blocked GH #54 issue `tj-2pkk`.
- **Stream 3 (`tj-pdnm.3`) — Closed (ready for push/deploy)**:
  - `AD-19`: Admin-gated `POST /api/v1/client-self-test/submit` via `Depends(require_admin_session)` on `src/api/v1/client_self_test.py` (`401` unauthenticated, `200` admin).
  - `F12`: Deleted obsolete `.github/workflows/check-logs.yml`, `.github/workflows/set-wazzup-channel.yml`, and `docker-compose.dev.yml`, plus active references in `README.md` and `scripts/orchestration/run_stage_closeout.py`.
  - `AD-10` (backend-only, no UI toggle): Aligned `src/services/chat.py` `_process_batch_inner` `bot_enabled` check to fail closed (matching `src/services/outbound_safety.py`), updated mock `None` -> `True` tests, and added fail-closed unit coverage.
  - `tj-i653`: Verified on live `noor-db-1` (`63/795` conversations had `name_gate_pending_request`, latest `updated_at = 2026-08-09 12:49:32`, `0` in retention window) and removed dead `name_gate` branches/keys/fields (`src/dialogue/state.py`, `src/llm/engine.py`, `src/llm/message_processor.py`) and legacy test fixtures.
  - `tj-ee5f.13.9`: Added stdlib-only `src/llm/model_capabilities.py` (`ModelCapabilities`, `MODEL_CAPABILITIES`, family-prefix resolution), validated OpenRouter `vendor/model` IDs + unknown-ID warnings in `src/core/config.py`, and routed `src/llm/safety.py` capability resolution + `provider.require_parameters=True` + deep-merged `provider` dicts through it.
  - `tj-7w8f.5` remains deferred standalone pending provider Bearer credential.
- **Stream 2 (`tj-pdnm.2`) — Read-only diagnostics complete (`tj-uvld`, `tj-1baw`)**:
  - `tj-uvld`: Confirmed `zoho_stock_incremental_enabled = False`, `zoho_stock_coverage_evidence = ""`, and ~4,032 full-mode GETs/day (`288` cycles on Nov 25; `1` HTTP 429 on Nov 24). `docs/research/2026-10-04-zoho-stock/snapshot-watch.py` is strictly read-only (0 OAuth/Redis/warehouse writes) and ready for a bounded `noor-server` observer + Self Client history correlation run on owner approval to close AC02.
  - `tj-1baw`: Profiled real Nov 19–25 e2e latency via `shadow_webhook_events.created_at` -> `messages.created_at` (`n=97`): subsequent-turn **p50 = 25.7s** (p90 = 33.0s; 15.0s intentional `inbound_quiet_seconds` + ~10.7s processing), Turn-1 **p50 = 169.7s** (p90 = 195.3s due to intentional 180s Dubai working-hours grace; after-hours Turn-1 = 26.1s). Reported "71s median" was inflated by Wazzup's minute-truncated `dateTime` + Turn-1 grace. Five low-risk telemetry/I/O wins identified (split `quiet_wait` vs `arq_queue_wait` + early-return `CHAT_LATENCY_EVENT`, short-TTL/batched `SystemConfig` reads, shared `httpx.AsyncClient` pools, parallel CRM/DB context load, deduplicate `_manager_takeover_active` / defer summary enqueue).
- **Stream 1 (`tj-pdnm.1`) — Urgent OpenRouter prepaid alert**: Checked live `noor-app-1` against both OpenRouter endpoints: `/api/v1/credits` shows `total_credits = $20.00`, `total_usage = $19.8217` (**only `$0.1783` prepaid spendable remaining**, while `/api/v1/key` shows `limit = $30.00`, `limit_remaining = $10.1783`). Prepaid top-up has NOT arrived yet and is urgently required before the Nov 27 odd shift. Client replies still pending for `hub.starec.ai` phase-1 scope, remaining KB facts, and catalog discrepancies (`LUMA 9786`, `NOVO 2400`, `NOVO 1200`).

## Nov 10–25 Live Pilot History (`tj-r62i` / `tj-pf5x` / `tj-4v2k`) — deployed at `988731df`
- **Nov 25 (`988731df`, `ff420172`, `d502e0e8`, `eb9edd57`, `8c2a0e51`)**: OpenRouter key/prepaid dual-endpoint credit monitoring, HTTP 402 spending-rejection acknowledgement + deduplicated Sales follow-up (`*4379`, `*1169`), reseller pricing below 20 units (`*4795`), showroom URL sharing, binding recorded budget caps (`*3626`), `disclose_limited_stock` newline/abbreviation/URL fix (`tj-4v2k`), canonical KB template digest safe-sync, Yulya's Nov 21 policies (`SOFA-*` MOQ=1/5d, `AF 1200` dual-motor, post-invoice bank transfer + small-order COD, `@alirezahasheminezhad` marketplace), and multi-row attachment quantity pairing.
- **Nov 14–23 (`tj-9f5e`, `tj-7z88`, `tj-f2sq`, `tj-8e2m`, `tj-uxo1`, `tj-8mtx`, `tj-xnsc`, `tj-y79o`, `tj-cz6j`, `tj-kddn`, `tj-o4qw`, `tj-t6g7`, `tj-k4pc`, `tj-r62i.9`, `tj-32uk`)**: Hybrid `CatalogConcept` / `CatalogFamily` search & reranking, edition/colour-strict media matching, B2B vendor onboarding route, Jebel Ali warehouse/showroom FAQ & tariffs, 20+ unit & custom seating/shape handoff, `Product.zoho_item_id` -> live Zoho SKU bridge, stale `manual_takeover` 2h alert, worker startup canonical KB sync, odd-day router blackout & sticky-lead shadow watchdogs, and Windows native pilot scripts (`scripts/pilot/`).
- **Nov 1–13 (`tj-id6m`, `tj-loge`, `tj-mi4g`, `tj-r62i.3`..`14`)**: Full audit remediation (`docs/reports/audit-2026-11-01/README.md`), switch to `anthropic/claude-sonnet-5.5` + `trust_model` + static system `cache_control`, `anthropic/claude-haiku-5.5` vision/PDF reader, `15s` quiet window, Dubai working-hours Turn-1 grace, and Zoho CRM auto-sync.

## Zoho Stock Sync Boundary (`tj-uvld`, `2026-10-03..04`)
- Implemented gated 600s delta + daily 03:17 UTC full + fresh selected-SKU quotation checks (`25a8c080` live; delta gate OFF, `warehouse_mutations_allowed = false`, `docs/reports/2026-10-04-zoho-stock-sync-optimization.md`, `.codex/stages/tj-uvld-stock-sync/summary.md`).
- EU Self Client read-only access (6 READ scopes, in-memory `<=1h` tokens) is proven (`docs/research/2026-10-04-zoho-stock/`); AC02 causal before/after natural stock change + operation correlation and real 24h delta metrics remain open.

## Operating Boundary & Recovery
- Production invariants: `TEST_CHANNEL_RESTORE_MODE=true`, approved `0665` test isolation, Wazzup guard enabled, `zoho_stock_incremental_enabled=False`. Website `products.is_active`, prices, and embeddings remain owned by catalog sync.
- Rollback for stock delta (if later enabled): unset `ZOHO_STOCK_INCREMENTAL_ENABLED` and `ZOHO_STOCK_COVERAGE_EVIDENCE`, recreate `app` + `worker` only; keep v2/v1 Redis snapshots intact.
- Standing owner rules: never push, deploy, mutate prod/DB/warehouse, or message clients without explicit current authorization; paid second reader (`--second-reader`) stays off (`tj-4q79`).

## Explicit defers
- `tj-7w8f.5`: Wazzup webhook Bearer auth enforcement deferred until provider credential is supplied (`observe` is non-authenticating telemetry only; never `PATCH /v3/webhooks` for `crmKey`).
- `tj-2pkk` (GH #54 `NOVO 1200`), `tj-4kot` (external ~50 req/min Zoho consumer), `tj-zc6k` (Wazzup external callback writer), `tj-ee5f.5`, `tj-gh21`, `tj-bt5p`, `tj-hye`: externally blocked; excluded from autonomous execution.
- `tj-id6m.17` closed 2026-11-26: `AD-19`, `F12`, `AD-10` (backend-only) delivered in `tj-pdnm.3`; `P1-5`, `P1-3`, `P3-1`, `AD-09`, `AD-04`, `AD-10` UI toggle, `AD-12`, `AD-25`, `AD-34` declined/closed.
- `tj-r62i` / `tj-z3hw`: External client router `audit.treejartrading.ae` ownership/eligibility pending for `*6890`, `*0933`, `*0698`, `*9658`, `*2731`.
- `tj-uvld` & `tj-1baw`: AC02 provider coverage / delta activation and low-risk latency optimizations remain open in `tj-pdnm.2`.
- `tj-ierv` / `tj-pdnm.1`: Missing owner facts for return window, warranty terms (incl. SkyLand/`AF 1200`), B2C website pickup, Ali's `chat_id`, catalog dimension conflicts (`LUMA 9786`, `NOVO 2400`), and `hub.starec.ai` phase-1 confirmation.

## Next recommended
Next stage id: tj-pdnm
Recommended action: (1) Follow up urgently on OpenRouter prepaid top-up (`$0.1783` remaining in `/api/v1/credits`) before the Nov 27 odd shift; (2) authorize `git push` + deploy of `tj-pdnm.3` (Stream 3 hygiene/security fixes) and `tj-pdnm.4` (Beads/handoff consolidation); (3) decide whether to launch a bounded read-only `snapshot-watch.py` run on `noor-server` for `tj-uvld` AC02 and implement the 5 low-risk latency/telemetry wins for `tj-1baw`; (4) resume `tj-pdnm.1` items as client answers arrive.

docs-reviewed: updated - `.codex/handoff.md` consolidated for `tj-pdnm` Streams 1-4; `README.md` updated for `F12`.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
