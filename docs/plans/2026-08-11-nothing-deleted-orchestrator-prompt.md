# Orchestrator prompt — `tj-n7p4-judged-repairs`

Hand to the Codex orchestrator verbatim, **after `tj-mshi-permission-list` is
accepted**. Claude verifies the result.

---

Target: repository `/home/me/code/treejar`, branch `main`, stage
`tj-n7p4-judged-repairs`. Base commit: the tip of `tj-mshi-permission-list`.
Audience: the Codex orchestrator running `orchestration-bridge:orchestrator-stage`.
Runtime: Codex CLI on WSL, single repo, main-only delivery.

Documentation: no external/versioned boundary — first-party Python and one
provider call through an existing client, no new dependency, no API surface.

## Goal

Run `orchestration-bridge:orchestrator-stage` for stage `tj-n7p4-judged-repairs`.
Deliver epic `tj-n7p4` children `.1`, `.2`, `.3`, `.6`, `.4` in that order, then
`.5` only if the owner authorises its paid calls in that session.

Stop the code from deleting the customer's reply on its own. Where a check finds
doubt, a judge reads it and either approves the text or writes the correction.

## Context

Read in this order: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
then `docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md`
— the audit and the five rules, which is the contract for this stage — then
`docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md` for rule P8,
which is where this epic came from. Then `bd show tj-n7p4` and each child.

Beads is the only tracker. Do not open a markdown task list.

What you are changing lives in `src/llm/response_policy.py::render_reply`: six
guards in a chain, each wrapped in `apply_guard_with_reply_bound`. The bound
catches a guard emptying the whole reply. It does not catch a guard removing one
sentence, and that is the gap.

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

The five rules of the spec, non-negotiable here:

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

Also in force: no existing test may be edited; add by addition only. Guard
sources not named by a child stay byte-identical.

## The judge

The judge is a model from the **other vendor** — the point is a second opinion,
not a second try. It is not the acceptance judge: for scoring a measured round
the judge is still the orchestrator reading blind, and
`real_opening_acceptance.py` already defaults to that. Do not confuse the two.

Give it the reply, which flag fired, and the evidence available in that turn.
Take back one of three answers. Record per turn: the flag, the answer, and the
model identity.

## Two ways this goes wrong, and they are opposite

**A model call on half of all turns.** The opening guard fires on every first
turn and removes a duplicate identity line 28 times in 60. It is *replacing*. It
stays deterministic and never reaches the judge. If you end up consulting a model
on 47% of replies, D1's distinction has been lost and the stage is wrong. Say so.

**A judge nobody can overrule, or one that never disagrees.** D3 starts
permissive on purpose. Do not hard-code a class of flag as non-overridable in
this stage; that is a question for `.5` to measure.

## Verification

Per child: `uv run ruff check src/ tests/`, `uv run ruff format --check src/
tests/`, `uv run mypy src/`, `uv run pytest tests/ -v --tb=short`, and
`scripts/orchestration/run_process_verification.sh`.

At `.1` and `.2`, which are behaviour-preserving: replay the 60 stored raw
outputs of the three rounds through the chain and confirm the rendered text is
unchanged. Both `tj-vz7o-luna-glm-20260810*` and `tj-rt7w-round-20260811` live
under `<git-common-dir>/codex-orchestration/corpus-bridge/`. Keep the text there.

At `.3` and `.6`, which change behaviour: the same replay must show a change on
exactly the turns where a flag fired, and no change anywhere else.

Stage close: `check_stage_ready.py tj-n7p4-judged-repairs`, then
`run_stage_closeout.py --stage tj-n7p4-judged-repairs --level slice_acceptance`.
A validated artifact per closed child, and `.codex/handoff.md` at or under 200
lines, re-pinned with
`uv run python scripts/orchestration/repin_traceability_sources.py` after every
edit to it.

## `tj-n7p4.5`, and money

Frozen twenty, seed `20260810`, paired against **2026-08-11**. The scoring judge
is you, reading blind: `real_opening_acceptance.py run` stops after the
generation arm and writes `reading-pack.json`, and `ingest-judgment` takes the
reading back. The repair judge is a paid second-vendor call and fires only on a
flag — about one opening in sixty on the stored evidence.

Ask the owner for the paid-call authority by name and amount before spending.
If it is not granted in that session, leave `.5` open and say so; that is a
complete outcome for this stage.

Report: criticals must not rise; how often a flag was raised; how often it was
approved rather than corrected; how often the fallback fired; and whether any
correction was worse than the text it replaced. **If every flag was approved,
the detector is wrong or the judge is not reading. Both are findings, not
successes.**

## Not in scope

- Epic `tj-mshi`, the promise registry. Rule P8 points here; the code does not
  overlap.
- The deterministic commitment check. It is a future trigger for this machinery,
  and under P5 it waits for a measured leak.
- Retiring the deterministic routes.
- The rubric, the applicability map, the scoring rulers. Frozen.

## Delivery

Local commits on `main`, one per child. No push, PR, merge, deploy, production
or staging mutation, model-configuration change, or real-user message. Keep
corpus text outside the repository; tracked evidence carries `dialog_id` and
integers only.

## Output

One tracked artifact per closed child under
`.codex/stages/tj-n7p4-judged-repairs/artifacts/`, plus
`.codex/stages/tj-n7p4-judged-repairs/summary.md` stating per child: what
changed, which gate proved it, and — for `.2` — the declaration each of the six
guards received and the reason, in one line each.

Report back: current state, what each child changed, the verification actually
run with its numbers, the flag and answer counts if `.5` ran, and anything left
open with the reason.

Do not report a child complete on the strength of the suite alone. For `.3`,
read by eye every reply the judge corrected, against the text it replaced.
