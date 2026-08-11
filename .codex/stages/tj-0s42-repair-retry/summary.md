# Stage tj-0s42-repair-retry

Status: accepted; `tj-0s42` closed
Base: `main` at `eaef3ab`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — first-party Python repair path
and LLM path policy, and an existing provider client. The OpenRouter model
capability list was read from the round's own stored preflight, not from a
version-sensitive external source.

docs-reviewed: updated - the handoff records the classified failure, the
counted retry, and the per-path reasoning switch. `AGENTS.md` and `README.md`
describe neither, so neither needed a change.

project-index: reviewed-no-change — no new file outside the existing modules
and no contract key moved.

## Scope

The owner questioned the premise of the previous round's finding: GLM is
stable, so `provider_unavailable` looked wrong, and a retry should have existed
anyway. Both objections were correct.

## What was actually wrong

**We never knew what failed.** Two call sites caught `Exception` and produced a
trace hardcoded to `provider_unavailable`. A transport failure, an answer the
output schema rejected, and a bug of ours were indistinguishable in the record,
so the round blamed the vendor on no evidence.

**There was no retry, and that was deliberate.** `max_attempts=1` in the path
policy, `max_attempts_override=1` at the call, and `retries=0` on the agent —
three separate places pinning one attempt. The reason was spend certainty: the
paid-call cap counts calls, so a hidden retry would have made the cap lie.

**The budget was probably the real cause.** GLM 5.2 advertises `reasoning`, and
reasoning tokens come out of the same `max_tokens`. The path allowed 800 tokens
for a complete rewritten reply plus a rationale, and reasoning was disabled for
exactly one model id in the codebase, which was not this one.

## What changed

- `classify_repair_failure` separates `provider_unavailable`,
  `judge_output_invalid` and `judge_call_failed`, and the exception class is
  carried on the trace as `error_type`.
- One bounded retry inside `review_flagged_reply` — at the runner boundary, so
  the harness journal and the paid-call cap see every attempt. Counted as
  `retries` distinctly from `fallbacks`.
- The per-call timeout is halved, 45s to 20s. The customer waits for this on
  their own turn, so the budget belongs to the whole repair: two attempts at
  20s stay inside what one attempt was already allowed. A test asserts it.
- `reasoning_enabled` is a path property, not a model id. Disabled here; the
  same vendor scores rounds elsewhere where thinking is worth paying for. The
  token budget goes to 1200.

## What is not proved

The reasoning diagnosis is a hypothesis. The stored evidence cannot separate
the causes — that was the defect being fixed. The next occurrence will name
itself.

## Verification

- Focused red: the fallback test failed on `calls == 1` when the retry landed.
  That is the contract this stage changes, and it was updated deliberately.
- 27 repair-judge tests and 35 safety tests pass.
- Protected 60-output replay: aggregate `1fc87c04…`, unchanged, so nothing in
  the deterministic reply chain moved.
- `uv run ruff check src/ tests/ scripts/`: passed.
- `uv run ruff format --check src/ tests/ scripts/`: passed.
- `uv run mypy src/`: passed over 174 source files.
- `uv run pytest tests/ -v --tb=short`: 3619 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh`: passed.

## Risks / Follow-ups / Explicit defers

No defer. A retry doubles the worst-case spend of a flagged turn, which is why
the cap counts attempts rather than flags. No paid call was made in this stage.
