# The over-constraint counter-set: first measurement

Task: `tj-feet.5`. Measured 2026-08-05 on `openai/gpt-5.6-luna`, the model chosen
after the `tj-feet.8` re-run and now serving the main slot. Round
`20260805/counterset-r1`, protected evidence outside Git.

14 cases — five categories answerable **without** the missing field, plus two
genuine violations as controls — in English and Arabic, three repetitions,
**42 responses**. Cost **$0.0039**.

## The seven metrics

Reported separately, each on its own denominator. There is deliberately no
combined figure.

| | metric | all | EN | AR |
|---|---|---|---|---|
| 1 | unsupported-fact rate | **0.000** (0/42) | 0.000 (0/21) | 0.000 (0/21) |
| 2 | false-refusal rate | **0.200** (6/30) | 0.200 (3/15) | 0.200 (3/15) |
| 3 | unnecessary-hedge rate | 0.000 (0/42) | 0.000 (0/21) | 0.000 (0/21) |
| 4 | task completion | 0.767 (23/30) | 0.800 (12/15) | 0.733 (11/15) |
| 5 | guard deleted a correct claim | **n/a**, denominator 0 | n/a | n/a |
| 6 | persuasion | 3.262 of 5 (n=42) | 3.095 (n=21) | 3.429 (n=21) |
| 7 | next_step | 3.833 of 5 (n=42) | 3.667 (n=21) | 4.000 (n=21) |
| | control compliance | 1.000 (12/12) | 1.000 (6/6) | 1.000 (6/6) |

Denominators differ on purpose. Rates 2 and 4 exclude the controls, which are
*supposed* to be refused; the controls have their own line. Metric 5 reports
`n/a` rather than a flattering `0.000`, because zero observations is not zero
errors.

## What the numbers say

**Nothing was fabricated.** Not one of the 42 responses asserted a product
attribute the evidence did not carry. The controls confirm this is not caution
masquerading as accuracy: when asked outright to invent an acoustic rating or to
confirm in writing a seat count, the model declined all twelve times and offered
what it did have instead. A refusal rate cannot be gamed here by agreeing to
everything, and it wasn't.

**Every false refusal is one category.** All six sit in `C04`, the labelled
hypothesis: *we are twenty people, would two of these desks be enough?* The
correct answer is a marked assumption with a confirming question. What came back,
in both languages and all three repetitions, was a decline —
*the catalog does not state how many people each desk seats, so I cannot
confirm* — followed by a useful question and the price and stock that are known.

It is a soft refusal, not a stonewall. But the customer asked a buying question
and did not get an answer, and this is the single commonest shape of a
twenty-person furniture enquiry.

**The over-refusal is not caused by our guards.** This is the load-bearing
finding. The `tj-feet.3` claim contract *permits* exactly the answer that was
missing: capacity as a visible assumption carrying a confirming question is an
approved claim, and only a bare capacity assertion is withheld. The model
declined on its own caution under the system prompt, with no guard involved.

That also explains metric 5's empty denominator: the guard never had to withhold
anything, because nothing unsupported was ever produced. The cost of the guards
on this set is not small — it is unobserved.

**The Arabic replies were grounded on English rows without refusing.** The
evidence carried English field names and values only, exactly as the live catalog
does. Not one Arabic response declined for want of an Arabic source, and Arabic
scored *higher* than English on persuasion and next step. The `tj-feet.3` design
decision — verify against the English row and treat the Arabic surface form as
translation — holds up on measurement.

**Persuasion is the weak axis, confirmed independently.** 3.262 of 5, against
3.833 for next step. The superseded round put the same model at 3.22 on
persuasion, on entirely different cases and a different instrument. Two
instruments that share nothing agreeing on the number makes it a property of the
assistant rather than an artefact of one measurement.

**The task-completion gap is small and specific.** Of the seven misses in 30,
six are `C04`. The seventh is one Arabic comparison that named both prices and
the cheaper option but omitted the difference the customer asked for.

## Method

One paid generation, then the guards applied to the same text. Running the set
twice — once before the guards and once after — would pay twice and mix the
guard delta with generation noise. Because the guards are deterministic code,
the same responses can be scored under two configurations and the delta carries
no sampling noise.

The instrument reports `n/a` for an empty denominator, and a deliberately
over-strict configuration is proved able to move metric 5 in
`tests/test_scripts_model_battle_counterset.py`. Over-strictness there is not
hypothetical: dropping field-path normalization is enough, because the live
catalog carries `Recommended load` and `Recommended Load` as separate keys.

Russian is absent by owner decision of 2026-08-05: the assistant serves English
and Arabic, and measuring a third language would be imitation coverage.

## What this hands to the next tasks

**`tj-feet.6`** now has a target that is specific rather than aspirational.
Persuasion at 3.262 is the axis to move, and the single highest-value change is
not a tone change: it is teaching the marked-assumption move on `C04`, which
would convert six false refusals into answers **without touching any factual
guard**, because the contract already permits it. That is the rare case where
the persuasion metric and the grounding metric move the same way.

**`tj-feet.9`** now has the scale it was waiting for. It also has a warning: on
this set the unsupported-fact rate is already 0.000, so a paraphrase checker has
no headroom to prove itself here and would be evaluated almost entirely on its
false-block rate. The counter-set needs harder grounding cases before that
checker can be accepted or rejected on evidence.

## Not claimed

This is one model, one set of 14 cases, three repetitions, one day. It measures
the assistant's behaviour on requests answerable without a missing field; it does
not measure real customer traffic. The guards' cost in deleted correct claims is
unobserved, not proven absent.
