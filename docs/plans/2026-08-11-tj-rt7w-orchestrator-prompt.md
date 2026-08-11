# Orchestrator prompt — `tj-rt7w-overcomplication`

Hand to the Codex orchestrator verbatim. Claude verifies the result.

---

Target: repository `/home/me/code/treejar`, branch `main`, base commit `3f9a719`,
stage `tj-rt7w-overcomplication`.
Audience: the Codex orchestrator running `orchestration-bridge:orchestrator-stage`.
Runtime: Codex CLI on WSL, single repo, main-only delivery.

Documentation: no external/versioned boundary - internal refactor of first-party
Python, no new dependency, API surface or version-sensitive behaviour.

## Goal

Run `orchestration-bridge:orchestrator-stage` for stage `tj-rt7w-overcomplication`
in `/home/me/code/treejar`, on `main`, base commit `3f9a719`. Deliver epic
`tj-rt7w` children `.1`–`.6` in dependency order. Scope `.7` and leave it
unstarted.

## Context

Read in this order: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
then `docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md`
— the measured audit and the six rules, which is the contract for this stage —
then `docs/reports/2026-08-10-the-rerun-and-what-the-judge-saw.md`, where the
defects were measured. Then `bd show tj-rt7w` and each child. Beads is the only
tracker; do not open a markdown task list.

Dependencies: `.1` `.2` `.3` are ready now; `.4` needs `.2`; `.5` needs `.4`;
`.6` and `.7` need `.5`.

- **`.1`** Noor offered to buy or assess a customer's used furniture with nothing
  behind it (opening 789) — a safety defect of the same class as the two
  criticals already fixed. Rule 5 below applies: the prompt is tried first.
- **`.2`** Nothing bounds what a guard may delete; on 2026-08-10 that cost four
  of twenty customers their whole reply. Put the bound inside the chain.
- **`.3`** Four independent AED/DHS/dirham regex families live in `engine.py`,
  `fact_extractor.py`, `grounding_output.py`, `opening_guard.py`; only one
  canonicalises `290` against `290.00`.
- **`.4`** `_apply_first_turn_opening_guard`, `_apply_selling_turn_guard`,
  `_repair_closed_questions`, `_guard_premature_quote_detail_collection` are
  closures inside `process_message`. Lift them into `src/llm/response_policy.py`
  as pure `(text, explicit state) -> text`. No logic change.
- **`.5`** Four exit closures, four different chains — **three skip
  `enforce_grounding_output` entirely**. Collapse onto one `render_reply()`,
  provenance passed in, not branched on.
- **`.6`** Split `process_message`, 1 827 lines and 17 nested closures. Intended,
  not optional; its size is settled after `.5`. Read the issue note first.

## Constraints

The six rules of the spec, non-negotiable here:

1. One exit applies one text policy for every reply.
2. A guard may delete a sentence, never a reply.
3. Guards are pure module functions, never closures over `process_message`.
4. One money parser, one canonical form, shared by extraction and grounding.
5. No new guard until the prompt was tried and the failure measured. Evidence:
   `tj-swgu` measured 22.8 where the model wrote every substantive turn against
   13.3 where a template replaced one.
6. A refactor and a behaviour change never ride in the same round. `.2` `.3`
   `.4` `.6` are behaviour-preserving; `.1` and `.5` change behaviour and each
   ships as its own commit.

Write zone: `src/`, `tests/`, `docs/`, `.codex/handoff.md`, `.codex/stages/`,
Beads. `.codex/handoff.md` has a hard 200-line limit — run
`python3 scripts/orchestration/repin_traceability_sources.py` after every edit to
it or the manifest tests fail.

Frozen, do not touch: `calculate_weighted_score`, `raw_total`,
`attainable_weighted_score`, `_build_applicability_assessment`. Both rulers and
the rubric stay as they are.

Out of scope: retiring any deterministic route. That is 8 259 lines, excluded on
purpose, and blocked until `.1`–`.6` close.

No corpus text — not a message, a company name or an amount — enters the working
tree, a scratch file or a commit. Derived artefacts carry `dialog_id` and
integers only. There are no commit hooks;
`tests/test_corpus_stays_outside_the_repository.py` is the only net.

Authority: **no paid model calls, no push, no PR, no deploy, no production or
staging mutation, no model-configuration change, no real-user message.** Commit
locally on `main`. `.7` needs the owner's current authorisation for exactly 20
Luna + 20 GLM calls, about $0.18 — bring it back as a request. Reversible local
work proceeds without asking. Ask the owner on material ambiguity; never resolve
ambiguity by narrowing a step.

Delegated streams need a dedicated worktree and a tracked artifact under
`.codex/stages/tj-rt7w-overcomplication/artifacts/<task_id>.md`, validated by
`validate_artifact.py`. Inline subagents are not allowed by this contract.

Stop and report rather than working around, if: a behaviour-preserving step
requires editing an existing test; `.5` changes an output you cannot explain from
"this path now runs grounding"; `.1` cannot be fixed by the prompt and you are
about to add a fourth grounding violation; the handoff cannot stay under 200
lines without losing something a reader needs; or anything needs a paid call, a
push or a deploy.

## Success criteria

Per commit: `uv run ruff check src/ tests/`, `uv run ruff format --check
src/ tests/`, `uv run mypy src/`, `uv run pytest tests/ -q --tb=short`,
`scripts/orchestration/run_process_verification.sh` — all green.

Per step:

- `.1` — the stored reply for 789 no longer promises a service Treejar has no
  evidence of providing; no other stored reply changes; the test covers the
  phrasing family, not one sentence.
- `.2` — one test per existing guard proving it cannot blank a reply; the
  2026-08-10 apostrophe case, replayed against the pre-fix guard, is caught; the
  twenty stored raw outputs re-render identically.
- `.3` — all four call sites agree on the twenty stored raw outputs.
- `.4` — each guard has direct unit tests that build no conversation; the
  acceptance harness imports the production functions instead of reimplementing
  the chain.
- `.5` — one function applies the text policy for every exit; a test fails if a
  new exit bypasses it; every changed output on the three previously ungrounded
  paths is read by eye and explained.
- `.6` — `process_message` under 300 lines, `engine.py` under 12 000.
- For `.2` `.3` `.4` `.6`, no existing test was edited. If a move forces a test
  edit, the move is wrong, not the test.

At stage close: `python3 scripts/orchestration/check_stage_ready.py
tj-rt7w-overcomplication`, then `run_stage_closeout.py --stage
tj-rt7w-overcomplication --level slice_acceptance --command '<focused command>'`.

## Output

One tracked artifact per closed child, plus
`.codex/stages/tj-rt7w-overcomplication/summary.md` stating per step: what
changed, which gate proved it, and for the behaviour-preserving steps the
evidence that behaviour did not move — no existing test edited, twenty stored
raw outputs identical. For `.1` and `.5`, name every output that changed and
why. Update `.codex/handoff.md` to current state within its 200 lines and re-pin.

Do not report a step complete on the strength of the suite alone. For `.5`, read
the changed replies.
