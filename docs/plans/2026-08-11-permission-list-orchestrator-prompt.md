# Orchestrator prompt — `tj-mshi-permission-list`

Hand to the Codex orchestrator verbatim. `tj-mshi.1` is closed: the owner
ratified the list on 2026-08-11 as written. Claude verifies the result.

---

Target: repository `/home/me/code/treejar`, branch `main`, base commit
`11e3c59`, stage `tj-mshi-permission-list`.
Audience: the Codex orchestrator running `orchestration-bridge:orchestrator-stage`.
Runtime: Codex CLI on WSL, single repo, main-only delivery.

Documentation: no external/versioned boundary — first-party prompt and policy
text, no new dependency, no API surface, no version-sensitive behaviour.

## Goal

Run `orchestration-bridge:orchestrator-stage` for stage
`tj-mshi-permission-list` in `/home/me/code/treejar`, on `main`, base commit
`11e3c59`. Deliver epic `tj-mshi` children `.2`, `.3`, `.4` in that order, then
`.5` only if the owner authorises its paid calls in that session.

Turn the prompt from a list of things Noor may not promise into a list of things
he may. The registry that holds that list already exists and is half-built.

## Context

Read in this order: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
then `docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md` — the
audit and the seven rules, which is the contract for this stage — then
`docs/plans/2026-08-11-permission-list-plan.md` for the per-child shape, then
`docs/plans/2026-08-11-promise-types-for-ratification.md`, **which by now carries
the owner's decisions and is the only source of what goes in the registry**.
Then `docs/reports/2026-08-11-the-round-after-the-cleanup.md` for where the
baseline is. Then `bd show tj-mshi` and each child.

Beads is the only tracker. Do not open a markdown task list.

The mechanism you are completing is `COMMERCIAL_CAPABILITIES` in
`src/llm/communication_policy.py`: eight entries, four modes, rendered into the
prompt as `[AUTHORIZED COMMERCIAL CAPABILITIES]`. It is the allowlist. It is
under-populated and every instruction string in it is currently phrased as a
prohibition.

`tj-mshi.1` is the owner's ratification and is **closed**: the list was ratified
on 2026-08-11 as written, so every row in it ships with its proposed mode and
condition. Do not re-open that decision; if a row looks wrong while you work,
record the finding and continue.

## Constraints

The seven rules of the spec, non-negotiable here:

1. **P1.** The registry is the only place in the codebase that says what Noor may
   promise.
2. **P2.** Every entry states what Noor may say and under what condition. No
   entry is phrased as a prohibition. The condition is not softened; it stops
   being the sentence and becomes the qualifier.
3. **P3.** Nothing Treejar does not do gets a block of its own. It is absent from
   the list, and the redirect — what Noor says instead — is itself a listed
   permission.
4. **P4.** `tool_required` means the tool returned success in the same run.
5. **P5.** Prompt first, then measure. No deterministic commitment check in this
   stage, however obvious it looks.
6. **P6.** A refactor and a behaviour change never ride in the same measured
   round. Nothing in this stage is a refactor.
7. **P7.** Only the ratified rows go in. All 22 promises and 3 redirects are
   ratified; nothing else is. Do not infer permission from the corpus counts.
8. **P8.** Owner decision of 2026-08-11: doubt is resolved by a second model,
   not by deleting a sentence. Nothing you add here may edit customer-visible
   text without a model having written the replacement. The repair architecture
   that makes that possible is a separate epic, `tj-n7p4`; this stage neither
   builds it nor works around it.

Also in force: no existing test may be edited. Add tests by addition only.

## `tj-mshi.4`, and the one test that breaks on purpose

`tj-mshi.4` deletes `CUSTOMER_OWNED_FURNITURE_POLICY` and the `"I will check"`
prohibition.

Deleting the used-furniture block is safe and proves nothing. `tj-rt7w.1`
shipped two layers, and the guarantee is in the second: a bounded deterministic
backstop in `grounding_output.py` that does not read the prompt. **Every test in
`test_llm_grounding_output.py` must pass untouched.** If one needs touching, the
step is wrong — stop and say so.

Exactly one existing test breaks by construction:
`test_llm_prompts.py::test_customer_owned_furniture_prompt_covers_the_service_promise_family`
asserts the block is present in the built prompt. Replace it in this child with
a test asserting the same coverage against the `not_offered` entry, and say in
the artifact that this was a declared removal, not a test edited to accommodate
a move. No other existing test may be edited.

**No compensating prohibition anywhere.** If something looks like it needs one,
it is a missing registry entry: fix the entry, or record the finding and leave
it. A quiet restore turns this stage into the fourth prohibition and the report
would say the opposite. Saying so is the single most useful thing you can do
here.

The case with no backstop behind it is `tj-riim` — the recruitment routing
promise. That one rests on the permission list alone, so read its reply by eye
rather than trusting the suite.

## Verification

Per child: `uv run ruff check src/ tests/`, `uv run ruff format --check src/
tests/`, `uv run mypy src/`, `uv run pytest tests/ -v --tb=short`, and
`scripts/orchestration/run_process_verification.sh`.

At `.4` additionally: every test in `test_llm_grounding_output.py` untouched and
green, and the 31 stored raw outputs replayed through the policy chain unchanged
— `.2`–`.4` touch prompt text, not the guards.

Stage close: `check_stage_ready.py tj-mshi-permission-list`, then
`run_stage_closeout.py --stage tj-mshi-permission-list --level slice_acceptance`.
A validated artifact per closed child under
`.codex/stages/tj-mshi-permission-list/artifacts/`, and `.codex/handoff.md` at or
under 200 lines, re-pinned with
`uv run python scripts/orchestration/repin_traceability_sources.py` after every
edit to it.

## `tj-mshi.5`, and money

The round is 20 Luna calls on the frozen twenty, seed `20260810`, judged by the
orchestrator itself. **The judge is you, reading blind. Do not call a paid model
to score it.** The harness defaults to this:
`real_opening_acceptance.py run` stops after the generation arm and writes
`reading-pack.json`; you read it and feed `ingest-judgment`. Paying a second
reader takes `preflight --second-reader` and separate authority.

Ask the owner for the paid-call authority by name and amount before spending
anything. If it is not granted in that session, leave `.5` open and unstarted
and say so; that is a complete and correct outcome for this stage.

Report the result paired against 2026-08-11 — the first baseline on this judge —
with its uncertainty and per attainable ceiling, never as an absolute level. Read
it in **both** directions: criticals must not rise — dialog 28 is the honest
test there, since 789 has a backstop and would stay fixed regardless — and rules
14 and 15 are the ones that could move. If criticals reach zero and 14/15 stay at zero, the list is
too tight; record that as a finding rather than reporting a success.

## Not in scope

- Epic `tj-n7p4` — the second-model review and rewrite. Rule P8 binds you not to
  contradict it; building any part of it here is out of scope.
- The deterministic commitment check. It is step 5 of the spec, it depends on
  `tj-n7p4`, and P5 means it waits for a measured leak in any case.
- The three `tj-vz7o.12` defects that reproduced on 2026-08-11.
- `tj-rt7w.14`, now blocked on `tj-n7p4.2` rather than on a validator we write.
- Retiring the deterministic routes.
- Any change to the rubric, the applicability map, or the scoring rulers. Frozen.

## Delivery

Local commits on `main`, one per child. No push, PR, merge, deploy, production
or staging mutation, model-configuration change, or real-user message. Keep
corpus text outside the repository; tracked evidence carries `dialog_id` and
integers only.

## Output

One tracked artifact per closed child under
`.codex/stages/tj-mshi-permission-list/artifacts/`, plus
`.codex/stages/tj-mshi-permission-list/summary.md` stating per child: what
changed, which gate proved it, and — for `.4` — that
`test_llm_grounding_output.py` passed untouched and which single test was
removed and replaced, in those words. Update `.codex/handoff.md` to
current state within its 200 lines and re-pin it.

Report back: current state, what each child changed, the verification actually
run with its numbers, whether `.4`'s stop rule fired, whether `.5` ran and under
what authority, and anything left open with the reason.

Do not report a child complete on the strength of the suite alone. For `.4`,
read the recruitment reply by eye: it is the one the suite cannot judge.
