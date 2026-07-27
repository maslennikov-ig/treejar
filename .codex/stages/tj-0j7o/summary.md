# Stage tj-0j7o Summary

Updated: 2026-07-27
Status: accepted; comparative choices recorded, production unchanged
Branch: `main`
Beads: `tj-0j7o`

## Boundary

One production-safe synthetic evaluation boundary selects independent winners
for Noor's core sales and fast/system routes. Paid OpenRouter calls are
approved; production routing, customer traffic, and external business systems
remain unchanged.

## Streams

| Stream | Owner | Decision | Reason |
| --- | --- | --- | --- |
| Official capability and model-ID verification | root/docs specialist | parallel read-only | Version-sensitive provider facts benefit from isolated authoritative research |
| Shared harness, cases, scoring, and tests | root | local | One scoring contract must remain consistent across both battles |
| Sales and system inference execution | root | sequential | Shared API client and latency measurement must avoid cross-suite contention |
| Methodology/result review | targeted read-only reviewer | after evidence | Route decisions warrant one specialist correctness lens |

## Scope Ledger

- Core sales: `z-ai/glm-5` versus
  `deepseek/deepseek-v4-flash`.
- Fast/system: `nex-agi/nex-n2-mini` versus
  `deepseek/deepseek-v4-flash`.
- Two repetitions per case with fixed synthetic evidence.
- Correctness gates precede weighted quality and latency.
- No production model switch in this stage.

## Accepted Result

- Core sales comparative choice: keep `z-ai/glm-5`.
  - weighted `92.879` versus DeepSeek `85.395`;
  - blind quality `91.33%` versus `91.00%`;
  - p95 `11.229s` versus `21.962s`.
- Fast/system comparative choice: prefer
  `deepseek/deepseek-v4-flash` with reasoning disabled and validation/fallback.
  - JSON/schema `97.5%` versus Nex `72.5%`;
  - semantic field accuracy `71.84%` versus `64.08%`;
  - p95 `14.804s` versus `5.553s`.
- Strict outcome for both routes is `no_safe_replacement`; comparative choices
  do not authorize an unguarded production switch.
- The removed `xiaomi/mimo-v2-flash` remains excluded.
- No secret value, customer identifier, or production mutation is present in
  the benchmark evidence.

## Evidence

- Harness: `scripts/model_battle.py`, `scripts/model_battle_cases.py`.
- Focused tests: `tests/test_scripts_model_battle.py`.
- Report: `docs/reports/model-battle-2026-07-27.md`.
- Raw and derived results: `.codex/stages/tj-0j7o/results/`.
- Stream artifact: `.codex/stages/tj-0j7o/artifacts/tj-0j7o.md`.
- Follow-ups: `tj-j13d` for guarded DeepSeek fast-route hardening and
  `tj-b93r` for the GLM-5 weak-catalog grounding guard.

## Closeout

- Release gates: Ruff passed; Ruff format passed over 302 files; Mypy passed
  over 162 source files; Pytest passed with `1569 passed, 19 skipped`.
- Focused benchmark suite: `37 passed`.
- E2E/smoke: not applicable — no runtime, route, deploy, or customer-flow
  mutation occurred; the authorized external work was the completed synthetic
  OpenRouter benchmark itself.
- `docs-reviewed: updated` — design, plan, durable report, stage summary, and
  handoff record final methodology, evidence, limitations, and next boundary.
- `project-index: reviewed-no-change` — no stable entrypoint change is planned.
- `graph-reviewed: no-change-needed` — Graphify is not configured and the graph
  report is absent.
