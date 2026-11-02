# Orchestrator Handoff

## Epic tj-id6m (2026-11-01..02): Full project audit & remediation — CLOSED & DEPLOYED (`93013c9` / `580116a`)
- Full audit + 17 closed remediation slices (`tj-id6m.1`..`tj-id6m.16`, `tj-id6m.18`) merged to `main` (`d7eb8ea`, `93013c9`, `580116a`) and deployed to `https://noor.starec.ai` via GitHub Actions CI/Deploy runs `41330430678` & `41397449530` (`docs/reports/audit-2026-11-01/README.md`). Fixed SPA path traversal (`HTTP 400`, `tj-id6m.1`), 30+ Admin UI/BE wiring bugs (`tj-id6m.2`..`tj-id6m.6`), SQL pagination/indexes (`2026_11_01_admin_ts_indexes`) + 60s dashboard cache (`tj-id6m.7`), ARQ concurrency `max_jobs=8` + staggered crons + server-side `queue_wait` (`tj-id6m.8`), channel/CRM negative/turn-embedding caches + stock digest memoization (`tj-id6m.9`, `tj-id6m.10`), slim runtime `Dockerfile` + lazy web `torch` startup (`libtorch` absent from PID 1) + `React.lazy` SPA splitting + immutable asset headers (`tj-id6m.11`, `tj-id6m.12`), `-13,154` net `src/` LOC of dead layers/helpers (`tj-id6m.13`..`tj-id6m.15`), `0` advisories across Python/FE (`tj-id6m.16`), and Arabic `opening_guard` transliteration + `result.usage` property + `24/24` green `bot_test_suite.py` (`tj-id6m.18`). Optional product choices deferred in `tj-id6m.17`; expired VPS `ZOHO_CRM_REFRESH_TOKEN` reissue tracked in `tj-tjum`.

## Stages tj-fsfx, tj-myx7 & tj-p82s (2026-10-26): Admin Dashboard controls/session/filter sweep, Month default period, full 14-step onboarding & v3 client portal guide
- Combined `codex/tj-myx7-admin-controls` + `codex/tj-p82s-dashboard-period` (`f2d040d`, live via CI `40325698749`) and expanded Viktor's portal guide in `tj-fsfx` (`.codex/stages/tj-fsfx/summary.md`, `.codex/stages/tj-myx7/summary.md`, `.codex/stages/tj-p82s/summary.md`). Added `GET /api/v1/admin/session` account/logout menu with per-admin audit actor attribution, exact deal/target/escalation drilldowns, Overview default `month` period with `localStorage` persistence, 14-step tour + 9-playbook guide, and republished client manual v3 (`https://aidevteam.ru/a/GaZJfnrjnN5VKtU2wLJdu1nFlqJq3xYO`).

## Stages tj-4kba / tj-j3zg / tj-lk87 / tj-ierv (2026-10-23..26) & October tester feedback `tj-i2b1` (2026-10-14) — deployed
- Admin login & UX summaries: `.codex/stages/tj-4kba/summary.md`, `.codex/stages/tj-j3zg/summary.md`, `.codex/stages/tj-lk87/summary.md`, `.codex/stages/tj-ierv/summary.md` (live on `main` / `https://noor.starec.ai`).
- Accepted `tj-i2b1` (`a72da15` / `4b032c7` / `6d4663f`, live): retained named model/finish/unit constraints, multi-unit quantity recovery, literal refusal persistence, and structured catalog photos (`docs/reports/2026-10-13-tester-feedback-fixes.md`, `docs/reports/2026-10-14-tester-epic-completion-delivery.md`).

## Wazzup webhook protection — deployed 2026-10-13

- `tj-vqcc`guard retained in livea72da15. CI38549111605 and postdeploy readback
  pass; original guard CI38425819094/4470/27 remains historical proof.
- Startup/minute checks and controlled real-provider repair passed; the real
  callback was never diverted. Test0665 and protected settings retained.
- Runbook `docs/ops/wazzup-webhook-guard.md`; deployment/rollback receipt
  `docs/reports/2026-10-13-wazzup-webhook-guard-delivery.md`.
- Fresh owner...0921 coffee-table message processed at17:17UTC, text accepted
  by Wazzup201 and owner-confirmed received. Callback/settings stable17:26UTC;
  `tj-vqcc` closed. Independent photo defect belongs to `tj-i2b1.4` above.
- Writer identity remainsUNKNOWN:14Oct GETs show Noor then audit again while
  cron reportsrestored;14Oct10:41GETagainaudit. tj-zc6kblocked: no account/audit access;
  provider-side owner action: `docs/ops/wazzup-callback-owner-action-20261014.md`.

Updated: 2026-10-04
Current branch: codex/tj-uvld-stock-sync
Current stage id: tj-uvld-stock-sync
Status: full release verified;4458 passed,20 gated skips; Ruff/mypy/process passed.
Delivery: owner authorized Push, Merge, Deploy2026-10-03; delivery completed, CI37130777663 passed.

## Current work

- tj-199k delivered: helpers Luna, repair/QA Terra; live 0f17419 / CI 41232988824 (4862 passed,27 skipped + pgvector1). App+worker readback preserves main Sol, voice/search, disabled/channel/audit gates; only FAST ENV and 3 QA model fields changed. Report/rollback: docs/reports/2026-10-31-noor-helper-model-migration.md.
- tj-3jcn delivered: main DB-backed chat is openai/gpt-6.1-sol / medium in app+worker, live 6df11eb, CI 41229254700 (4858 passed / 27 skipped + pgvector 1). Two paid SDK/tool-cycle POSTs cost USD0.001346 of USD0.10. ENV/helpers/channel gates unchanged; private rollback /opt/noor/.hotfix-backups/tj-3jcn-sol-20261031T181216Z. Evidence: docs/reports/2026-10-31-noor-pilot-and-model-readiness.md and sol-provider/runtime receipts.
- Client pilot choices v2: https://aidevteam.ru/a/S1zQSadyVtJDNCkX2FO10BMX2c2ODIk0 ; prompt docs/prompts/2026-10-31-customer-claude-noor-pilot.md. Pilot requires choices, shared egress ownership and channel/restore-mode agreement. Preserve the audit receiver/disabled guard; test0665 qridle, business9235 active; no customer sends or pilot activation performed.

- Beads tj-uvld owns AC01–AC12 and remains in_progress until provider coverage,
  delta activation and real 24h optimized measurement are accepted.
- Worktree: /home/me/code/treejar/.worktrees/tj-uvld-stock-sync.
- Base: main 36c86137a51d2e6485db92c28ec057fe26f03339; prepared docs and
  tj-4kot cooldown07591b8 reused by cherry-pick. Primary dirty work preserved.
- Installed: gated 600s delta + daily03:17UTC full, owned lock/CAS generations,
  48h retention with1h customer ceiling, selected-SKU fresh quotation checks,
  shared HTTP counters and read concurrency/cooldown.
- Owner decision: stock2 vs agreed5 stops quotation, states only2 available,
  and awaits a new customer decision. Consent becomes deferred; unchanged
  shortage state cannot trigger another automatic/background creation.
- Source observation and successful dataset coverage are distinct. Multi-page
  delta requires two identical complete reads; changed pages abort publication.
  This safeguard does not establish provider paging/operation completeness.
- Stock source unchanged in live app+workera72da15 after authorized tester
  delivery. Stock-stage4451/27CI and4458/20local are historical; current full
  canonicalCI4712/27passed. Delta gate remains off.
- .env/safety fingerprints unchanged; DB/Redis/nginx containers retained.
- New v2/legacy:2557 rows,48h TTL. UTC[14:50:52,14:53:10):
 13GET/13HTTP200,1successful full cycle; not optimized24h evidence.
- Delivery receipt:docs/reports/2026-10-03-zoho-stock-sync-delivery.md.
- Latest report: docs/reports/2026-10-04-zoho-stock-sync-optimization.md.
- Implementation report: docs/reports/2026-10-03-zoho-stock-sync-optimization.md.
- Stage: .codex/stages/tj-uvld-stock-sync/summary.md.

## Provider evidence and eligibility

- Owner2026-10-04: working organization only, no warehouse mutations.
- Fresh live readback24checks passed, runtime25a8c080 unchanged.
  UTC[03Oct14:50:52,04Oct06:00:00):2019 attempts,2015HTTP200,4HTTP429/minute,
 155successful full cycles/4failed/23local cooldown skips;15h9m8s, not optimized24h.
- Read-only history probe04Oct:5GET,4HTTP200+1HTTP401 at inventoryadjustments;
 stopped without OAuth refresh/retry/access changes.9 returned item timestamps
 precede last24h query boundary; filter/field semantics unproved, no causal
 missed-operation inference. Coverage gate stays closed. Receipts:
 docs/research/2026-10-04-zoho-stock/.

- Access follow-up10:06UTC: one cached-token GET returned401/code57
  (not_authorized); stopped, no refresh/retry. Scope history suggests missing
  history READ grants; role/grant distinction is not proven by cached TTL.
- Read-only access resolved without owner console action: existing EU Self
  Client client_credentials produced <=1h tokens for six exact READ scopes;
  no refresh tokens, production token replacement, env/Redis or warehouse write.
  10:59/11:03/11:19UTC:3OAuthPOST200 +17InventoryGET200, no retries.
  Validated adjustment/receive/return/transfer history samples available.
  Packages response shape remains unverified, not inferred empty.
  Executed source hashes and safe receipts: research README above.
- Applied quantity adjustment04Oct06:12UTC contains selected line +10;
  matched current item stock24, item timestamp16Sep12:46UTC. No observed
  old quantity or complete delta membership; this does not certify coverage.
  Current docs do not guarantee stock-only changes advance item timestamps.
 21offline Self Client guards passed; old17grant/6audit checks retained.
  Archived localhost server-based helper is not a client/Viktor instruction.
- Bounded natural quantity observer started04Oct11:48:19UTC, deadline05Oct
 11:48:19UTC (14:48MSK). Initial full11:46UTC:2397 numeric-stock rows;
 unknown quantities are excluded, never zero. Snapshot Redis GET only until
 first quantity change; then <=16 cached-token InventoryGET, no OAuth/retry/
 writes. Stops after one comparison or24h. Startup/source-bound receipt and
13offline observer guards: research snapshot-watch-* files. Local SSHPID71170;
 private runtime directory is in snapshot-watch-launch.json. Observer output
 still needs root reading; no automatic chat callback or delta activation.

- 2026-10-03 read-only probes, bulk/paging limits and catalog mapping:
  docs/research/2026-10-03-zoho-stock/ (delta activation stays off).

## Operating boundary

- Livea72da15, TEST_CHANNEL_RESTORE_MODE=true; protected app/worker safety
  fingerprints equal predeploy. Approved0665 sender/allowlist and Telegram
  phone isolation unchanged. Owner-authorized Wazzup guard flag is now true;
  guard repeatedly restores callback; provider subscription flags unchanged.
- Current owner authority covers tj-uvld push/merge/deploy with delta gate off.
- Warehouse mutations are explicitly excluded by current owner instruction.
  Requested diagnostic access uses existing EU Self Client, six exact READ
  scopes, <=1h access tokens only in app memory. Existing shared Inventory/
  CRM client configuration, refresh/cached tokens and production env preserved.
  Permanent reauthorization/revocation, permissions changes and real messages
  still require separate approval.
  Stock investigation used no paid model reader/calls.
- Website products.is_active, catalog prices and embeddings remain owned by
  their existing sync; stock state never writes those fields.

## Recovery

- Disable ZOHO_STOCK_INCREMENTAL_ENABLED and clear the coverage evidence in
  app+worker environment, recreate only app+worker under approved delivery.
  Proven five-minute full mode remains available; this restores higher API use.
- Keep v2 state and the last-full v1 snapshot; do not flush Redis/ARQ/customer
  data. Previous binary reads original v1 as_of with its one-hour ceiling.
- Rollback/deployment commands and measurement packet are in the current report.
- Preserve unrelated environment, live DB, queued/held messages and test0665.

## Explicit defers

- tj-tjum: `ZOHO_CRM_REFRESH_TOKEN` in `/opt/noor/.env` returns `invalid_credentials` from `accounts.zoho.eu` (while `ZOHO_INVENTORY_REFRESH_TOKEN` works); Noor degrades gracefully in chats, awaiting owner token reissue in Zoho EU API Console.
- tj-id6m.17 (deferred by owner 2026-11-02 on closing `tj-id6m`): 10 optional product/ops choices parked unless requested (`docs/reports/audit-2026-11-01/README.md`: LLM reasoning effort/retries, in-flight supersession cancel, duplicate current-turn prompt message, CRM `paused`/`closed` reply behavior, manual `escalation_status` editing, `bot_enabled` fail-open vs fail-closed default + UI kill-switch, payment reminder UI/`manual` mode, public `/client-self-test/submit` retirement/rate-limit, KB `language` filter & `target_only` definition, one-off GitHub workflows).
- tj-r62i: client pilot waits for submitted choices, customer-side durable ownership/final-send coordination, authorized channel/restore-mode plan and fresh delivery evidence. Main Sol release tj-3jcn is complete; it did not activate the pilot.

- tj-i2b1: earlier527fe1f saved budget/hold but failed mixed matching/selection.
  Corrected a72da15live/CI4712passed; fresh2/3unit retained/held proof pending.
- tj-zc6k: stop recurring writer via account owner/provider; no audit SSH or
  Wazzup admin access available. Enabled guard recovers but cannot revoke keys.
- tj-uvld: AC02 provider stock/lifecycle coverage and paging stability need
  read-only causal before/after observations and complete delta membership.
  History access is now available; no owner console step is pending. Owner
  forbids warehouse mutations and no test organization is available.
- tj-uvld: provider-gated delta activation and real24h optimized counters are
  still pending; code delivered, no claim of optimized production savings yet.
- tj-4kot: outside account consumer (~50requests/min) incident remains open;
  cooldown fix delivered in25a8c08; external load resolution remains unproved.
- tj-535gclosed: liveREADONLYcollector07:15UTC returns45stale escalations,
  0dependency failures. Monitoring remains disabled; no old records changed.
- Zoho quotation live E2E remains unverified; no real messages were sent here.
- tj-1baw latency remains separate; tj-bgwu fixed in `codex/project-consistency-20261013`.
- Paid second reader stays off; reader-gap drift tracked in tj-4q79.
- tj-ierv: KB lacks owner facts for returns window, warranty term, hours,
  delivery/assembly fees, payment methods; articles defer them to the manager.

## Next recommended

Next stage id: tj-uvld-stock-sync
Recommended action: continue the same boundary after approved provider evidence.

Code delivery completed. Owner requires working-org read-only continuation.
History access live-verified through temporary read-only Self Client grants.
Next needs sufficient redacted before/after operation observations and complete
delta membership, without introducing warehouse test operations.
Read-only access alone does not establish otherwise unobserved coverage. Resolve
modified-since/filter timestamp semantics, prove AC02, then authorize delta
activation and collect24h UTC[start,end) counters. Do not close tj-uvld early.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the same authorized tj-uvld boundary.
Read docs/prompts/2026-10-03-zoho-stock-sync-optimization.md and the current
report/Beads notes to continue. Preserve the dirty primary checkout.

docs-reviewed: updated - audit reports (`docs/reports/audit-2026-11-01/`) and handoff updated; documentation-decision: dependency-lockfile upgrades preserve public contracts while internal PydanticAI/FastAPI adaptations are covered by strict mypy and full suite.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
