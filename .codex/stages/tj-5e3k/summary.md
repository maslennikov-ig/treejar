# Stage tj-5e3k Summary

Updated: 2026-07-27
Status: in progress
Branch: `main`
Beads: `tj-5e3k`

## Boundary

One production-safe synthetic evaluation boundary compares four candidates on
each Noor route. It reruns all baselines in the same provider window and
preserves the accepted cases, scoring, hard gates, and blind-review contract.
Production routing and customer traffic are excluded.

## Streams

| Stream | Owner | Decision | Reason |
| --- | --- | --- | --- |
| Candidate profile, tests, and harness | root | local | One shared scoring and request contract |
| Sales and system inference | root | sequential | Comparable latency without client/rate-limit contention |
| Anonymous sales review | context-isolated reviewer | after sales evidence | Model identities must remain hidden until scoring is recorded |

## Scope Ledger

- Sales: GLM-5, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Fast/system: Nex-N2-Mini, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Twelve sales and twenty-four system cases, two repetitions each.
- Fresh baseline runs, strict gates, comparative ranking, durable evidence.
- No production switch.

## Current Evidence

- Both new exact IDs are present in the live OpenRouter catalog.
- Both advertise tools, tool choice, reasoning, response format, and structured
  outputs required by this stage.

## Closeout

- Verification pending.
- `docs-reviewed: pending`
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

