# Orchestrator prompt — permissions, then judged repairs

Hand to the Codex orchestrator verbatim. Two stages, run **in sequence**: the
second does not start until the first is accepted. Claude verifies the result.

---

Target: repository `/home/me/code/treejar`, branch `main`, base commit
`9938005`.
Audience: the Codex orchestrator running `orchestration-bridge:orchestrator-stage`.
Runtime: Codex CLI on WSL, single repo, main-only delivery.

Documentation: no external/versioned boundary — first-party Python, prompt and
policy text, and one provider call through an existing client. No new
dependency, no API surface, no version-sensitive behaviour.

## Goal

Two owner decisions of 2026-08-11, in this order and not in parallel.

**Stage 1, `tj-mshi-permission-list`.** Turn the prompt from a list of things
Noor may not promise into a list of things he may. Deliver epic `tj-mshi`
children `.2`, `.3`, `.4`, then `.5`.

**Stage 2, `tj-n7p4-judged-repairs`.** Stop the code from deleting the
customer's reply on its own. Deliver epic `tj-n7p4` children `.1`, `.2`, `.3`,
`.6`, `.4`, then `.5`.

The repo contract allows one active implementation stage. Accept stage 1 —
`check_stage_ready.py` and `run_stage_closeout.py` both green — before opening
stage 2. They touch the same reply path, so running them together would make
either one unmeasurable.

## Context

Read in this order: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`.

Then for stage 1:
`docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md` — the audit and
rules P1–P8, the contract for that stage;
`docs/plans/2026-08-11-permission-list-plan.md` — the per-child shape;
`docs/plans/2026-08-11-promise-types-for-ratification.md` — **ratified by the
owner on 2026-08-11 as written, and the only source of what goes in the
registry**.

Then for stage 2:
`docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md` —
the audit and rules D1–D5.

And `docs/reports/2026-08-11-the-round-after-the-cleanup.md` for where the
measurement baseline is. Then `bd show tj-mshi`, `bd show tj-n7p4`, and each
child.

Beads is the only tracker. Do not open a markdown task list.

## Paid calls: authorised in advance, and the two judges are not the same

The owner granted this on 2026-08-11 before the work started. **You do not need
to ask again**, and you may not exceed it.

| | authorised | expected |
|---|---|---|
| `tj-mshi.5` | 20 Luna generation calls | ~$0.005 |
| `tj-n7p4.5` | 20 Luna generation calls | ~$0.005 |
| `tj-n7p4`, repair judge | ≤25 second-vendor calls for the whole stage, including any spent verifying the judge path in `.3` | ~$0.03 |
| ceiling, both stages | **$2.00** | ~$0.05 |

**The scoring judge is you, reading blind, and it is free.** That is the owner's
standing decision and the harness already defaults to it:
`real_opening_acceptance.py run` stops after the generation arm and writes
`reading-pack.json`; you read it and feed `ingest-judgment`. **Never pass
`--second-reader`.** In the 2026-08-10 round a paid scoring model took $0.175 of
the $0.18 spent; that is the mistake this rule exists to prevent.

**The repair judge is a different thing.** It is the second-vendor model that
stage 2 builds: it fires only when a check raises a flag, roughly once in sixty
openings on the stored evidence, and it answers *approve*, *correct*, or
*cannot-fix*. It is paid, it is inside the budget above, and it is not the
scoring judge. Do not let one become the other.

If a stage would exceed its authorisation, stop and report rather than trimming
the round to fit.

---

# Stage 1 — `tj-mshi-permission-list`

## What you are completing

`COMMERCIAL_CAPABILITIES` in `src/llm/communication_policy.py`: eight entries,
four modes, rendered into the prompt as `[AUTHORIZED COMMERCIAL CAPABILITIES]`.
It is already the allowlist. It is under-populated against what sellers actually
promise, and every instruction string in it is currently phrased as a
prohibition. Fill it, turn it round, delete what it subsumes, measure.

`tj-mshi.1` is closed: all 22 promises and 3 redirects are ratified with their
proposed modes and conditions. Do not re-open that decision; if a row looks
wrong while you work, record the finding and continue.

## Constraints

1. **P1.** The registry is the only place in the codebase that says what Noor
   may promise.
2. **P2.** Every entry states what Noor may say and under what condition. No
   entry is phrased as a prohibition. The condition is not softened; it stops
   being the sentence and becomes the qualifier.
3. **P3.** Nothing Treejar does not do gets a block of its own. It is absent
   from the list, and the redirect — what Noor says instead — is itself a listed
   permission.
4. **P4.** `tool_required` means the tool returned success in the same run.
5. **P5.** Prompt first, then measure. No deterministic commitment check in this
   stage, however obvious it looks.
6. **P6.** A refactor and a behaviour change never ride in the same measured
   round. Nothing in this stage is a refactor.
7. **P7.** Only the ratified rows go in.
8. **P8.** Nothing you add here may edit customer-visible text without a model
   having written the replacement. That architecture is stage 2; this stage
   neither builds it nor works around it.

No existing test may be edited. Add by addition only.

## `tj-mshi.4`, and the one test that breaks on purpose

`.4` deletes `CUSTOMER_OWNED_FURNITURE_POLICY` and the `"I will check"`
prohibition.

Deleting the used-furniture block is safe and proves nothing. `tj-rt7w.1`
shipped two layers and the guarantee is in the second: a bounded deterministic
backstop in `grounding_output.py` that does not read the prompt. **Every test in
`test_llm_grounding_output.py` must pass untouched.** If one needs touching, the
step is wrong — stop and say so.

Exactly one existing test breaks by construction:
`test_llm_prompts.py::test_customer_owned_furniture_prompt_covers_the_service_promise_family`
asserts the block is present in the built prompt. Replace it in this child with
a test asserting the same coverage against the `not_offered` entry, and say in
the artifact that this was a declared removal, not a test edited to accommodate
a move.

**No compensating prohibition anywhere.** If something looks like it needs one,
it is a missing registry entry: fix the entry, or record the finding and leave
it. A quiet restore turns this stage into the fourth prohibition and the report
would say the opposite.

The case with no backstop behind it is `tj-riim`, the recruitment routing
promise. It rests on the permission list alone, so read its reply by eye rather
than trusting the suite.

## `tj-mshi.5`

Frozen twenty, seed `20260810`, paired against **2026-08-11** — the first
baseline on this judge, so this is the first round in the project with a valid
paired comparison. Read it in **both** directions:

- criticals must not rise. Dialog 28 is the honest test there, since 789 has a
  backstop and would stay fixed regardless;
- **rules 14 and 15 score zero today** and a permission list is the thing that
  could move them.

If criticals reach zero and 14/15 stay at zero, the list is too tight. Record
that as a finding, not a success.

---

# Stage 2 — `tj-n7p4-judged-repairs`

Start only after stage 1 is accepted.

## The measured facts you are working from

Audited on the 60 stored replies of the three measured rounds. Do not re-derive
them; do not contradict them without re-measuring.

- A guard removes a sentence from **28 of 60 replies**. It is the opening guard.
- All 31 removed sentences are the model's own greeting or identity line, which
  the deterministic anchor replaces verbatim. **Nothing is lost.**
- `grounding_output` removes and replaces nothing: **1 reply in 60, 2 sentences.**
- The other four guards did not fire on this set. That is a property of a
  first-turn corpus, not evidence that they are safe.

## Constraints

1. **D1.** No customer-visible content is removed without a replacement. A guard
   declares itself *replacing* — and a test holds that what it removes is
   covered by what it adds — or *removing*, in which case it may not edit the
   text at all and raises a flag instead.
2. **D2.** A flag is a question, not a verdict. A deterministic check may only
   classify.
3. **D3.** The judge answers approve, correct, or cannot-fix, and **may
   approve**. Approvals over a flag are counted separately.
4. **D4.** The fallback is a manager handoff, never a deletion.
5. **D5.** R2 still binds. A correction that empties the reply is rejected, and
   a correction is re-classified before it is sent: a rewrite that introduces a
   new violation is a failure, not an improvement.

No existing test may be edited. Guard sources not named by a child stay
byte-identical.

## Two ways this goes wrong, and they are opposite

**A model call on half of all turns.** The opening guard fires on every first
turn and removes a duplicate identity line 28 times in 60. It is *replacing*. It
stays deterministic and never reaches the judge. If you end up consulting a
model on 47% of replies, D1's distinction has been lost and the stage is wrong.
Say so.

**A judge nobody can overrule, or one that never disagrees.** D3 starts
permissive on purpose. Do not hard-code a class of flag as non-overridable; that
is a question for `.5` to measure. If `.5` shows every flag approved, the
detector is wrong or the judge is not reading — both are findings.

---

# Verification, both stages

Per child: `uv run ruff check src/ tests/`, `uv run ruff format --check src/
tests/`, `uv run mypy src/`, `uv run pytest tests/ -v --tb=short`, and
`scripts/orchestration/run_process_verification.sh`.

Stage 1, at `.4`: every test in `test_llm_grounding_output.py` untouched and
green, and the 31 stored raw outputs replayed through the policy chain
unchanged — `.2`–`.4` touch prompt text, not the guards.

Stage 2, at `.1` and `.2`, which are behaviour-preserving: replay the 60 stored
raw outputs of the three rounds through the chain and confirm the rendered text
is unchanged. At `.3` and `.6`, which change behaviour: the same replay must
show a change on exactly the turns where a flag fired, and nowhere else. The
stored runs are under
`<git-common-dir>/codex-orchestration/corpus-bridge/`. Keep the text there.

Stage close, each stage: `check_stage_ready.py <stage-id>`, then
`run_stage_closeout.py --stage <stage-id> --level slice_acceptance`. A validated
artifact per closed child, and `.codex/handoff.md` at or under 200 lines,
re-pinned with `uv run python
scripts/orchestration/repin_traceability_sources.py` after every edit to it.

# Not in scope

- The deterministic commitment check. It is step 5 of the permission spec, it
  depends on stage 2's machinery, and P5 means it waits for a measured leak.
- The three `tj-vz7o.12` defects that reproduced on 2026-08-11.
- Retiring the deterministic routes.
- The rubric, the applicability map, the scoring rulers. Frozen.

`tj-riim` closes inside `tj-mshi.4`. `tj-rt7w.14` closes inside `tj-n7p4.3`.

# Delivery

Local commits on `main`, one per child. No push, PR, merge, deploy, production
or staging mutation, model-configuration change, or real-user message. Paid
calls only within the authorisation above. Keep corpus text outside the
repository; tracked evidence carries `dialog_id` and integers only.

# Output

One tracked artifact per closed child, plus a `summary.md` per stage stating per
child: what changed, which gate proved it, and —

- for `tj-mshi.4`: that `test_llm_grounding_output.py` passed untouched, and
  which single test was removed and replaced, in those words;
- for `tj-n7p4.2`: the declaration each of the six guards received and the
  reason, one line each.

Update `.codex/handoff.md` to current state within its 200 lines and re-pin it.

Report back: current state, what each child changed, the verification actually
run with its numbers, what each round cost against the authorisation, the flag
and answer counts from `tj-n7p4.5`, and anything left open with the reason.

Do not report a child complete on the strength of the suite alone. For
`tj-mshi.4` read the recruitment reply by eye; for `tj-n7p4.3` read every reply
the judge corrected against the text it replaced.
