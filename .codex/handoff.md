# Orchestrator Handoff

## Stage tj-ierv / tj-nm8c / tj-7ps5 (2026-10-23): admin dashboard UX overhaul — owner-authorized deploy
- Branch codex/tj-7ps5-admin-ux; summary .codex/stages/tj-ierv/summary.md.
- Delivered Light/Dark ThemeProvider, Variant 5A Bento overview, Variant 1B nav/queues,
  Variant 2A/3A canonical KB/rules preview+safe sync, Variant 4A conversations & 6A AIQC.

## October tester feedback — authorized completion2026-10-14

- Accepted epic `tj-i2b1`; findings `tj-i2b1.1` (false mismatch caveats), `.2`
  (missing updated summary), `.3` (literal refusal persistence), `.4`
  (missing photos for structured catalog titles).
- Delivered sourcea72da15 onmain; approved source4b032c7 plus CI fix6d4663f.
- Livea72da15/CI4712passed27skips:10:37fresh request saved2LUMA/6000/declined;
  separate10:43update saved3LUMA/12people, retained6000 and declined quote.
  Owner confirms photos in first reply and updated summary in second;
  no quotation effect or quote_sent. Prior527fe1f failure stays in delivery report.
- Source fixes retain named model/finish/unit constraints, recover explicit
  multi-unit quantity lost from model search queries, distinguish broad needs
  from missing exact items, and expose the committed selection/budget to replies.
  Requested summaries remain model-owned; retained customer budgets now
  survive output grounding, with old catalog prices still requiring new evidence.
- Literal evidence accepts one presentation quote pair only when the unchanged
  excerpt occurs in the current message. No paraphrase/history/permission gate
  changes. Explicit quote holds must be recorded, not just promised in prose.
- Media recognizes explicit comma-delimited model codes and a literal finish
  on the same reply line. Actual CT1065 text retains2photos, not the third variant.
- Acceptance/delivery details: `docs/reports/2026-10-13-tester-feedback-fixes.md`.
  Historical local acceptance:1271 tests, Ruff/format/Mypy194 passed. Earlier
  fixture replay passed with qty3/budget6000/consentdeclined, no real sends.
  Total smoke costUSD0.04873962; latestcapturescurrenttext,3units/6000/held,
  budgetstopbeforefinalreply. App/workera72da15 deployed14Oct10:26UTC.
- Accepted source4b032c7 adds DB tz/index/client fixes (`tj-535g`), LLM/name/
  quantity consistency, repo/Docker hygiene and `tj-bgwu`; engine11360lines.
  Independent root4555/20and96CI/metadata checks passed. Canonical CI38526089347
  passed4584/27,Ruff/Mypy194,semantic gate/deploy; tj-7ize accepted/closed.
- Authority/preflight/rollback and delivery: `docs/reports/2026-10-14-tester-epic-completion-delivery.md`.
- Cleanup/ownership receipt: `docs/reports/2026-10-13-tester-feedback-closeout.md`.
  Dirty primary preserved; deployed.env/protectedfingerprint byte-identical.
  Test0665/guard/restore retained; equivalent CI/catalog worker checkouts removed.
- docs-reviewed:updated;graph-reviewed:no-change-needed - existing paths.

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

docs-reviewed: updated - state/entrypoints, provider receipts, rollback and pending gates.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
