# Orchestrator Handoff

Updated: 2026-09-23
Current branch: main (delivery worktree: codex/catalog-price-unit)
Current stage id: tj-stwf-test-only-restore (last operational stage)
Status: Luna medium integrated, deployed, and bounded post-deploy checks complete.

## Current truth

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

- tj-bgwu: corpus identity tests assume a normal .git directory; local linked
  worktree acceptance uses focused checks and canonical CI for the full suite.
- Existing unrelated product tasks remain tracked separately. Wazzup sender
  authentication enforcement is backlog; referral activation remains excluded.
- Paid second reader remains off; reader-gap drift stays tracked in tj-4q79.

## Next recommended

Continue tester-authored testing on test0665. Full WhatsApp delivery and a real
quotation remain separate observations; bounded model checks do not certify every
future answer. No implementation or main-integration tail remains for this task.

docs-reviewed: updated - final release, model evidence, fixes and recovery recorded.
graph-reviewed: no-change-needed - no graph is available in this worktree.
