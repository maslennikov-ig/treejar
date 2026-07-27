# tj-ee5f.3 policy v2 implementation report

## AI path

Entrypoint: no-argument `TrustedAcceptanceRegistry.from_canonical_repo()` and
the local CLI.
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
self-authorization seam. The production registry validates the canonical
repository top-level, origin, and git-common identity, then loads its own
policy; dependency injection exists only in a test backend under `tests/`.
The public verifier and finalizer accept only `run_id`; the operator root is
derived from canonical git-common layout. Each protected open/evaluation
returns a frozen, ephemeral `VerifiedEvidenceContext`; it is never persisted
or replaceable on the caller-visible production registry.
Finalization consumes a committed protected execution snapshot and derives the
run, index, report source, receipts, and anchor. It fsyncs prepared trees,
publishes tracked then protected data, and writes the whole-tree protected final
commit marker last through a temporary 0600 file, complete write, file fsync,
atomic rename, and directory fsync. Empty, truncated, or contract-invalid
markers are never accepted; retry removes the incomplete final roots and
deterministically rebuilds them from the protected snapshot. It also removes
orphan per-run staging before retry. The protected snapshot commit binds the
authorization digest, journal head, exact attempt-chain-head map, and canonical
operator-store digest. Protected
receipts cover classifier, structured event, tool,
readback, attempt, and report-source artifacts. Decisive evidence must bind an
attempt whose protected commit and receipt already passed verification, and
the attempt commit itself now binds the attempt digest alongside raw/tracked
bytes, semantic result, authorization, and unique phase head.

## Validation

- Final focused trust-boundary surface: 117 passed.
- Complete acceptance surface: 192 passed with exactly the two frozen Task1
  checks deselected; those two fail when included.
- Full repository excluding two frozen Task 1 Beads provenance checks:
  1816 passed, 19 skipped.
- Ruff/format, full `src` mypy, strict acceptance-module mypy, and process
  verification passed.
- Artifact validation and stage sizing passed. Stage readiness remains with the
  orchestrator because the repo currently names `tj-j13d` as the active stage
  and has no `tj-ee5f/summary.md`.
- No network, live provider, customer, production, deployment, or paid-model
  action was performed.

## Residual risk

The local boundary does not defend against arbitrary Python execution in the
same process or an OS/host owner that can rewrite the git-common protected
store. Python-private names and file modes are not security boundaries for
those actors; that threat model requires an external WORM store or an
independently managed signing/key service.

Production traffic, real model/provider behavior, release identity, and
externally authorized readbacks remain unverified by design. They require the
later separately authorized acceptance execution. The two frozen Task 1
provenance failures remain explicit and were not masked.
