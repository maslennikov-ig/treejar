# Noor Model Battle Implementation Plan

**Goal:** Produce reproducible, evidence-backed winners for Noor's core sales
and fast/system model routes without changing production.

**Approach:** Build one synthetic OpenRouter harness with shared request,
latency, retry, validation, and evidence contracts. Run the sales and system
suites sequentially with two repetitions, then complete a blinded qualitative
review and publish a durable comparison report.

**Non-goals:** Production routing/config changes, real customer data or
messages, Zoho/Wazzup mutations, and cost optimization.

## Scope ledger

- Core sales GLM-5 versus DeepSeek V4 Flash -> Task 1.
- Fast/system Nex-N2-Mini versus DeepSeek V4 Flash -> Task 1.
- Fixed synthetic cases, blinded evidence, hard gates, and route-specific
  winners -> Task 1.
- No production switch -> closeout gate.

### Task 1: Reproducible two-route model battle

**Files:** `scripts/model_battle.py`, `scripts/model_battle_cases.py`,
`tests/test_scripts_model_battle.py`, `.codex/stages/tj-0j7o/results/`,
`docs/reports/model-battle-2026-07-27.md`, and stage/handoff files.

**Boundary:** Root owner; synthetic evaluation and OpenRouter paid calls;
rollback is deletion of generated local evidence because no production state
changes.

**Interfaces:** Consumes the existing OpenRouter key and repository prompt/schema
contracts; produces JSONL evidence, deterministic scores, blinded review input,
and one route-level recommendation per battle.

**Verification lane:** `tdd-required` — the work introduces parsing, schema
validation, scoring, percentile calculation, and winner-selection behavior.

- [x] Add failing tests for case validation, JSON/schema scoring, semantic
  scoring, latency aggregation, hard gates, blinding, and winner selection.
- [x] Implement the complete harness and fixed synthetic cases.
- [x] Verify official candidate availability and supported parameters before
  paid calls.
- [x] Run the sales suite twice per case, preserving raw evidence and timings.
- [x] Run the system suite twice per case, preserving raw evidence and timings.
- [x] Record blinded qualitative sales review before unblinding.
- [x] Generate the durable report and select winners only through the accepted
  gates.
- [x] Run focused tests, Ruff/format/Mypy, process verification, stage closeout,
  documentation review, and safe delivery.
