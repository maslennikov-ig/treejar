# Codex correction prompt — unblock the `tj-ee5f` paid battle

**Date:** 2026-08-04
**Target runtime:** Codex CLI in this repository
**Kind:** handoff (cross-runtime, manual)
**Supersedes:** `2026-08-03-codex-tj-ee5f-remediation-handoff.md`, whose round is
complete and verified.

## Why this round exists

The review remediation round is genuinely done: `R-01`..`R-16`, `R-19`, `R-20`
are implemented with focused tests, `R-17` is a bounded recorded defer, and all
gates are green (`2804 passed, 19 skipped`). Four things nevertheless stop the
paid battle from starting, and none of them are a product defect:

1. Beads cannot reach `.13`. It is blocked by `.7`/`.8`, whose own notes say
   they close only after a release-bound production retest — and that retest is
   `.1`, which is blocked by `.13`. No formal cycle, no workable order.
2. The free metadata/capability/cost preflight has not been rerun against the
   repaired harness. Plan Task 6 step 1 requires it and it costs nothing.
3. `RequestCostBudget.reserve_request` raises an uncaught `RuntimeError` when a
   worst-case reservation would cross the USD 1 cap. GLM-5.2's recorded
   worst-case estimate is USD 1.121494, so the most likely single outcome of
   launching today is the whole round aborting mid-run with an incomplete
   matrix.
4. One `finish_reason=length` adds the candidate to `stopped_models` and drops
   its rows from the blind comparison, so a `TRUNCATED` response eliminates the
   candidate from the round. The owner ruled that `TRUNCATED` is a harness
   budget event, not a model quality failure; elimination is stricter than that
   and biases toward the terse incumbent.

## Prompt

```text
Target: Codex gpt-5.6 orchestrator
Audience: fresh Codex session, repo `/home/me/code/treejar`

Goal: Make the sealed model battle launchable. The remediation round is
verified; this round removes four launch blockers and stops before spending.

Success criteria:
- `bd ready` reaches `tj-ee5f.13` under an order that survives `bd dep cycles`,
  with the production-retest obligation of `.7`/`.8` recorded where `.1` owns it.
- The free metadata, capability, and cost preflight is rerun on the repaired
  harness; its execution order, per-model reservations, and capability statuses
  are published as tracked evidence.
- Exhausting a per-model cap ends that candidate with a recorded reason instead
  of raising out of the run loop; already-written rows stay valid evidence.
- A `TRUNCATED` response no longer removes a candidate from the round; it is
  recorded, unscored, and the candidate continues, per the owner's budget rules.
- Focused tests cover cap exhaustion mid-matrix and a truncation that does not
  eliminate.

Context:
- Branch `codex/tj-ee5f-quality-model-battle` at `ea35d44`; gates green there.
- Review findings and owner budget rules:
  `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`.
- Blockers with file evidence: `scripts/model_battle.py` `reserve_request`
  cap raise, and the `stopped_models` truncation path in the round loop.
- Repo contract: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`.

Constraints:
- Write zone: `scripts/`, `tests/`, `.codex/stages/tj-ee5f/`, `.codex/handoff.md`,
  `docs/superpowers/`. Leave `src/`, `docs/client/`, and untracked files alone.
- Never raise a per-model cap and never widen the shared allowance.
- Preserve frozen `AC-01..AC-30` and its digest.
- `tj-ee5f.13.9` stays a bounded defer; do not reopen product-runtime `R-17`.

Ask the owner when two outcomes stay plausible and the answer changes
acceptance — notably whether a cap-exhausted or truncation-affected candidate
is ranked on partial evidence or withdrawn. Ask separately, naming the exact
action, before any paid OpenRouter call, model-config change, push, deploy, or
production readback. The metadata and pricing preflight is free and needs no
separate authority.

Output: behavior first — what a launch would now do differently, the command
that shows it, and the published preflight order and reservations; then Beads
state; gate output and diffs last.

Stop: Stop once the battle is launchable and report the preflight numbers. Do
not run the paid battle, change model config, push, deploy, or touch production.
```

## Notes for the launcher

- Blocker 1 is a process decision the orchestrator can make from the spec: `.1`
  already owns winner-only production acceptance, so the retest obligation
  belongs there and `.7`/`.8` can close on local-remediation scope.
- Blockers 3 and 4 may change what counts as an acceptable round. The prompt
  requires the orchestrator to ask rather than default.
- Deliberately out of scope, all non-blocking and already reviewed: the `pstdev`
  noise rule mixing between-case variance, `parallel_tool_calls=false` for the
  only candidate that supports parallel calls, and the missing system-prompt
  digest needed later by the winner acceptance manifest.
