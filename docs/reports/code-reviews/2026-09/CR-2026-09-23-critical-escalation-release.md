# Code Review: Critical-only escalation release

**Date**: 2026-09-23  
**Scope**: `codex/critical-escalation-only` against `origin/main`, including final corrections  
**Verdict**: PASS after resolving four high-impact false-positive paths

## Issues found and fixed

1. `src/llm/escalation_policy.py`: an old approved quotation plus an unrelated
   new "yes" could trigger order handoff. A pending quotation could also expose
   handoff before acceptance was recorded. Manager handoff now requires approved
   quote state plus explicit current acceptance or a successful current-turn
   `record_customer_intent` call. Pending quote acceptance is recorded first.
2. `src/llm/escalation_policy.py`: "I need a refund policy" and Arabic questions
   about refund terms matched refund-incident keywords. Policy-information
   phrases no longer trigger an incident handoff.
3. `src/llm/escalation_policy.py`: an empty current message could reuse an old
   human request from conversation history. Only current customer text now
   supplies critical escalation evidence.
4. `src/llm/engine.py`: repeated calls during an already active handoff could
   create duplicate rows and manager alerts. The tool is now hidden and direct
   execution exits without notifying again.

All four are covered by focused regressions. The existing `tj-bltw` Bead was
reopened for these corrections; no separate unresolved review task remains.

## Positive patterns

- One deterministic policy gates tool exposure, direct tool execution, and
  exhausted-repair fallback. The model cannot override the decision by choosing
  a more urgent reason or escalation type.
- Accepted-quotation handoff follows the recorded quote state; ordinary sales,
  catalog gaps, and pre-side-effect failures continue autonomously.
- The manager guide now reflects the live critical-only rules rather than its
  superseded list of 18 broad triggers.

## Risk and validation

This changes shared conversation behavior but has no schema, migration,
dependency, permission, or public API change. The CI deploy remains restricted
to the existing test-only inbound channels and worker mode. Recovery is the
existing app-only rollback path; no customer data reset is part of this change.

- `git diff --check`: PASS
- `uv run ruff check src/ tests/`: PASS
- `uv run ruff format --check src/ tests/`: PASS
- `uv run mypy src/`: PASS (181 source files)
- Focused escalation, intent, engine, and repair tests: PASS (779 tests)
- `scripts/orchestration/run_process_verification.sh`: PASS

CI and production rollout results must be recorded separately after push; this
local review alone is not evidence of a deployed runtime.
