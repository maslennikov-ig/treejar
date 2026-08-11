# Stage tj-t6ug-selling-turn-declarations

Status: accepted; `tj-t6ug` closed
Base: `main` at `1754544`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — first-party Python response
policy and protected stored outputs. No new dependency, no API surface, no
version-sensitive behaviour.

docs-reviewed: updated - the handoff now records three guard modes instead of
two, names which guard is which, and carries the unmeasured multi-turn limit
as an explicit defer. `AGENTS.md` and `README.md` describe neither the guard
contract nor the replay, so neither needed a change.

project-index: reviewed-no-change — the only edit to `.codex/orchestrator.toml`
moves `current_stage_id` and `current_stage_summary` to this stage. No key was
added, removed or repurposed, and no directory changed shape.

## Scope

One bounded fix found by auditing `tj-n7p4`. The three selling-turn guards
shared a single declaration, so the bundle took its strictest member's mode.
Split them, give the two that reduce an executable proof, and make the
protected replay a tracked entry point instead of a hand-run command.

## Execution

Root-owned. One file of guard logic, one of declarations, three test modules,
one new script. No subagent, no paid call, no external documentation lookup.

## What was wrong

`apply_selling_turn_guard` composed `collapse_question_form`,
`refuse_to_chase_the_name` and `carry_the_company_question` behind the name
`selling_turn`, declared `REMOVING` under D1. Two consequences, reproduced on
`1754544` before any change:

- `carry_the_company_question` only ever appends. Declared with the bundle it
  was suppressed and raised a removal flag, which under `.3` spends a
  second-vendor call on a turn where nothing was removed.
- `collapse_question_form` stopped folding. A reply asking three questions
  reached the customer whole, and the only thing between them and a form was a
  judge that under D3 may approve it. That fold was earned by measurement on
  2026-08-09: S01 turn 2 asked five things in a numbered list and R04 turn 2
  asked four, in a median conversation two messages long.

Both paths are non-first-turn. The frozen twenty and the protected replay are
first-turn openings, so neither could see either one. The `tj-n7p4.2`
invariant `customer-visible-output-unchanged` was proved on evidence that
cannot exercise this guard.

## The third mode

`GuardMode.REDUCING`, on the line where the customer actually stands. A
surplus question is the reply's own ask and costs them nothing; anything else
is the answer they came for. A reducing guard may drop the first and may not
touch the second, and `only_asks_were_dropped` proves that at runtime: the
candidate's words are a subsequence of the original, so nothing is invented,
and every content word survives in order. When the proof fails the guard
behaves exactly like `REMOVING` — no edit, one flag, and the judge reads it.

D1 is not weakened. It is enforced on the customer's loss rather than on the
character count, and it is enforced by a predicate rather than by a label.

## Acceptance boundary

No customer-visible content is removed unless a deterministic replacement is
proved, a reduction proof holds, or a model wrote and re-classified the
repair. Nothing spends a judge call on a turn where nothing was removed.

## Verification

- Focused red: the declaration test failed on `question_form` missing from
  `RESPONSE_GUARD_DECLARATIONS` before the split.
- Focused green: 11 declaration-contract tests, 4 policy-guard tests, 34
  sales-turn-guard tests, 4 replay-script tests.
- Behaviour reproduction: five non-first-turn shapes read by hand before and
  after — additive question, inline question form, ask list, repeated name
  request, and a first turn left untouched.
- Protected 60-output replay, run at `1754544` and at the fix in a temporary
  worktree: identical aggregate digests under both conventions,
  `68c926ed…` for the fixture convention and `1fc87c04…` for raw model text.
  One `grounding_output` flag on dialog 789 in both, which is `tj-n7p4.3`'s
  own recorded change and not this stage's.
- `uv run ruff check src/ tests/ scripts/`: passed.
- `uv run ruff format --check src/ tests/ scripts/`: passed.
- `uv run mypy src/`: passed over 174 source files.
- `uv run pytest tests/ -v --tb=short`: 3604 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh`: passed.

## Declared test replacement

`test_selling_turn_guard_needs_only_explicit_state` asserted the composition
through `apply_selling_turn_guard`. Declaring each guard separately removed
that composition, so the test is replaced by
`test_selling_turn_guards_need_only_explicit_state`, which asserts the same
behaviour through `render_reply`. That end-to-end path is the coverage whose
absence let the bundle's mode go unnoticed, so this is a declared replacement
rather than a test edited to accommodate a change.

Three assertions in `tests/test_llm_response_guard_declarations.py` changed
with the contract they encode: `selling_turn` is no longer a declaration.

## Risks / Follow-ups / Explicit defers

- The two reducing guards remain unmeasured on live multi-turn traffic. The
  frozen set is first-turn only, so no round in this project has ever
  exercised them. Recorded as a limit of the instrument, not as a defer: the
  fix restores the behaviour that was measured on 2026-08-09 rather than
  introducing a new one.
- The `tj-mshi.4` replay fixture digests `generation.content`, which in the
  round recorded after the harness began shipping its output is already past
  the guards. The fixture still detects any change to the chain and is kept;
  `--convention raw` is the honest reading and a correct baseline is written
  at `tj-t6ug-replay-baseline.json`.
