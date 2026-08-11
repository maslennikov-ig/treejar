# Stage tj-mshi-permission-list

Status: in progress
Base: `main` at `ee34629`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — first-party Python, prompt and
policy text, and an existing provider client only.

## Scope

Deliver `tj-mshi.2`, `.3`, `.4`, then `.5`. The ratified list is immutable
input. The stage changes the prompt and measures the result; it adds no
deterministic commitment check or customer-text repair path.

## Execution

Root-owned and sequential. The children share one registry and prompt path, so
parallel writes would make the measured change and rollback boundary unclear.

## Current checkpoint

`tj-mshi.1`, `.2`, and `.3` are accepted. `tj-mshi.4` is the next child. No
paid call has occurred in this stage yet.

The owner explicitly authorized updating
`test_commercial_capability_registry_uses_evidence_authorization_modes` on
2026-08-11. Its exact-set expectation expands from the old eight entries to the
ratified 25 and is recorded as a declared contract expansion. No compatibility
shim or second registry is introduced.

## Child results

### tj-mshi.2 — accepted

- `COMMERCIAL_CAPABILITIES` contains exactly the 22 ratified promises and three
  redirects with their owner-ratified modes and explicit sources.
- `not_offered` is a first-class mode; the previous broad
  `exceptional_terms` bucket is replaced by the separately ratified manager
  commitments.
- The owner authorized the existing exact-set test update. Focused red-green
  proved the old eight-entry set fails and the 25-entry set passes.
- Ruff and format passed; Mypy passed over 173 source files; Pytest passed with
  3559 tests and 19 skips; process verification passed.

### tj-mshi.3 — accepted

- All 25 instructions state what Noor may say while preserving the ratified
  condition; the rendered header is `[WHAT NOOR MAY PROMISE]`.
- Focused red-green failed first on `showroom_visit`, `project_samples`,
  `discount`, and the old header, then passed after the positive rewrite.
- The owner-authorized discount assertion replacement holds both
  `manager_required` and the prior-approval condition.
- Ruff and format passed; Mypy passed over 173 source files; Pytest passed with
  3560 tests and 19 skips; process verification passed.

## Acceptance note for the remaining children

Two additional existing assertions pin prompt prohibitions that the ratified
plan explicitly removes:
`test_the_directive_unlocks_no_fact_and_no_commercial_term` pins the negative
discount wording owned by `.3`, and
`test_build_system_prompt_appends_immutable_evidence_grounding_policy` pins the
future-check prohibition owned by `.4`. Neither is a grounding backstop test.
The owner authorized both as declared contract replacements on 2026-08-11;
their replacement assertions preserve the condition while testing the new
positive permission contract.
