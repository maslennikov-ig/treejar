# The three contract gaps, closed — and what the replay can and cannot say

Tasks `tj-feet.12`, `.13`, `.14`, plus `tj-feet.11`. Written 2026-08-06.
**No provider call was made for any of this.** Total cost of the day: nothing.

## Why these existed

Enabling the widened `tj-feet.10` scope on 2026-08-05 would have rewritten 30 of
37 verified turns, and almost none of that was a fabrication being caught. Three
structural classes accounted for it. None was a defect in the model; each was a
gap in the contract.

## What changed

**`tj-feet.12` — a derivation is verified through its inputs.** `check_claim`
routed `derived_fact` through the same existence check as `catalog_fact`, and a
derivation is on no row by definition, so a comparison, a total or a calculation
could never be supported. A derived claim now names an `operation` and lists
every `ClaimInput` it rests on. Each catalog input is checked against the row it
names; an input the customer supplied is taken at face value, because it is
theirs, but may not overwrite a value the catalog does state.

Listing inputs is not by itself verification, so the arithmetic is recomputed:
the figures the reply states must be the input figures or the single result of
the named operation. `800 + 900 = 1,700` ships; the same inputs reported as
`1,500` do not. An operation the runtime cannot restate stays withheld even when
every input is sound.

The owner decision of 2026-08-05 survives the new route. A per-product seating
capacity may not be an input to a derivation from either side — `two desks x ten
people = twenty` was the measured shape, and multiplying a capacity does not
make it a catalog fact. A figure carrying no SKU is about the customer's own
team and is unaffected.

**`tj-feet.13` — an Arabic surface form is a translation, not a source.** The
module has always documented that an Arabic reply is verified against the
English row and its wording treated as translation. Literal containment did not
implement that, so `هيكل فولاذي` against a stored `steel frame` and `دبي`
against `Dubai` were both withheld. A claim now carries the English value it
rests on in `source_value`, which costs no call and no translation model.

The branch opens only for a non-Latin surface form. Otherwise `source_value`
would be an escape hatch — name the stored value there, write anything in
`value` — which is the one thing the contract exists to prevent. And words are
translation while a figure is a fact in any script, so a translated surface may
not state a number the row does not carry: `١٢٠ كجم` against a stored `120 kg`
ships, `١٥٠ كجم` does not.

This one also affects the shipped narrow repair path, not only the widened
scope, which is why it was the P1 of the three.

**`tj-feet.14` — an absence statement is not an attribute claim.** The model
emits `capacity = "not specified in the catalog"`. The path is absent, so the
claim was withheld — which withheld the assistant saying the catalog does not
state something, the exact sentence the partial answer exists to produce.
Absence is now its own claim type, checked against the row's *status* rather
than against a value, with no lexical detection of absence wording anywhere.

It is checked, not waved through: denying an attribute the row does state is a
false statement about the catalog and stays withheld.

## A fourth class the replay found

`field_path=sku, value=CH-A` was withheld, because `row_from_catalog_product`
never flattens the identifier into the fields the model is shown. The row *is*
that SKU, so naming it is the one claim that needs no column. It is now
supported; naming a different SKU is not; and a catalog that does carry an `sku`
column still wins over the identifier.

## What the replay measured, and what it did not

The 209 stored claims of round `20260805/claimpass-r1` were re-run through the
fixed contract offline.

| | |
|---|---|
| turns replayed | 37 |
| claims | 209 |
| withheld, contract as shipped | 52 |
| turns that would be rewritten, as shipped | **30 of 37** |
| turns that would be rewritten, upper bound after the fix | **1 of 37** |

Of the 52 withholdings, 36 were derived facts, 8 Arabic surface forms and 7
absence statements. One residual remains and is arguably correct: a claim that a
*separate back material* is not specified, on a row whose `Materials` field does
state `steel frame`.

**The 1 of 37 is an upper bound, not a measurement.** The stored claims predate
these fixes and carry none of the fields the fixes need. Reaching that number in
production requires the model to name an operation, list its inputs and supply
`source_value` correctly — and the derived-fact branch, which is 36 of the 52,
is the one that asks the most of it. The before-number is exact; the
after-number assumes the model cooperates every time, which nothing here has
measured.

What would settle it is one more claim pass on the current contract: 42 turns,
about `$0.02`, the same shape as the run that produced this evidence. It has not
been run and needs its own authorization.

## `tj-feet.11` — the manifest pins that kept breaking

`.codex/orchestrator.toml` and `.codex/handoff.md` are declared by `AGENTS.md`
to be current state, and the `tj-ee5f` traceability manifest pins whole-file
digests of both. Any stage that sets `current_stage_id` or updates the handoff
breaks three manifest tests with a message that says nothing about what changed.
`tj-feet` re-pinned by hand twice on 2026-08-05.

The design question of whether a frozen manifest may pin mutable state belongs
to the `tj-ee5f` stream and is left there. What is fixed is the trap:
`scripts/orchestration/repin_traceability_sources.py` re-pins exactly those two
paths and reloads what it writes through the real validator, so it cannot
produce a manifest the gate then rejects. `--check` reports drift and writes
nothing.

It is **not** listed in the `AGENTS.md` Operational State inventory alongside
the other orchestration scripts, where a maintainer would look for it. Adding it
there was tried and reverted: `AGENTS.md` is pinned in the same frozen registry
as `repo-contract`, so a one-line addition to an operational list breaks the
same three tests and would need a deliberate re-pin of another stream's
acceptance provenance. Doing that quietly is worse than the missing line. The
step is recorded in `.codex/handoff.md`, which is current state and is what the
next orchestrator reads first; the `AGENTS.md` entry is a bounded defer owned by
`tj-ee5f`.

That the fix for this trap was itself caught by the trap is the clearest
evidence available for the recorded design question.

The narrowness is the point, and it is the property under test: a frozen
requirement, a scenario set or the scope snapshot drifting still fails loudly.
This records that current state moved. It is not a way to launder a change.

## Not claimed

No provider call, so nothing here is measured on live model output. The
regressions prove the contract; the replay bounds the effect. Whether the
widened `tj-feet.10` scope should now be enabled is a separate decision that
still wants a fresh pass and still belongs to the owner — the added latency it
was originally weighed on, 7.7 s median and 17 s at p90, is unchanged by any of
this.
