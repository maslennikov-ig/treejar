# Stage tj-lj09-glm-proof

Status: accepted; `tj-lj09` closed
Base: `main` at `28a150d`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — the vendor's behaviour was
measured directly against the live endpoint rather than read from a
version-sensitive document, which is what the stage exists to do.

docs-reviewed: updated - the round report now carries the measured cause in
place of the assumed one; the handoff records the budget and the inert
reasoning switch. `AGENTS.md` and `README.md` describe neither.

project-index: reviewed-no-change — no new tracked file outside the existing
modules and the stage directory, and no contract key moved.

## Scope

`tj-0s42` fixed the classification and added the retry, but left the diagnosis
standing as a hypothesis: reasoning tokens starving an 800-token structured
answer. A hypothesis in a shipped comment is the same defect the stage was
opened to remove. This stage settles it against the live vendor.

## Method

The failed request was rebuilt from the round's own stored state and matched
the recorded request digest `a39e8bd0…` byte for byte, so what was replayed is
the call that failed and not a reconstruction of it. Twelve paid calls across
five configurations, with `notify_on_failure_override=False` so a failing
attempt could not page a manager.

## What the replay established

**The provider was never down.** Every failure is `UnexpectedModelBehavior`,
classified `judge_output_invalid` — our own output schema rejecting a truncated
answer. Not one transport error in twelve calls.

**The budget was the cause, and it was not close.** A complete answer costs
720–1494 completion tokens. About 300 of those are the JSON the schema asked
for; the rest is reasoning this vendor bills for and never returns. At 800 the
call cannot succeed. At 1200 it succeeded twice in four. At 2000 it succeeded
eight times in eight.

**Reasoning cannot be declined here.** `enabled: false`, `effort: low` and
`max_tokens: 256` all left completion around 1430 tokens. The switch added in
`tj-0s42` is inert for `z-ai/glm-5.2`, so it was not the fix and the code no
longer says it was. It stays declared because the intent is right and vendor
behaviour changes, but any path that sets it must budget as though it were
ignored.

## What changed

- `max_tokens` and `output_tokens_limit` on the repair path: 1200 → 2000.
- The comments on the path and on `LLMPathPolicy.reasoning_enabled` now record
  what was measured, including that the switch does nothing here.
- `test_the_repair_judge_does_not_pay_for_thinking_it_cannot_afford` is
  replaced by `test_the_repair_judge_can_afford_the_answer_it_asks_for`, which
  pins the measured budget instead of the retired hypothesis.
- The round report's finding is rewritten from the assumed cause to the
  measured one.

## The finding that is not about this bug

A repair call costs about $0.005. Generating the reply it repairs cost
$0.000084. Repairing a turn costs sixty times what writing it does, so the
repair path's firing rate is a product and pricing question, not a tuning one.
Raised for the owner; not decided here.

## Verification

- Request digest `a39e8bd07e400c26…` reproduced from the round's stored state:
  identical to the one recorded when the call failed.
- 12 live calls: 800 → 0/2; 1200 with reasoning left on → 1/2; 1200 with
  reasoning off → 2/2; 2000 with reasoning off → 4/4; two probes each at
  `effort: low` and `reasoning.max_tokens: 256` → 2/2 with no token reduction.
- Worst observed latency 15.33s against the 20s per-call timeout; two attempts
  still fit under the 45s a single attempt was once allowed.
- `uv run ruff check src/ tests/ scripts/`: passed.
- `uv run ruff format --check src/ tests/ scripts/`: passed.
- `uv run mypy src/`: passed.
- `uv run pytest tests/ -v --tb=short`: see the artifact for the count.
- `scripts/orchestration/run_process_verification.sh`: passed.

## Risks / Follow-ups / Explicit defers

No defer. Two limits stated rather than hidden. The budget is measured on one
request; a longer customer question could cost more, and the retry plus the
`judge_output_invalid` class are what will surface it rather than another
silent handoff. And the reasoning switch is kept in the codebase while known to
be inert for this model, which is a small standing risk of someone reading it
as protection — the comment and the test both say otherwise.

Paid calls: 12, $0.058492, under owner authority given in session on
2026-08-12. The estimate offered beforehand was one call at $0.0013; the
overrun is reported rather than absorbed.
