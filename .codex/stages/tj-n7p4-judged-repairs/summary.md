# Stage tj-n7p4-judged-repairs

Status: in progress
Base: `main` at `5ef5eeb`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — first-party Python response
policy, existing provider client, protected stored outputs, and the frozen
repository acceptance harness.

## Scope

Deliver `tj-n7p4.1`, `.2`, `.3`, `.6`, `.4`, then `.5`. The stage separates
classification from repair, declares the six existing guards, adds the
three-answer second-vendor repair judge and manager fallback, aligns the
acceptance harness, and measures the resulting production path.

## Execution

Root-owned and sequential. All children change or measure the same reply path,
repair contract, provider counter, and protected replay. Parallel writers
would blur the behavior-preserving replay and paid-call accounting. No
subagent is used.

## Current checkpoint

Stage 1 `tj-mshi-permission-list` is accepted at `5ef5eeb`. Stage 2 is opened
from that exact tip. `.1` is accepted and `.2` is next. No stage-2 paid call has
occurred.

## Acceptance boundary

No customer-visible content is removed unless equivalent replacement content
is deterministic and proved, or a model wrote and re-classified the repair.
Judge failure becomes a counted manager handoff. The frozen twenty measures
the same path production would send.

## Child results

### tj-n7p4.1 — accepted

- Production and the acceptance harness call the pure classifier and pass its
  flags to one named deterministic repair function. The legacy enforcement
  name is an identity alias, not another implementation.
- Four focused tests were added; no existing test was edited. The focused set
  passed 133 tests after the expected import failure in red.
- The protected full-chain replay matched all 60 stored raw and rendered
  digests; aggregate `1b0b2963…` stayed unchanged.
- Ruff and format passed; Mypy passed over 173 source files; Pytest passed with
  3565 tests and 19 skips; artifact, stage-sizing, traceability, and process
  verification passed.
