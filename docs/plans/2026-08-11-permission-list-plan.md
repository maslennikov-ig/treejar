# Execution plan — the permission list

Date: 2026-08-11
Spec: `docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md`
List: `docs/plans/2026-08-11-promise-types-for-ratification.md`
Epic: `tj-mshi`. Stage id: `tj-mshi-permission-list`.
Base: `main` at `11e3c59`.

## Shape

One cohesive vertical slice, five children in a straight chain. Each is a small
diff in one or two files. The risk is not where it looks: step 4 removes prompt
text whose guarantee is really held by a deterministic backstop, so the exposed
case is `tj-riim`, which has no backstop at all.

```
.1 ratify  →  .2 fill  →  .3 turn round  →  .4 delete  →  .5 measure
                                                 ↑
                                            tj-riim closes here
```

`.1` is the owner's, not the orchestrator's. **The orchestrator starts at `.2`
and only after `.1` is closed.** Rule P7.

## Per child

### `tj-mshi.1` — ratify *(owner)* — **closed 2026-08-11**

Ratified as written. All 22 promises and 3 redirects ship with their proposed
mode and condition, including row 10 — come back with an answer, permitted only
when no tool can answer this turn — which the owner confirmed against their own
2026-08-10 approval on dialog 819.

The same session added rule **P8**: doubt is resolved by a second model, not by
deleting a sentence. That is epic `tj-n7p4` and it is not built here; this stage
only has to avoid contradicting it, which it does by adding no text-editing path
at all.

### `tj-mshi.2` — fill the registry

`src/llm/communication_policy.py` only. Add the ratified entries to
`COMMERCIAL_CAPABILITIES` with mode and source; add the `direct` and
`not_offered` modes to `CapabilityMode`.

Nothing reads the new entries differently yet, so behaviour is unchanged and the
child is verifiable by tests alone. New test: the registry covers exactly the
ratified set.

### `tj-mshi.3` — turn every entry round

Same file. Rewrite all instruction strings as permissions with conditions, and
the `[AUTHORIZED COMMERCIAL CAPABILITIES]` header with them.

New test: no instruction string in the registry contains `never`, `do not`,
`don't`, `cannot`, `must not`. That is a crude check and it is deliberate — it
is the one thing that cannot drift back silently.

This child changes the prompt, so it changes behaviour. It does not ship a
measured round of its own: `.3` and `.4` are one behaviour change and are
measured together in `.5`. They are separate children because `.4` is the risky
half and has to be revertible on its own.

### `tj-mshi.4` — delete what the registry subsumes *(P0)*

Remove:

- `CUSTOMER_OWNED_FURNITURE_POLICY` in `src/llm/prompts.py`, and the
  `LANGUAGE_DIRECTIVE` splice that carries it;
- the `"I will check" / "Let me check"` prohibition, `prompts.py` rule 7;
- the grounding-policy bullet at `communication_policy.py` that forbids offering
  to check later, which the `tool_required` condition now states positively;
- any other prompt sentence whose whole content is a registry entry's condition.

**What breaks, and what must not.** `tj-rt7w.1` shipped two layers: this prompt
block and a bounded deterministic backstop in `grounding_output.py`. The
guarantee is in the backstop and does not read the prompt, so deleting the block
is safe and every test in `test_llm_grounding_output.py` must pass **untouched**.

One test does break by construction:
`test_llm_prompts.py::test_customer_owned_furniture_prompt_covers_the_service_promise_family`
asserts the block is in the built prompt. Replace it in this child with a test
asserting the same coverage against the `not_offered` entry, and say in the
artifact that it was a declared removal rather than a test edited to accommodate
a move. If any behaviour test in `test_llm_grounding_output.py` needs touching,
the step is wrong — stop and say so.

**Stop rule.** No compensating prohibition anywhere. If something looks like it
needs one, it is a missing registry entry; fix the entry or record the finding.
A quiet restore turns this epic into the fourth prohibition and nobody would
know.

`tj-riim` closes with this child if the recruitment redirect holds — and that is
the case with no backstop behind it, so it is the one worth reading by eye.

### `tj-mshi.5` — one measured round

Frozen twenty, seed `20260810`, judged by the orchestrator, paired against
**2026-08-11** — the first baseline on this judge, so this is the first round in
the project's history with a valid paired comparison.

Read in both directions:

| direction | what would show it |
|---|---|
| fewer unsupported promises | criticals do not rise; **dialog 28 no longer promises a routing** — the honest test, since 789 has a deterministic backstop and would stay fixed regardless |
| **more supported ones** | rules 14 and 15 move off zero |

If criticals reach zero and 14/15 stay at zero, the list is too tight. That is a
finding to record, not a result to celebrate.

Paid calls need current owner authority, named and priced before spending.

## Verification

Per child: `uv run ruff check src/ tests/`, `uv run ruff format --check src/
tests/`, `uv run mypy src/`, `uv run pytest tests/ -v --tb=short`, and
`scripts/orchestration/run_process_verification.sh`.

At `.4` additionally: every test in `test_llm_grounding_output.py` untouched and
green, and the 31 stored raw outputs replayed through the policy chain unchanged
— `.2`–`.4` touch prompt text, not the guards.

Stage close: `check_stage_ready.py` then `run_stage_closeout.py --stage
tj-mshi-permission-list --level slice_acceptance`.

## What must not happen

- **No new prohibition block.** If a defect appears mid-stage that seems to need
  one, it is a missing or wrong registry entry. Fix the entry, or record the
  finding and leave it.
- **No second place for promise rules.** P1. If the registry cannot express
  something, that is a finding about the registry's shape, not a licence to put
  the rule in `prompts.py`.
- **No deterministic commitment check in this stage.** P5: it ships only after
  `.5` measures a leak, it owes its own round, and under P8 it would be a
  trigger for `tj-n7p4`'s rewrite rather than a repair of its own.
- **Nothing added here may edit customer-visible text.** P8.
- **No existing test edited.** If a step needs one edited, the step is wrong —
  stop and say so.
- No push, PR, deploy, production or staging mutation, or real-user message.
  Paid calls only in `.5` and only with current authority.

## Sequencing note

`.2` and `.3` could be one child. They are two because the registry is the
durable artefact and the wording is the thing most likely to need a second pass
after `.5`. Keeping them apart means the second pass is a one-file diff against
a settled list.
