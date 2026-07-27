# Code Review: Grounded Model Adoption Post-Release

**Date:** 2026-07-27
**Generated:** 2026-07-27T17:00:36+03:00
**Status:** ✅ success
**Review version:** 1
**Scope:** `50f03ec..13f0a5c` plus the bounded `tj-r1f3` correction
**Verdict:** ACCEPT after fixes

## Executive Summary

| | P0 | P1 | P2 | P3 |
| --- | ---: | ---: | ---: | ---: |
| Findings | 0 | 1 | 2 | 0 |
| Remaining | 0 | 0 | 0 | 0 |

## Detailed Findings

### P1 — Grounding policy was not the final runtime prompt tail

- **Evidence:** `src/llm/prompts.py:273-282` finalized the policy after
  database components, but `src/llm/engine.py:8673-8725` appended mutable
  behavior, FAQ, CRM, customer-fact, and runtime blocks afterwards.
- **Impact:** later instructions or untrusted context could weaken the intended
  evidence/tool/manager hierarchy.
- **Fix:** `src/llm/communication_policy.py:115-121` now normalizes the prompt
  to exactly one policy copy. Both the database builder and final live
  sales/follow-up assembly use it; the live return at
  `src/llm/engine.py:8727` is the final tail.
- **Invariant:** the prompt test injects conflicting behavior, FAQ, customer
  facts, and runtime directives, then proves they all precede the single final
  policy.

### P2 — Grounding smoke accepted contradictory semantic equivalents

- **Evidence:** direct probes passed asserted showroom booking, guaranteed
  sample fulfillment, spinal-health benefit, and inventory-unit claims because
  the original evaluator recognized only a narrow set of literal phrases.
- **Impact:** the bounded release gate could report a false-positive safe
  result for a semantically unsafe free-text reply.
- **Fix:** `scripts/verify_model_routes.py:54-82` adds clause-aware bounded
  patterns for those assertion domains while preserving safe negation.
  Regression cases are recorded at
  `tests/test_scripts_verify_model_routes.py:150-205`.

### P2 — Missing-stock smoke accepted deferred-check promises

- **Evidence:** the evaluator accepted “Let me check” even though the runtime
  contract requires silent tool use. The first delta also showed that
  “I'll confirm availability” escaped the initial correction.
- **Impact:** a `5/5` smoke result could overstate fallback compliance.
- **Fix:** `scripts/verify_model_routes.py:79-82,405-424` rejects first-person
  future `check`, `confirm`, `look up`, and `verify` promises. Safe
  “can't confirm without a current inventory result” wording remains valid.

## Validation Results

- TDD red phase: six expected failures, followed by two expected synonym
  failures in the bounded correction.
- Final affected slice:
  `uv run pytest tests/test_llm_prompts.py tests/test_llm_engine.py
  tests/test_scripts_verify_model_routes.py -q --tb=short` — `374 passed`.
- Mypy — passed over `162` source files.
- Focused Ruff, Ruff format, and `git diff --check` — passed.
- Final delta-review — no remaining P0–P3 findings; `ACCEPT`,
  `replan_required: false`.
- **Overall:** ✅ PASSED.
- No provider, production, customer, Wazzup, Zoho, quotation, order, paid, or
  other external action was performed.

## Positive Patterns

- The centralized model settings continue to disable V4 Flash reasoning across
  default helper paths, including fact extraction.
- The correction preserves the accepted `build_system_prompt()` contract and
  does not rewrite closed `tj-j13d` evidence.
- Unsafe and safe-negation examples are both covered, reducing false positives
  without treating unknown stock as unavailable.

## Next Steps

The accepted historical `5/5` provider evidence was produced by the previous
validator. Before this correction is deployed, rerun the bounded five-call
provider smoke and the normal health/readback checks with current
authorization. Push/deploy and provider calls are intentionally outside this
local review pass.

## Documentation and Graph Review

- `docs-reviewed: updated` — this report and the current-state handoff record
  the findings, fixes, verification, and external delivery gate.
- `project-index: reviewed-no-change` — no new entrypoint or ownership boundary.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
