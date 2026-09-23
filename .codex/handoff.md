# Orchestrator Handoff

Updated: 2026-09-23
Current branch: codex/tj-uz6j-tester-0923 (from codex/catalog-price-unit 5967db6)
Current stage id: tj-uz6j-tester-0923
Status: Tester-feedback repairs implemented locally; not committed or deployed.

## Current stage: tj-uz6j tester feedback 2026-09-23

- Source: Angela's WhatsApp test of demo routes A/B on test0665 against live
  release 071b0e3; conversations 207f7c10, fa224cab, d24c5360. Plan:
  `docs/plans/toasty-munching-ritchie.md`.
- Regressions surfaced after the glm-5.3-flash -> gpt-6-luna switch (6ae4c0e):
  Luna follows tool contracts literally, exposing contract/state defects.
- Implemented (uncommitted): T1 media for products named by short model
  reference; T2 exact/generic match kinds, no false "exact item not confirmed";
  T3/T7 persisted decision state (selection/quote consent close the choice,
  proposal-bound affirmatives incl. wrong keyboard layout, reply supersession
  for messages arriving mid-generation); T4 named SKU direct lookup regardless
  of local stock; T5 negated quotation statements; T6 delivery/installation per
  docs/faq.md Q9-Q10 (owner decision 2026-09-23, supersedes 2026-08-11 assembly
  rule; grounding capability registry changed accordingly); T9 Zoho 429
  resilience and quotation deferral.
- Production was read only (DB SELECTs, logs). No server change was made.

## Previous release truth

- Live code release: `071b0e32f35bec5474ba4b7e4d1b651f85d45295`.
- CI35855524010 passed: 4,115 tests, 27 skipped; Ruff/format, Mypy and standard
  app-only deployment passed. App/worker are running with zero restarts;
  exact SHA health and healthy database/Redis confirmed.
- Primary model is `openai/gpt-6-luna`, with explicit core reasoning medium.
  DB override and environment fallback agree. Both running containers' settings
  and all four changed source hashes match the accepted code.
- Curly/modifier apostrophes in introduced names are captured before generation;
  generation-error replies no longer receive additive customer questions.
- Agent instructions prohibit deriving price units from packaging counts.
  Live Arabic/pack-price checks passed after a witnessed unsupported box-price
  claim was corrected. Original failed/incomplete traces are retained.
- Five distinct model scenarios checked across bounded runs: original Nadia,
  exact SKU, declined quotation/order/handoff, Arabic opening, packaging price.
  Real model/prompt/schemas, intercepted tool results, read-only catalog snapshot.
  No customer sends or order/CRM mutations. This is not WhatsApp E2E proof.
- Report/evidence: `docs/reports/2026-09-23-gpt6-luna-main.md` and its two JSON
  receipts. Tasks tj-qr32, tj-3nvu, tj-pmbv and tj-y1uj are delivered.
- Prior critical-only escalation, model-owned intent, quotation consent and
  35-second completion/90-second core deadline protections remain present.
- Prior reports: `docs/reports/2026-09-22-telegram-reset-webhook.md` and
  `docs/reports/2026-09-18-quotation-timeout.md`.

## Operating boundary

- TEST_CHANNEL_RESTORE_MODE=true; WhatsApp limited to ending0665. Sender and
  outbound allowlist match. Telegram remains authenticated admin reset only.
- Worker registers only process_incoming_batch; cron and embedding warmup off.
- No resets, customer data repairs, held-message inspection/replay, or outbound
  test messages were performed in this acceptance.
- Owner authorized Push, Merge, Deploy and bounded post-deployment model tests.
  The completed smoke set cost USD0.00813352; the earlier compatibility check
  cost USD0.0000155. No further paid tests or broader activation are queued.
- Frozen general grounding policy is unchanged; price-unit clarification is in
  the sales-agent instructions. Runtime readback safeguards remain unchanged.

## Recovery

- Latest source backup:
  `/opt/noor/.hotfix-backups/deploy-20260923T113912Z-from-e325c63fd7cf687d15d738cea2a20fd4a98a8f6b.tar.gz`.
- Original model-switch rollback: `/opt/noor/.hotfix-backups/tj-qr32-20260923`,
  prior main-model DB/env value z-ai/glm-5.3-flash; tagged app/worker images.
- Preserve all subsequent customer data and unrelated environment changes.
  Model rollback requires both the DB setting and environment fallback.
- Prior reset/data recovery pointers remain in the dated reports; no historical
  customer data or held messages were changed by this delivery.

## Explicit defers

- tj-uz6j.8: multi-turn demo-scenario regression gate before model/prompt
  switches (root cause of periodic degradation) is tracked, not built.
- tj-i0n0: no background retry for deferred quotations; completion happens on
  the next customer message or via the alerted manager.
- tj-n4kt catalog stock drift and tj-1baw reply latency are tracked separately.

- tj-bgwu: corpus identity tests assume a normal .git directory; local linked
  worktree acceptance uses focused checks and canonical CI for the full suite.
- Existing unrelated product tasks remain tracked separately. Wazzup sender
  authentication enforcement is backlog; referral activation remains excluded.
- Paid second reader remains off; reader-gap drift stays tracked in tj-4q79.

## Next recommended

Next stage id: tj-uz6j-tester-0923
Recommended action: commit the repairs, then deploy only with fresh owner
authority and have the tester rerun routes A and B on test0665.

## Starter prompt for next orchestrator

Use $orchestrator-stage for tj-uz6j. Read the plan above, verify the local
acceptance evidence, and obtain explicit owner authority before push or deploy.
Preserve the test0665-only boundary.

docs-reviewed: updated - tester-feedback stage and defers recorded.
graph-reviewed: no-change-needed - no graph used.
