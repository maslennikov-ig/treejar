# tj-ee5f.5 Task 2 — Production adapters, collector, and CLI

Base: `main@48493b679423aa679aefe513f1eaf47f37ed17e7`.
Candidate: `fdabff2`.

Implement Task 2 from
`docs/superpowers/plans/2026-07-28-noor-task3-production-trust-repair.md`.

## Boundary

- Local implementation and fake transports only.
- No network, SSH, provider, production, customer, CRM, quotation, order,
  Telegram, deploy, cleanup, or other external action.
- Consume the accepted Task 1 authority handle, permit, producer, collector,
  transcript, gate, inventory, and finalizer contracts without weakening them.

## Deliverables

- `scripts/e2e_acceptance/production.py`
- `scripts/run_noor_e2e_acceptance.py`
- minimal compatible `scripts/e2e_acceptance/runner.py` changes
- focused acceptance tests
- `.codex/stages/tj-ee5f/artifacts/tj-ee5f.5-task2.md`

## Required behavior

- Fake HTTP and read-only SSH transports with deterministic timeout, response,
  and uncertain-dispatch behavior.
- Capability dispatch by typed capability, never scenario ID.
- Exact permit validation immediately before adapter I/O.
- Protected message/request files; raw responses only in protected storage;
  redacted checksum projections only in tracked output.
- Independent read-only collector that cannot mutate and emits the exact Task 1
  collector artifact/receipt layout.
- Protected run-plan loader with deterministic plan/evaluator digests.
- Resumable `prepare`, `preflight`, `execute-resume`, `record-gate`, and
  `reconcile-action`, and `finalize` commands that fail closed on drift,
  duplicate permits, stale readbacks, unknown actions, incomplete settlement,
  or nonterminal effects.
- Local fake-transport end-to-end and crash/recovery coverage.
- Strict production snapshot materialization that binds the sealed plan,
  evaluator, authorization, independent final-causal head, terminal journal
  head, all 29 attempts, four artifacts for every recorded gate, collector
  receipts, and the complete derived publication before its first write.
- Descriptor-relative protected snapshot writes and safe single-component run
  identities.

## Verification

TDD RED before behavior implementation. Run focused tests, all acceptance tests,
Ruff, format, Mypy, full Pytest, process verification, artifact validation,
privacy/secret scans, and independent full-range review. Do not push.

## Prior independent findings to re-check

The original frozen range received `FIX` for eight P1 findings and one P2
verification gap. Review the complete corrected range from the clean Task 1
base; do not rely on the superseded early MERGE note. Specifically reproduce
or inspect baseline provenance, sealed-plan replay, capability routing, permit
ordering, collector recovery, raw/tracked separation, unknown-action
reconciliation/settlement, exact gate retry, and journal-bound finalization.
