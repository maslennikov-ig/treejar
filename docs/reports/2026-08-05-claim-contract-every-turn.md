# The claim contract on every catalog turn: built, priced, left off

Task: `tj-feet.10`. Measured 2026-08-05 on `openai/gpt-5.6-luna`. Round
`20260805/claimpass-r1`, protected evidence outside Git. Cost **$0.0195** for
42 measured turns.

**Shipped switched off.** The widened scope is implemented and its regression
passes, and the measurement says it must not be enabled yet — not because of the
latency, which is the cost the owner was asked to weigh, but because of three
things the measurement found in the contract itself.

## What was built

The `tj-feet.3` claim pass fires only on one of two hardcoded requested gap
types. On a turn where the customer asked nothing, the model's text was final
and a volunteered attribute had nothing to be checked against.

`_verify_volunteered_claims()` closes that. The trigger is **structural** — a
catalog row reached the model this turn — and never a pattern over the reply
text, which the specification rejects. Two properties keep it safe:

* A clean turn keeps its original reply **untouched**. The check is paid, the
  rewrite is not. Only a turn that actually volunteered something unsupported is
  regenerated, so a verified turn cannot lose its formatting, media or tone to a
  second generation.
* An unparseable verification leaves the turn exactly as it was.

Scope is one `system_configs` row, `claim_contract_scope`, defaulting to
`requested_gaps`. Setting it to `every_catalog_turn` switches the widened scope
on with no deploy, the same reversible mechanism as the model slot.

## The price of the extra call

42 turns, one call each, over the stored `counterset-r2` replies with the exact
directive and payload the runtime sends.

| | |
|---|---|
| latency, median | **7 698 ms** |
| latency, p90 | **17 319 ms** |
| provider cost per turn | **$0.000465** |
| contract followed | 37 of 42 (0.881) |
| claims emitted per turn | 5.6 median |

The money is irrelevant: a thousand catalog turns cost 47 cents. The latency is
not. Roughly **7.7 seconds added to the median catalog turn** on top of the
generation it follows, and 17 seconds at p90, on a WhatsApp conversation. Five of
42 turns ran past the token budget mid-payload and produced nothing usable, so
one turn in eight would pay that latency for no verification at all.

## The finding that actually decides it

Running the contract over the 209 claims those 37 turns emitted, **30 of 37
turns would have been rewritten**. Almost none of that is a fabrication being
caught. Three structural classes account for it, and each is a gap in the
contract rather than a defect in the model.

**Derived facts have no home.** `check_claim` routes `derived_fact` through the
same existence check as `catalog_fact`, and a derivation is on no row by
definition. *CH-A is cheaper than CH-B*, *AED 4,000 for two desks*, *two desks ×
ten people = twenty* were all withheld. Tracked as `tj-feet.12`.

**Arabic surface forms are withheld against their English values.** The module
states that an Arabic reply is verified against the English row and the Arabic
wording treated as translation. `_value_is_covered` does literal containment, so
*هيكل فولاذي* against a stored *steel frame* and *دبي* against *Dubai* were both
withheld. The stated design is not the implemented one, and this affects the
shipped narrow path too. Tracked as `tj-feet.13`, at P1.

**Saying an attribute is absent is itself withheld.** The model emits claims
like `capacity = "not specified in the catalog"`. The path is absent, so the
claim is withheld — which withholds the assistant saying the catalog does not
state something, the exact sentence the partial answer exists to produce.
Tracked as `tj-feet.14`.

Enabling the widened scope before those three land would rewrite four turns in
five, and most of the rewrites would remove correct content.

## One live defect this found and fixed

The first pass of the measurement withheld a stored **price on 16 turns and a
stock count on 10**, because the model quoted `AED 800` against a value stored
as `800.00`, and `2,000` against `2000`. Literal containment failed on
presentation.

That is not specific to the widened scope: the shipped narrow path uses the same
comparison, so a customer could have been told the catalog does not state a price
it does state. `_value_is_covered` now accepts a value whose numbers are all
stored numbers — currency, thousands separators, Arabic-Indic digits and word
order are presentation — while a *different* number is still withheld. Both
directions are pinned by tests. Price withholding fell from 16 to 9 and stock
withholding to zero.

This is also the first non-empty denominator for counter-set metric 5, *the guard
deleted a correct claim*. It reported `n/a` on 42 responses because nothing was
ever withheld. Widening the scope produced the observations, and they are bad.
That is the metric doing its job.

## What acceptance this meets

- A volunteered unsupported attribute is withheld on a turn where the customer
  requested no fact gap, proven by a focused regression that failed before the
  change: `test_a_volunteered_attribute_is_withheld_with_no_requested_gap`.
- Added latency and provider cost per catalog turn are measured and reported
  above.
- Recommendation, comparison, stock, quotation, Arabic and escalation behaviour
  is preserved, by construction rather than by hope: with the switch at its
  default nothing changes, and with it on a clean turn is returned untouched.
- Gates: ruff, ruff format, mypy clean; `uv run pytest tests/ -q` gives **3035
  passed, 19 skipped**.

## Not claimed

Latency was measured over a residential WSL connection to OpenRouter, so it is
an upper bound on what a server would see, not a production SLA. The 42 turns are
counter-set replies, which are shorter than a real catalog turn with five rows,
so the claim count per turn is a lower bound. One model, one day. Option (b) from
the task design — a structured output type on the main agent, removing the second
call entirely — was not built or measured; it becomes the more attractive option
now that the second call's latency has a number.
