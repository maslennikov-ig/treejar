# Model-Written Prose Over Verified Facts — Design

**Date:** 2026-08-07
**Owner:** `tj-swgu`
**Status:** ready to execute

## Goal

Raise the S01–S10 production acceptance from **18.0/30 to the 24.0 threshold**
by removing or wrapping the deterministic routes that replace the model's prose,
without moving a single verified-fact guarantee or side effect.

## Why this and not something else

The 2026-08-07 run separates on exactly one variable: who wrote the turn.

| | scenarios | comparable mean |
|---|---|---|
| every substantive turn model-written | S01 S02 S03 S04 S07 | 22.8 |
| at least one turn replaced by a template | S05 S06 S08 S09 S10 | 13.3 |

Excluding S04, which is low for the separate reason below, the model-written
cohort averages **24.8 — already above threshold**. Nothing else in the run
comes close to that effect size. Functional correctness is not the problem: it
improved from six failures to two, and both remaining failures are inside
templates.

## Where the routes came from

Nine deterministic routes accumulated one at a time between 2026-05-15 and
2026-07-30. Each fixed a real complaint. No commit body records why any of them
exists; the reasoning survives only in test names, and it is consistent — the
model escalated instead of answering, added alternatives when told not to, did
not reliably state price and stock, or failed to fire a CRM write.

The premise behind all of them is that the model cannot be trusted on that turn.
The main model changed to `openai/gpt-5.6-luna` on **2026-08-05 17:50 UTC**,
after the last route was written. None had been re-tested against it.

## What the counterfactual established

Each route was neutralised at its predicate against the deployed runtime, with
conversation state, catalog lookups and the claim contract running as in
production and outbound sending stubbed. Recorded on `tj-ja1v`.

**`stock-price-options` — the premise is gone.** The model produced the correct
SKU, live stock, unit price and the twelve-unit total the template omits, with
no alternatives and no quotation.

**`service-availability`, `saved-context-summary` — the diagnosis was wrong.**
Neither turn reached the model when the route was off. Both fell to the
verified-answer policy, which escalated with "I want to be accurate, so our
manager will confirm this for you." These routes are not compensating for the
model; they are patches over an over-eager handoff. With the handoff relaxed the
model answered both correctly, including the parsed products-and-quantities
field that the saved-context template gets wrong.

**`verified-catalog-functional-failure` — right to fire, wrong remedy.** The
model's rejected answer kept both product families, stayed under the stated
ceiling and offered a real cross-sell, but its cross-sell arithmetic left nine
chairs for twelve people. The detection is correct. Substituting a template is
not: the substitute dropped a whole family, printed a coverage line that
contradicts the lines above it, and leaked an escaping artefact.

**`selection-confirmation`, `exact-quote-deterministic`, `sales-opportunity` —
these carry the action.** They persist selection state, create the quotation and
write the CRM opportunity inside the route, and cannot be tested by switching
them off. They stay. The write already completes before a pure text renderer is
called, so the sentence is separable from the guarantee.

`name-gate` is the ninth and is out of scope: it is a first-turn identity gate,
not a replacement for an answer.

## Design

**One rule.** A deterministic route may own *what is true* on a turn. It may not
own *how it is said*, unless the model has been given the turn and failed it.

Three shapes follow, and every task below is one of them:

1. **Retire** — the guard's premise no longer holds. Delete the route and its
   renderer; rewrite its tests to pin the behaviour rather than the template
   text. (`tj-swgu.1`, `tj-swgu.4`)
2. **Repair, don't replace** — the guard's detection is correct. Keep it, and on
   rejection send one repair directive naming the specific defect instead of
   substituting text. The template becomes the second fallback, not the first
   response. The engine already has this mechanism. (`tj-swgu.2`)
3. **Wrap** — the route owns a write. Keep the write first and unconditional,
   then let the model write the sentence over the facts the route already
   verified, falling back to the existing renderer if the model run fails.
   (`tj-swgu.3`)

**Fix the cause, not the symptom.** `tj-rily` narrows the handoff policy so it
stops escalating low-risk questions. That is what makes shape 1 available for
two of the routes, and it stops the same patch being written a third time.

**S04 is the same failure from the other side.** Correct, and not selling. It
gets a per-turn runtime directive on comparison and closed-product turns, not a
larger system prompt.

**Make accretion visible.** `LLMResponse.text_provenance` already distinguishes
`model`, `model_repaired`, `deterministic_replacement` and
`deterministic_static`. Surface it per turn in the acceptance capture and assert
on the aggregate, so the next route shows up as a number rather than as a
surprise months later.

## Binding constraints

- The product system prompt does not grow. New guidance is per-turn
  `runtime_directives` only.
- Frozen `AC-01..AC-30` and its digest stay unchanged.
- Public REST/webhook contracts and the database schema stay unchanged.
- The claim contract keeps its current setting: block only on proven falsehood;
  a derived fact that cannot be proven still reaches the customer.
- No side effect moves, becomes conditional on model output, or runs later than
  it does today. The CRM write, the quotation and the selection state are not in
  scope for behaviour change.
- Rejected and still rejected: lexical backstop over reply text, per-message
  ensembles, abstention fine-tuning, knowledge graph, whole-response blocking,
  and determinizing past the point where the model stops doing the language
  work. The last is the defect being removed, not a tool for removing it.
- Sealed acceptance rounds are superseded, never rewritten. Protected evidence
  stays outside Git.
- No PII, provider or message identifiers, or exact captured wording in reports.
- Live runs, pushes and deploys need current explicit owner authority.

## Acceptance for the epic

One production run on a single runtime identity, scored by the production
evaluator, with:

- comparable mean **≥ 24.0**, against 18.4 (2026-08-03) and 18.0 (2026-08-07);
- functional failures **0**, against 2;
- no scenario below **20.0** comparable except where the customer explicitly
  forbade the behaviour the checklist rewards, stated per scenario;
- external readbacks clean and test data cleaned up;
- no new unsupported fact on the bait counter-set.

## What could make this wrong

The counterfactual measured single turns in isolation. A route removed may be
load-bearing on a turn the acceptance set never exercises — the S06 result
already showed that switching one route off hands the turn to the next route,
not to the model. Every retirement task therefore rewrites the route's existing
tests to pin behaviour, rather than deleting them, and the full suite is the
gate before the live re-run.
