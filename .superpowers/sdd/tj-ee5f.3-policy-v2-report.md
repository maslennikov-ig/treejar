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

The alternate-path correction removes every runtime root-injection seam. The
only public verifier accepts `run_id`; the low-level loader requires a private
registry capability. Protected producer receipts now bind every attempt to its
run, execution, raw/tracked bytes, semantic result, authorization, protected
commit, and unique phase head. The same fixed-root materializer/receipt pattern
protects decisive structured evidence and binds the report source to the full
report payload and verified snapshot.

## Validation

- Final focused trusted execution/report surface: 73 passed.
- Complete acceptance surface: 175 passed; only the two frozen Task1 checks
  failed when included.
- Full repository excluding two frozen Task 1 Beads provenance checks:
  1799 passed, 19 skipped.
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
