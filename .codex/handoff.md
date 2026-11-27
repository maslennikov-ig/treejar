# Orchestrator Handoff

Updated: 2026-11-27
Current branch: main (live runtime `f6ed7c6c` + pending `tj-1baw` latency wins)
Current stage id: tj-pdnm (Post-Pilot Stabilization, Optimization & Backlog Consolidation; `tj-pdnm.3`, `tj-pdnm.4`, `tj-pdnm.5` closed)
Status: **LIVE PILOT ACTIVE (`2026-11-27`)** on `https://noor.starec.ai` (`anthropic/claude-sonnet-5.5`, `prose_guards_mode = "trust_model"`, `bot_enabled = true`): autonomous pilot monitor, Nikita QA report, Noor shift report, and `@adt_helper_bot` 1-tap approval daemon run on `80.74.28.160` (`/opt/adt-ops`) over SSH to `noor-server`.

## Master Epic `tj-pdnm` Consolidation (`2026-11-26..27`)
- **Stream 4 (`tj-pdnm.4`) — Closed**: Audited August 2026 pre-pilot eval backlog against live `anthropic/claude-sonnet-5.5` + `prose_guards_mode = "trust_model"`. Closed `tj-vz7o` (13/13 children complete), `tj-wvuk`, `tj-c58g`, `tj-2f1u`, `tj-gwg1`, and `tj-jlx4` as superseded with concrete code/doc evidence, and closed `tj-1786710875876-43-79ae060f` as duplicate of canonical externally blocked GH #54 issue `tj-2pkk`.
- **Stream 3 (`tj-pdnm.3`) — Closed (`f6ed7c6c`)**:
  - `AD-19`: Admin-gated `POST /api/v1/client-self-test/submit` via `Depends(require_admin_session)` on `src/api/v1/client_self_test.py` (`401` unauthenticated, `200` admin).
  - `F12`: Deleted obsolete `.github/workflows/check-logs.yml`, `.github/workflows/set-wazzup-channel.yml`, and `docker-compose.dev.yml`, plus active references in `README.md` and `scripts/orchestration/run_stage_closeout.py`.
  - `AD-10` (backend-only, no UI toggle): Aligned `src/services/chat.py` `_process_batch_inner` `bot_enabled` check to fail closed (matching `src/services/outbound_safety.py`), updated mock `None` -> `True` tests, and added fail-closed unit coverage.
  - `tj-i653`: Verified on live `noor-db-1` (`63/795` conversations had `name_gate_pending_request`, latest `updated_at = 2026-08-09 12:49:32`, `0` in retention window) and removed dead `name_gate` branches/keys/fields (`src/dialogue/state.py`, `src/llm/engine.py`, `src/llm/message_processor.py`) and legacy test fixtures.
  - `tj-ee5f.13.9`: Added stdlib-only `src/llm/model_capabilities.py` (`ModelCapabilities`, `MODEL_CAPABILITIES`, family-prefix matching), validated OpenRouter `vendor/model` IDs + unknown-ID warnings in `src/core/config.py`, and routed `src/llm/safety.py` capability resolution + `provider.require_parameters=True` + deep-merged `provider` dicts through it.
  - `tj-7w8f.5` remains deferred standalone pending provider Bearer credential.
- **Stream 2 (`tj-pdnm.2`) — In Progress (`tj-uvld`, `tj-1baw`)**:
  - `tj-1baw`: Profiled real Nov 19–25 e2e latency via `shadow_webhook_events.created_at` -> `messages.created_at` (`n=97`): subsequent-turn **p50 = 25.7s** (p90 = 33.0s; 15.0s intentional `inbound_quiet_seconds` + ~10.7s processing), Turn-1 **p50 = 169.7s** (p90 = 195.3s due to intentional 180s Dubai working-hours grace; after-hours Turn-1 = 26.1s). Implemented 4 low-risk telemetry/I/O wins: (1) split `quiet_wait` from `arq_queue_wait` in `src/services/chat_latency.py` & `src/services/chat.py` + emit `CHAT_LATENCY_EVENT` on early returns (`voice_fallback`, `escalation_fallback`, `manual_takeover`, `skipped`); (2) batch `_read_turn_config` via `get_system_configs()` in `src/core/config.py`; (3) overlap `_fetch_crm_context()` with `build_message_history()` in `src/llm/message_processor.py`; (4) defer `_enqueue_summary_refresh_if_needed()` until after `_send_deferred_product_media()`.
  - `tj-uvld`: Confirmed `zoho_stock_incremental_enabled = False`, `zoho_stock_coverage_evidence = ""`, and ~4,032 full-mode GETs/day (`288` cycles on Nov 25; `1` HTTP 429 on Nov 24). Authorized read-only `docs/research/2026-10-04-zoho-stock/snapshot-watch.py` run on `noor-server` to collect natural before/after change evidence for AC02.
- **Stream 1 (`tj-pdnm.1`) — OpenRouter funded, awaiting client replies**: Verified live `noor-app-1` OpenRouter top-up on 2026-11-27: `/api/v1/credits` `total_credits = $40.00`, `total_usage = $19.8217` (`$20.18` prepaid remaining); `/api/v1/key` `limit = $30.00`, `limit_remaining = $10.18`. Nov 27 odd shift is funded. Client replies still pending for `hub.starec.ai` phase-1 scope, remaining KB facts, and catalog discrepancies (`LUMA 9786`, `NOVO 2400`, `NOVO 1200`).

## Nov 10–25 Live Pilot History (`tj-r62i` / `tj-pf5x` / `tj-4v2k`) — deployed at `988731df`
- **Nov 25 (`988731df`..`8c2a0e51`)**: OpenRouter key/prepaid dual-endpoint credit monitoring, HTTP 402 spending-rejection acknowledgement + deduplicated Sales follow-up, reseller pricing <20 units, showroom URL sharing, binding recorded budget caps, `disclose_limited_stock` newline/abbreviation/URL fix (`tj-4v2k`), canonical KB template digest safe-sync, Yulya's Nov 21 policies, and multi-row attachment quantity pairing.
- **Nov 1–23 (`tj-id6m`..`tj-9f5e`)**: Full audit remediation (`docs/reports/audit-2026-11-01/README.md`), `anthropic/claude-sonnet-5.5` + `trust_model` + static system `cache_control`, `anthropic/claude-haiku-5.5` vision/PDF reader, `15s` quiet window, Dubai working-hours Turn-1 grace, hybrid `CatalogConcept`/`CatalogFamily` search, Zoho CRM auto-sync, and odd-day router watchdogs.

## Operating Boundary & Recovery
- Production invariants: `TEST_CHANNEL_RESTORE_MODE=true`, approved `0665` test isolation, Wazzup guard enabled, `zoho_stock_incremental_enabled=False`, `warehouse_mutations_allowed=false`. Website `products.is_active`, prices, and embeddings remain owned by catalog sync.
- Rollback for stock delta (if later enabled): unset `ZOHO_STOCK_INCREMENTAL_ENABLED` and `ZOHO_STOCK_COVERAGE_EVIDENCE`, recreate `app` + `worker` only; keep v2/v1 Redis snapshots intact.
- Standing owner rules: never push, deploy, mutate prod/DB/warehouse, or message clients without explicit current authorization; paid second reader (`--second-reader`) stays off (`tj-4q79`).

## Explicit defers
- `tj-7w8f.5`: Wazzup webhook Bearer auth enforcement deferred until provider credential is supplied (`observe` is non-authenticating telemetry only; never `PATCH /v3/webhooks` for `crmKey`).
- `tj-2pkk` (GH #54 `NOVO 1200`), `tj-4kot` (external ~50 req/min Zoho consumer), `tj-zc6k` (Wazzup external callback writer), `tj-ee5f.5`, `tj-gh21`, `tj-bt5p`, `tj-hye`: externally blocked; excluded from autonomous execution.
- `tj-id6m.17` closed 2026-11-26: `AD-19`, `F12`, `AD-10` (backend-only) delivered in `tj-pdnm.3`; `P1-5`, `P1-3`, `P3-1`, `AD-09`, `AD-04`, `AD-10` UI toggle, `AD-12`, `AD-25`, `AD-34` declined/closed.
- `tj-r62i` / `tj-z3hw`: External client router `audit.treejartrading.ae` ownership/eligibility pending for `*6890`, `*0933`, `*0698`, `*9658`, `*2731`.
- `tj-uvld` & `tj-1baw`: AC02 provider coverage / delta activation and live validation of `tj-1baw` telemetry/I/O wins remain open in `tj-pdnm.2`.
- `tj-ierv` / `tj-pdnm.1`: Missing owner facts for return window, warranty terms (incl. SkyLand/`AF 1200`), B2C website pickup, Ali's `chat_id`, catalog dimension conflicts (`LUMA 9786`, `NOVO 2400`), and `hub.starec.ai` phase-1 confirmation.

## Next recommended
Next stage id: tj-pdnm
Recommended action: Verify CI + live production deploy of `tj-1baw` latency wins, monitor the read-only `snapshot-watch.py` observer on `noor-server` for `tj-uvld` AC02, confirm real Nov 27 odd-shift `noor_chat_latency` telemetry, and resume `tj-pdnm.1` items as client answers arrive.

## Starter prompt for next orchestrator
Use $orchestrator-stage for Beads epic `tj-pdnm` (`tj-pdnm.1` / `tj-pdnm.2`). Read `.codex/orchestrator.toml`, `.codex/handoff.md`, and `bd show tj-pdnm` before acting; inspect `snapshot-watch` output on `noor-server` and live `noor_chat_latency` telemetry before any delta activation.

docs-reviewed: updated - `.codex/handoff.md` updated for `tj-pdnm` (`tj-1baw` + OpenRouter `$40` top-up + required orchestrator handoff sections).
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
