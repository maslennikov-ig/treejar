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
from that exact tip. `.1`, `.2` and `.3` are accepted; `.6` is next. One
stage-2 repair-judge call cost $0.001265216.

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

### tj-n7p4.2 — accepted

- `closed_question` — **replacing**: a standalone known-slot question becomes
  a localized acknowledgement and the next action.
- `premature_quote_details` — **replacing**: the answer stays and pre-consent
  detail collection becomes the quotation opt-in.
- `first_turn_opening` — **replacing**: duplicate greeting and identity are
  removed only after canonical identity and capability cover them.
- `selling_turn` — **removing**: trailing or repeated questions can disappear
  without equivalent text.
- `deferred_commitment` — **replacing**: it only inserts a named commitment and
  preserves the original reply.
- `grounding_output` — **removing**: unsupported sentences can disappear
  without equivalent text.
- Eight new contract tests passed without editing any existing test. Removing
  declarations return original text plus a flag; replacing declarations reject
  uncovered output. The named legacy candidate bridge preserves output only
  until `.3` consumes the flags.
- The protected replay matched all 60 raw and rendered digests with zero
  coverage failures and aggregate `1b0b2963…`; only the one known grounding
  flag fired.
- Ruff and format passed over 371 files; Mypy passed over 173 source files;
  Pytest passed with 3573 tests and 19 skips; process verification passed.

### tj-n7p4.3 — accepted

- A fixed second-vendor judge now answers approve, correct or cannot-fix for a
  removal flag. Per-turn trace records flags, model, answers, tokens and cost;
  no flag means no call.
- Corrections pass through the complete reply policy again. Empty or still
  flagged corrections are rejected and retain a counted handoff requirement.
- One finalizer records the actual final reply once, masks reply and candidate
  PII before the provider call, and filters deferred media against corrected
  text. The `.2` legacy removal-candidate bridge is gone.
- With owner authorization, two stale assertions that required automatic
  deletion now require original text plus a non-visible candidate. A local
  judge fixture prevents unit tests from making external calls.
- Protected replay matched all 60 source digests, fired one flag and changed
  exactly that reply: dialog 789. One GLM call returned one accepted correction
  for $0.001265216; zero approvals, cannot-fix, rejected corrections or
  handoffs. Final aggregate digest: `802c0e95…`.
- The root read the correction beside the original and prior candidate. It
  replaces the unsupported customer-furniture service with supported catalog
  help and preserves confirmed context and the next question. This accepted
  semantic reading closes `tj-rt7w.14` without a brittle length ratio.
- Ruff and format passed over 373 files; Mypy passed over 174 source files;
  Pytest passed with 3585 tests and 19 skips; process verification passed.
