# Catalog Discovery Handoff Guard

Stage: `tj-lgmg-catalog-discovery`
Beads task: `tj-lgmg`
External issue: GitHub #55

## Goal

Prevent ordinary furniture discovery requests from becoming manager handoffs.
Catalog/product routing should handle furniture categories and use-case context before
the verified-answer no-match guard escalates.

## Routing Evidence

- `tj-lgmg` tracks GH #55 and is in progress.
- Prior related fixes handled SKU/order/name-gate cases, but this issue repeats at
  the broader intent boundary.
- Local code points are `src/llm/verified_answers.py` and the chat-layer handoff
  behavior in `src/llm/engine.py`.
- No dependency/API lookup is needed: the change is local intent classification and
  regression coverage.
- Graphify is not configured in this worktree (`graphify-out/GRAPH_REPORT.md` absent).

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write Zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | Preserve issue/history evidence | prior read-only subagents | none | Beads/GitHub history | summarized findings | done | Independent research already completed. |
| B | Add RED policy and engine regressions | local | `tests/` | Stream A findings | targeted pytest failures | sequential | Tests define one shared behavior contract. |
| C | Implement guard | local | `src/llm/verified_answers.py` | Stream B | targeted/full pytest | sequential | Same logic surface as tests; avoid overlapping writes. |
| D | Closeout | local | Beads/stage docs | Streams B-C | repo closeout commands | sequential | Requires fresh command evidence after implementation. |

## Implementation Tasks

1. Add RED tests for wardrobes, beds, and use-case context such as restaurant.
2. Keep payment terms and company/showroom office-location questions on manager path.
3. Extend product discovery signals and low-risk context handling in verified policy.
4. Run targeted regressions, then canonical verification where feasible.
5. Update Beads/handoff/stage evidence and report docs/graph review status.
