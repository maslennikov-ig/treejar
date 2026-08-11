# Stage tj-mshi-permission-list

Status: accepted
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

`tj-mshi.1` through `.5` and epic `tj-mshi` are closed. Stage readiness and
slice closeout passed; safe workspace cleanup found no child workspace to
remove. `tj-n7p4-judged-repairs` remains unopened until this accepted stage is
committed locally.

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

### tj-mshi.4 — accepted

- The customer-owned-furniture block, two future-check prohibitions, greeting
  duplicate for `deferred_answer`, and compact-policy discount duplicate are
  gone. Their conditions remain once in the positive registry; no compensating
  prohibition was added.
- `test_customer_owned_furniture_prompt_covers_the_service_promise_family` was
  **removed and replaced** by
  `test_customer_owned_furniture_redirect_covers_the_service_promise_family`.
  This was a declared removal, not a test edited to accommodate a move.
- `test_llm_grounding_output.py` passed untouched: 107 passed; SHA-256
  `9cd7c94e22ff029702271040db3b80cd4d416b761645abf0ca6c3e641cbe7917`.
- Protected replay was widened from 31 to all 60 stored raw outputs: zero
  changes, aggregate digest `1b0b2963…` before and after.
- The root read the recruitment redirect and the phrasing-family test passed.
  The actual new dialog 28 reply remains the acceptance boundary for
  `tj-riim` in `.5`.
- Ruff and format passed; Mypy passed over 173 source files; Pytest passed with
  3561 tests and 19 skips; process verification passed.

### tj-mshi.5 — accepted

- Exactly 20 authorized Luna generation calls and zero judging calls completed
  on the frozen seed-`20260810` set. Cost was $0.005458; 20/20 responses,
  20/20 root evaluations, and 20/20 language passed.
- The root read all 20 replies and 300 criteria blind with zero red flags.
  Dialog 28 no longer promises recruitment routing or a callback; dialog 789
  still rejects customer-owned-furniture buying, resale, or assessment.
- Criticals did not rise: 1 to 1. The candidate harness code is dialog 1067
  `hallucination`, a frozen-detector false positive on a catalog-supported SKU;
  `tj-2p4c` tracks it without changing the ruler.
- Paired weighted delta was +0.32 with 95% CI -0.86 to +1.82; raw delta was
  +0.25 with 95% CI -0.10 to +0.70. Both are inconclusive.
- Rules 14 and 15 stayed 0 to 0 and were applicable on 0/20 openings. This
  corpus cannot decide whether the permission list is too tight.
- Ruff and format passed; Mypy passed over 173 source files; Pytest passed with
  3561 tests and 19 skips; artifact and process verification passed.
- Full report:
  `docs/reports/2026-08-11-permission-list-measured-round.md`.

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

## Closeout reviews

- `docs-reviewed: updated - the measured-round report, stage summary, child
  artifacts, and handoff state the permission contract, paired result,
  protected evidence boundary, and instrument limitations.`
- `project-index: reviewed-no-change - no module, public facade, or navigation
  entry was added, removed, or renamed.`
- `graph-reviewed: no-change-needed - Graphify is not initialized in this
  repository.`
