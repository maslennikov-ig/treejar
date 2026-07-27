# tj-ee5f.3 policy v2 implementation report

## AI path

Entrypoint: `TrustedAcceptanceRegistry.open_contracts()` and the local CLI.
Orchestration: immutable Task 1 loaders → typed policy compiler → exact
29-execution plan → authorization/preflight trust loading → protected
journal/adapter → structured oracle evaluation → anchored run loader.
Output boundary: canonical rollups and a typed Russian Markdown report written
exclusively with descriptor-relative no-follow I/O.

## Failure and fix

The returned Task 2 implementation allowed scenario-specific behavior,
caller-owned scope/results/readbacks, reusable classifier results, forgeable
action reservations, per-run quota resets, independently supplied tracked
attempts, and insufficiently bound authorization/store state.

Policy v2 replaces those paths with exact-set compilation, registry-loaded
classifier and structured artifacts, authorization-scoped append-only state,
one-use permits, sealed-raw redaction, an exact timestamped causal phase
machine, and protected run anchors. The final correction adds a generic
execution path for all 9 evidence blocks, requires 29 indexed committed-attempt
artifacts with exact seven-phase hash chains, removes caller-selected protected
roots, binds authorization to the immutable Task1 bundle, and derives the typed
report from protected execution/report-source evidence.

The same-process correction removes every runtime root-injection and local
self-authorization seam. The public verifier and finalizer accept only
`run_id`; finalization consumes a protected, digest-bound execution snapshot,
publishes the protected anchor last, and cleans both trees if full verification
fails. Protected receipts now cover classifier, structured event, tool,
readback, attempt, and report-source artifacts. Decisive evidence must bind an
attempt whose protected commit and receipt already passed verification, and
the attempt commit itself now binds the attempt digest alongside raw/tracked
bytes, semantic result, authorization, and unique phase head.

## Validation

- Final focused trust-boundary surface: 104 passed.
- Complete acceptance surface: 179 passed with exactly the two frozen Task1
  checks deselected; those two fail when included.
- Full repository excluding two frozen Task 1 Beads provenance checks:
  1803 passed, 19 skipped.
- Ruff/format, full `src` mypy, strict acceptance-module mypy, and process
  verification passed.
- Artifact validation and stage sizing passed. Stage readiness remains with the
  orchestrator because the repo currently names `tj-j13d` as the active stage
  and has no `tj-ee5f/summary.md`.
- No network, live provider, customer, production, deployment, or paid-model
  action was performed.

## Residual risk

Production traffic, real model/provider behavior, release identity, and
externally authorized readbacks remain unverified by design. They require the
later separately authorized acceptance execution. The two frozen Task 1
provenance failures remain explicit and were not masked.
