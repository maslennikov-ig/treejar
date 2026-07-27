# Stage tj-5e3k Summary

Updated: 2026-07-27
Status: accepted
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
| Anonymous sales review | fresh context-isolated reviewer | after sales evidence | Model identities remain hidden and A/B/C/D exposure is counterbalanced |
| Correctness and delta review | targeted reviewer | after evidence | Release-boundary methodology and report claims require an independent lens |

## Scope Ledger

- Sales: GLM-5, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Fast/system: Nex-N2-Mini, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Twelve sales and twenty-four system cases, two repetitions each.
- Fresh baseline runs, strict gates, comparative ranking, durable evidence.
- No production switch.

## Result

- Core sales strict winner: `z-ai/glm-5`, weighted `93.975`, all hard gates
  passed, blind quality `93.50%`, p95 `10.710s`.
- Fast/system strict outcome: `no_safe_replacement`; every candidate missed at
  least the `95%` semantic gate.
- Fast/system practical hardening target: `deepseek/deepseek-v4-pro`, weighted
  `85.353`, `100%` first-pass JSON/schema, reliability, tool arguments, and
  reasoning-control compliance; semantic accuracy `72.82%`, p95 `12.168s`.
- DeepSeek V4 Flash is the semantic runner-up at `73.79%`, weighted `84.133`,
  p95 `15.298s`.
- Nex ignored the reasoning-disable request in all 48 runs, returned seven
  first-pass 502 errors, and achieved only `70%` JSON/schema.
- GLM-5.2 is not selected for either route.
- Production routing is unchanged.

## Evidence

- Exact candidate IDs and parameters are preserved in
  `results/model_catalog.json`.
- Complete matrices: 96 sales and 192 system rows.
- A/B/C/D label exposure is exactly `6/6/6/6` for every sales candidate.
- Targeted review findings were fixed through negation-aware claims, explicit
  reasoning diagnostics, strict prior-evidence validation, punctuation
  normalization, and a fresh balanced blind review.
- The two final P3 harness findings were also closed with wrong-suite-tag and
  contradictory-clause regression tests; score-only regeneration preserved
  the accepted route decisions.
- Durable report:
  `docs/reports/model-battle-glm52-v4pro-2026-07-27.md`.

## Closeout

- Focused suite: `56 passed`.
- Release gates: Ruff passed; Ruff format passed over 302 files; Mypy passed
  over 162 source files; Pytest passed with `1588 passed, 19 skipped`.
- `docs-reviewed: updated` — methodology, reasoning-control behavior, review
  corrections, final rankings, limitations, and follow-up boundary are
  recorded.
- `project-index: reviewed-no-change` — no stable application entrypoint,
  route, API, integration, or ownership boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
