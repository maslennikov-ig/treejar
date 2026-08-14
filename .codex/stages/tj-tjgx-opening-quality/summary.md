# Stage `tj-tjgx-opening-quality`

Status: accepted.

The stage fixes the four bounded first-opening defects measured in `tj-399z`.
It does not change the rubric, applicability map, model, price anchor,
retrieval contract, or production runtime.

## Result

- Discovery examples are kinds of work, not products (`tj-j62b`).
- Product categories may answer the job but may not relist Treejar's offer
  (`tj-593w`).
- Each distinct stated need is answered or explicitly left unconfirmed before
  discovery (`tj-1orh`).
- Equivalent bounded name wording is recognised without matching named objects,
  so the canonical ask is not duplicated (`tj-b8px`).

## Verification

Focused TDD first produced four intended failures, then 85 passes. The release
closeout passed Ruff, format, Mypy, process verification, and the full suite:
3803 passed, 20 skipped, 0 failed. This is exactly five new passing tests over
the 3798/20/0 baseline. Protected replay remains `1b425bd1…` against frozen
`1fc87c04…`, with the same seven expected differences on dialogs 28, 875 and
1291; no re-baseline was made.

project-index: reviewed-no-change — no runtime entrypoint, module ownership or
navigation path changed; only the current-stage pointer moved.

docs-reviewed: updated — the current-state handoff records the new response
contract and keeps the production boundary explicit.

graph-reviewed: no-change-needed — Graphify is not initialized and no graph
entrypoint exists for this repository.
