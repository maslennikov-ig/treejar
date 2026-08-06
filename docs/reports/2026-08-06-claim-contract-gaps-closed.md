# The three contract gaps, closed, then measured

Tasks `tj-feet.12`, `.13`, `.14`, plus `tj-feet.11`. Written 2026-08-06.

The fixes and the offline replay cost nothing. One confirming provider round was
then authorized and run: `$0.0250`, and it overturned the replay's projection.

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

**The 1 of 37 was an upper bound, and it was wrong by an order of magnitude.**
It assumed the model would fill the new fields correctly every time. The
confirming round below measured what it actually does.

## The confirming round, and what it overturned

Round `20260805/claimpass-r2`, run 2026-08-06 on `openai/gpt-5.6-luna` under
owner authorization. 42 turns, `$0.0250`, `max_tokens` raised from 1200 to 2500.

| | as shipped (r1) | measured after (r2) |
|---|---|---|
| turns rewritten | **30 of 37** | **12 of 42** |
| claims withheld | 52 of 209 | 19 of 265 |
| contract followed | 37 of 42 | **42 of 42** |
| latency, median | 7 698 ms | 8 519 ms |
| latency, p90 | 17 319 ms | 14 612 ms |

**12 of 42, not the 1 of 37 the replay projected.** Reporting the bound as the
result would have overstated the fix by a factor of ten.

Two things did hold. The five turns that produced nothing usable in r1 were
token truncation, not incomprehension: at 2500 tokens the contract was followed
42 out of 42. And the new fields carry the effect — replaying the *same* r2
claims with the new fields ignored gives 27 of 42 rewritten against 12 of 42
with them, which isolates the fields from every other difference between rounds.

Every remaining withholding is a derived fact. The causes, by hand:

* **12 — the customer's own quantity, unlabelled.** The model gives it a
  plausible field path (`quantity`, `planning.desk_count`,
  `calculation.required_units`) and leaves `customer_stated` false, so the
  contract looks for it on the row and does not find it. The contract requires
  an input to be one of two shapes; the directive only mentioned the flag in
  passing. The directive now states both shapes plainly. **That change is
  unmeasured** — it was written after the round, and re-running the same 42
  cases to score a fix written from their failures would be fitting to the test
  set, not measuring.
* **5 — a per-desk capacity used as a derivation input.** Correctly refused; the
  owner decision holds. In production these turns also carry the sizing
  directive that routes them to a marked assumption, which this offline harness
  does not send, so this class is partly an artefact of the measurement.
* **1 — a comparison naming a single input.** A model error the contract caught.

## What this means for enabling the widened scope

It did not confirm it. The condition for turning `claim_contract_scope` on was
that the measurement back the projection, and it did not: 12 turns in 42 would
still be rewritten, and the latency it was first weighed on is unchanged at
8.5 s median. The switch stays off.

## The reversal: block only what the row refutes

Owner decision, 2026-08-06, stated plainly: *a spoiled reply is worse than a
model error. An error can be corrected; a mangled answer has already been read.*

The contract was built on the opposite assumption — block anything that cannot
be proven — and the measurement is what settles it. Across a counter-set built
specifically to bait fabrication, the model's measured unsupported-fact rate was
**0.000**, taken before the contract's repair pass ever ran. So the strict rule
was rewriting most replies while catching nothing that had been measured.

`supported` and `may_reach_customer` were already separate fields on
`ClaimCheck`; the code simply set them together. They are now used for what they
mean:

* **refuted** — the row carries a different value → still blocked;
* **unverified** — the row cannot confirm it → ships, and is recorded;
* **supported** — the row confirms it.

Two blocks survive untouched because they are owner rules about *presentation*,
not about verification: a seating capacity may never be stated as a plain fact,
and an assumption still needs its marker and its confirming question.

A comparison now falls under unverified rather than refuted, because a
comparison restates and does not calculate — there is no arithmetic in it to
prove a stray figure wrong with. A sum, difference or product still is, so
`800 + 900` reported as `1,500` remains blocked.

Measured on the same two rounds, with the code as it now stands:

| | turns rewritten |
|---|---|
| r1, strict rule as shipped 2026-08-05 | 30 of 37 |
| r2, after the three gap fixes | 12 of 42 |
| **r2, refuted-only** | **4 of 42** |

All four are the capacity rule. Nothing is now rewritten for being merely
unconfirmed.

The block is gone, the visibility is not: `ContractResult.unverified` is its own
bucket and is logged at info on every turn. That is what will tell us, from live
traffic rather than from a counter-set, whether the strict rule was protecting
anything after all.

**What was given up, said plainly.** An invented attribute the catalog is simply
silent about — a mesh back on a chair whose back is undocumented — now reaches
the customer. That was the original `tj-feet.3` criterion, and this reverses it.

### What the reversal actually lets through, measured

The sentence above states a risk. Applying the shipped contract to the 265
claims of `claimpass-r2` puts a number on it:

| | |
|---|---|
| claims approved | 261 |
| of those, unverified | **15** — 5.7% of all claims |
| withheld | 4, all the capacity rule |
| turns carrying an unverified claim | 11 of 42 |

**All 15 are derived facts. Not one is a `catalog_fact`.** The feared case — the
model asserting a product attribute the row does not carry — did not occur once
in 42 turns. What ships unconfirmed is arithmetic whose unverifiable input is a
quantity the customer supplied: `total_price_aed = 4000` from two desks at 2000,
`required_desks = 5`. That is the class the contract never could verify and had
no business blocking, and it agrees with the judge scoring these same replies at
0.000 unsupported facts.

The quality of a *rewritten* reply remains unmeasured, before or after. The
exposure shrank rather than being closed: rewrites fell from 12 turns in 42 to
4, and those 4 are the capacity rule, which routes into the marked-assumption
path that `tj-feet.6` did measure at 0.000 false refusals and 1.000 task
completion.

Caveat, as always: 42 turns, one model, one sitting. The counter-set is built to
bait fabrication, which makes 0 catalog-fact fabrications a meaningful result
rather than an easy one, but it is not production traffic.

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

One model, one day, 42 counter-set turns that are shorter than a real catalog
turn with five rows. Latency was measured over a residential WSL connection, so
it is an upper bound on what a server would see, not an SLA. The directive fix
for the unlabelled-quantity class is written but unmeasured, and is reported as
such rather than folded into the 12 of 42. Option (b) from the original task
design — a structured output on the main agent, removing the second call
entirely — is still unbuilt and, now that the second call has a second set of
numbers, still the more attractive of the two.
