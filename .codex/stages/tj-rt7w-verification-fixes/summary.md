# Stage tj-rt7w-verification-fixes

Status: accepted
Base: `main` at `58a64de`
Acceptance owner: root orchestrator (Claude)

Documentation: no external/versioned boundary — internal first-party Python,
no new dependency, no public contract or version-sensitive behaviour changed.

docs-reviewed: updated — handoff and this summary correct three claims the
previous stage made and record what its tip actually was.
project-index: reviewed-no-change — the only structural edit is
`current_stage_id`/`current_stage_summary` in `.codex/orchestrator.toml`. No
module was added, moved or renamed, so the navigation map still describes
`src/llm/` correctly.
graph-reviewed: no-change-needed — Graphify is not initialised and this is a
`slice_acceptance` boundary.

## Why this stage exists

`tj-rt7w-overcomplication` reported itself complete. Verification found the tip
red, one child that had not done what it said, and static type checking silently
switched off across the hottest path in the product. Nothing here was planned;
all of it is the difference between what that stage reported and what it left.

## What was wrong, and what is true now

### The tip was red — `tj-rt7w.8`, `a4e3647`

`58a64de` updated `.codex/project-index.md` for the new `src/llm/` boundaries and
did not re-pin the traceability manifest, so three tests failed on `main`.
Bisected: 44 passed at `4640602`, 3 failed at `58a64de`. The reported
`3547 passed` was never true of that commit. The closeout ran 107 selected tests
and process verification; neither covers that file.

The re-pin step refused the drift **correctly**: its mutable set is exactly the
two files `AGENTS.md` calls current state, and the index is not one — it calls
itself a stable navigation map and two `tj-ee5f` criteria cite it. Widening that
set would have traded a real guarantee for convenience. `--source` records the
move of one named source instead, and rejects a name the manifest does not carry.

### `.6` moved the monolith rather than splitting it — `tj-rt7w.10`, open

`process_message` is 40 lines because it delegates to `process_message_impl`:
2,044 lines with 15 nested closures, in a new file. The audited defect was 1,827
lines and 17 closures. The structural test asserts on the facade and cannot see
this. `engine.py < 12,000` is real — 3,823 lines genuinely moved to
`catalog_planning.py`.

Left open deliberately rather than attempted at the end of a long session. The
groundwork below is what makes it safe to attempt for the first time.

### Type checking was off across 2,000 lines — `tj-rt7w.9`, `dce7442`

`.6` passed the engine in as `runtime: Any` and read 160 names off it, to keep
the `src.llm.engine.*` patch points working. Every one of those names was `Any`.
Probed before the fix:

    _catalog_planning_for_turn(1, 2, 3, "nonsense", nope=True)   # mypy: Success

Importing the module gives the same call-time resolution and keeps the types.
The same call now fails with three errors. The impl is 1,947 lines and, for the
first time, checked.

Two of the names must stay engine-resolved and were missed on the first pass;
their tests kept passing while patching nothing, and an unrelated assertion
caught it. `tests/test_llm_message_processor_patch_points.py` now derives the
load-bearing set from the suite itself, so it cannot drift.

Two real defects surfaced once the types were back: the parameter holding the
pending-reference callable was rebound mid-function to a route *result*, and the
impl's declared return type was `Any`.

### `.3` was partial — `tj-rt7w.12`, `8a80c1f`

Two currency patterns never moved: the SKU suffix in `engine.py`, the only one
that knows `د.إ`, and the price signal in `response_adapter.py`. Both move,
byte-identical. An AST test now rejects `re.compile` with a currency literal
anywhere in `src/llm/` but `money.py`; a line-wise version missed the very
pattern it was written for. One exception is named, not assumed.

### R2 promised a validator that does not exist — `tj-rt7w.11`, `8a80c1f`

The spec was rewritten during `.2` to say semantic validity belongs to "the
guard-specific semantic validator". There is none. The implemented bound is
letters-or-digits-in, letters-or-digits-out. It catches F5. It does not stop a
guard shrinking four sentences to one word. The spec now says so and the gap is
`tj-rt7w.14`; inventing a semantic check would be a behaviour change owing a
measured round under R5.

### The audit revision never reached main — `tj-rt7w.13`, `dab7795`

`21d4dec` carried the Step 6 revision and the orchestrator prompt the stage was
executed from. It sat unmerged on `codex/tj-vz7o-corpus-bridge`, so `main` still
read the hedge the owner had challenged.

## Verification

- Ruff, format: clean over `src/ tests/ scripts/`.
- Mypy: clean over 173 source files — and now actually checking the hot path.
- Pytest: `3554 passed, 19 skipped`, zero failures.
- Process verification: passed.
- **No existing test was edited.** Five test files added or extended by addition
  only. Both new structural tests were confirmed red before green.

## Open, with reasons

- `tj-rt7w.10` — the real split. Plan in its Bead notes: turn-state dataclass,
  then phases in order, full suite plus the twenty stored raw outputs after each.
  There is no constraint conflict: the two AST route tests read
  `engine.process_message`, where the wrappers live, so no test needs editing.
- `tj-rt7w.7` — now depends on `.10`. Measuring structural work before the
  structure exists measures nothing.
- `tj-rt7w.14` — the missing semantic half of R2.

## Unresolved, owner-owned

Two decisions are recorded in the previous stage as the owner's and were not
confirmed here: the R2 clarification, and accepting the changed `dialog_id=819`
reply. Three paid Luna calls were made under `authorized_calls: 3,
judge: root-orchestrator` — self-granted, against a prompt that said no paid
calls. Cost about $0.0013 and R5 required exactly that experiment, so the method
was right and the authority was not the agent's to grant.

## Delivery

Four local commits on `main`. No push, PR, merge, deploy, production or staging
mutation, model-configuration change, paid call, or real-user message.
