# Live reply repair and main release

Tasks: tj-15bc (runtime failures), tj-a1bi (main delivery).
Owner explicitly authorized Push, Merge, Deploy on 2026-09-17.
Status: merged into main and deployed.
Release: `4abe8355d6dbb074d1d8e66e963457e054a481c2`.
CI: https://github.com/maslennikov-ig/treejar/actions/runs/35223521584 (success).

## Verified causes

- 12:32 UTC, conversation 3cad3e63-c1c2-42fb-b272-c728207dc51f:
  formal quotation reply contains a bare numbered item. Reproduction confirms
  the surplus-question reducer can delete question text but retain its ordinal.
- 12:36 UTC, same conversation: get_stock -> _resolve_inventory_item ->
  Zoho Inventory GET /items raises HTTP 429 after retries and aborts agent run.
- 12:39 UTC, conversation 03eec434-3b6e-4df7-8efb-051252efd159:
  search tools run for LUMA and NOVO, then catalog-fact-repair produces a generic
  answer claiming no catalog access (81 input tokens). Installed PydanticAI
  skips dynamic system prompts on nonempty message history. The repair pass
  also reused DB history instead of the completed model/tool exchange.

## Repairs

- Register dynamic persona/context as per-run instructions, including turns
  with history. Carry completed tool messages and retrieved rows into catalog
  repairs. Output repair gets bounded catalog/history evidence with PII masking.
- Reject reductions that leave bare list markers. Flag malformed generated
  lists for a coherent model rewrite, including surrounding count references.
- Return typed unavailable evidence for transient Inventory reads; do not invent
  zero stock, lose catalog facts or retry failed lookups repeatedly in a turn.
  Avoid blind retries of writes. Unrelated notification errors remain visible.
- Native sequential tool scheduling protects the shared AsyncSession and
  mutable turn state when the model requests multiple tools in one response.
- CI preserves an already-running test-only worker only after checking current
  and candidate effective settings, allowed channel, inbound-only function set
  and zero cron jobs. Refresh app/worker together with a 180-second graceful
  timeout. Normal/stopped workers keep the prior app-only deployment gate.

## Risk and acceptance

Premortem: GO WITH CONDITIONS. No environment, access, database repair, queue
cleanup or broader activation. Existing test-only restrictions and Telegram
reset remain. Back up prior runtime source/image before standard deployment;
check exact release, healthy dependencies and identical worker boundaries.
Do not send synthetic customer messages or make more paid probe calls.

Real local FunctionModel tests exercise history -> tools -> repair with full
persona/evidence, Inventory 429 continuation, and nonoverlapping shared-session
operations. Formatting tests reproduce the orphan marker and require model repair.
No new paid-model or WhatsApp end-to-end acceptance is claimed.

Local release verification: 4,065 tests passed and 20 skipped; one handoff-schema
check failed, required fields were restored, then all 65 related documentation
and process checks passed. Total functional acceptance: 4,066 tests. Ruff,
format and Mypy (180 source files) passed. Deployment script: 11 tests and bash
syntax passed. No new paid calls or synthetic messages.

Pre-deploy backup: `/opt/noor/.hotfix-backups/tj-15bc-main-20260917`.
Rollback to prior source archive and `compose-rollback.yml` (app/worker only),
image `noor-intent:tj-tn29`, release `9a08683`; retain environment and DB activity.

GitHub OAuth rejected workflow-file updates (missing workflow scope). Delivery
therefore leaves CI unchanged and makes the existing --app-only script invocation
preserve verified running test-only workers automatically. The same 11 deployment
tests pass for that exact invocation. No permission expansion was requested.
Runtime src/ is byte-identical to the fully checked implementation branch.

## Final live evidence

Deployment completed 2026-09-17 at approximately 12:55 UTC. CI passed
4,059 tests, skipped 27; lint and type-check succeeded. Standard deployment
completed with app and worker running, zero restarts, public health200 with exact
release SHA and healthy database/Redis. All14changed source-file hashes match
accepted local code in BOTH containers. Environment fingerprint unchanged.
Worker registers only process_incoming_batch; restore mode remains true, cron
and embedding warmup disabled. Telegram reset source hashes also match.

App image: `sha256:700bb57c11522a1fa8ecac920dde9255d8aa0a3d4f3a6455964bbb16d9bbe27b`.
Worker image: `sha256:0f10dc981d7c72de23436275a34f9f93b891e9730e7fc5e5e1d0636ef38a1e5f`.
The standard build creates separate service image identities with matching source.
No synthetic outbound messages, additional paid probes, DB repairs or resets.
The previous isolated probe's limitations remain documented in the prior report;
this release adds actual local multi-request agent regression evidence.
