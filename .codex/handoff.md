# Orchestrator Handoff

Updated: 2026-10-03
Current branch: codex/tj-uvld-stock-sync
Current stage id: tj-uvld-stock-sync
Status: local stock optimization verified;241 tests/Ruff/mypy/process passed.
Delivery: local commits only; main/live remains outside this task's authority.

## Current work

- Beads tj-uvld owns AC01–AC12 and remains in_progress until provider coverage,
  authorized delivery and real 24h measurement are accepted.
- Worktree: /home/me/code/treejar/.worktrees/tj-uvld-stock-sync.
- Base: main 36c86137a51d2e6485db92c28ec057fe26f03339; prepared docs and
  tj-4kot cooldown07591b8 reused by cherry-pick. Primary dirty work preserved.
- Candidate: gated 600s delta + daily03:17UTC full, owned lock/CAS generations,
  48h retention with1h customer ceiling, selected-SKU fresh quotation checks,
  shared HTTP counters and read concurrency/cooldown.
- Owner decision: stock2 vs agreed5 stops quotation, states only2 available,
  and awaits a new customer decision. Consent becomes deferred; unchanged
  shortage state cannot trigger another automatic/background creation.
- Source observation and successful dataset coverage are distinct. Multi-page
  delta requires two identical complete reads; changed pages abort publication.
  This safeguard does not establish provider paging/operation completeness.
- Code SHA:0b5c723eeb96c240d2c1654f6b570d951aa782eb.
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

- Readiness audit reported live/main36c8613, TEST_CHANNEL_RESTORE_MODE=true,
  WhatsApp sender/outbound allowlist limited to ending0665, Telegram webhook
  healthy after token rotation. This task did not change those settings.
- Earlier stage's push/deploy/model-test authority does not cover tj-uvld.
- Merge/push/deploy, external stock mutations, OAuth/access changes and real
  messages need fresh owner approval. No paid model reader/calls were used.
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
- tj-uvld: merge/release checks/deploy/activation and real24h counters require
  separate delivery authority; no claim of actual production savings yet.
- tj-4kot: outside account consumer (~50requests/min) incident remains open;
  reused cooldown fix does not prove external load resolved or authorize deploy.
- tj-535g: monitoring fixa4cc1a7 remains separate and undeployed; monitoring
  activation was not changed. Primary handoff retains its independent truth.
- Zoho quotation live E2E remains unverified; no real messages were sent here.
- tj-1baw latency and tj-bgwu linked-worktree corpus assumptions remain separate.
- Paid second reader stays off; reader-gap drift tracked in tj-4q79.

## Next recommended

Next stage id: tj-uvld-stock-sync
Recommended action: continue the same boundary after approved provider evidence.

After local acceptance/commits, request one concrete approved test organization
and a bounded stock-operation diagnostic. Prove AC02 before considering delta
activation. Then obtain separate merge/deployment authority and collect24h
UTC [start,end) counters with Moscow conversion. Do not close tj-uvld early.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the same authorized tj-uvld boundary.
Read docs/prompts/2026-10-03-zoho-stock-sync-optimization.md and the current
report/Beads notes to continue. Preserve the dirty primary checkout.

docs-reviewed: updated - state/entrypoints, provider receipts, rollback and pending gates.
graph-reviewed: no-change-needed - no enabled task-owned graph; ordinary code navigation used.
