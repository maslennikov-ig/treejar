# Orchestrator Handoff

Updated: 2026-10-03
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
- Live app+worker:25a8c080e9b014333380b8e62be7d5e981daefe7;
  CI4451 passed/27 gated skips; local4458/20. Zero restarts, health/deps OK.
- .env/safety fingerprints unchanged; DB/Redis/nginx containers retained.
- New v2/legacy:2557 rows,48h TTL. UTC[14:50:52,14:53:10):
 13GET/13HTTP200,1successful full cycle; not optimized24h evidence.
- Delivery receipt:docs/reports/2026-10-03-zoho-stock-sync-delivery.md.
- Report: docs/reports/2026-10-03-zoho-stock-sync-optimization.md.
- Stage: .codex/stages/tj-uvld-stock-sync/summary.md.

## Provider evidence and eligibility

- Read-only probes2026-10-03:9 InventoryGETs,8HTTP200+1HTTP400.
  Literal trailingZ rejected; +0000 accepted, including sorted empty delta.
  Bulk1/2/4/8 returned all requested IDs with numeric stock;8 is a verified
  lower bound, not the endpoint maximum. No business write/OAuth refresh.
- Stock-operation coverage, nonempty paged delta semantics/equal timestamps
  and lifecycle completeness remain unproved. Incremental activation stays off.
- Current read-only mapping:343 active catalog rows,250 stored IDs,306 matches,
 2557 snapshot entries. Optional catalog scoping stays off.
- Retained receipts: docs/research/2026-10-03-zoho-stock/.

## Operating boundary

- Live25a8c08, TEST_CHANNEL_RESTORE_MODE=true; .env and app/worker safety
  fingerprints equal predeploy. Approved0665 sender/allowlist and Telegram
  phone isolation unchanged; no new messaging/webhook configuration.
- Current owner authority covers tj-uvld push/merge/deploy with delta gate off.
- External stock mutations, OAuth/access changes and real messages still need
  separate approval. No paid model reader/calls were used.
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

- tj-uvld: AC02 provider stock/lifecycle coverage and paging stability need an
  approved test organization or bounded owner-authorized transactions.
- tj-uvld: provider-gated delta activation and real24h optimized counters are
  still pending; code delivered, no claim of optimized production savings yet.
- tj-4kot: outside account consumer (~50requests/min) incident remains open;
  cooldown fix delivered in25a8c08; external load resolution remains unproved.
- tj-535g: monitoring fixa4cc1a7 remains separate and undeployed; monitoring
  activation was not changed. Primary handoff retains its independent truth.
- Zoho quotation live E2E remains unverified; no real messages were sent here.
- tj-1baw latency and tj-bgwu linked-worktree corpus assumptions remain separate.
- Paid second reader stays off; reader-gap drift tracked in tj-4q79.

## Next recommended

Next stage id: tj-uvld-stock-sync
Recommended action: continue the same boundary after approved provider evidence.

Code delivery completed. Next needs one concrete approved test organization
and a bounded stock-operation diagnostic, or sufficient redacted operation
history. Prove AC02, then authorize delta activation and collect24h UTC
[start,end) counters with Moscow conversion. Do not close tj-uvld early.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the same authorized tj-uvld boundary.
Read docs/prompts/2026-10-03-zoho-stock-sync-optimization.md and the current
report/Beads notes to continue. Preserve the dirty primary checkout.

docs-reviewed: updated - state/entrypoints, provider receipts, rollback and pending gates.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
