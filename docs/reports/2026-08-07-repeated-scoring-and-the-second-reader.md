# Repeated scoring, and what a second reader found, 2026-08-07

`tj-swgu.9` asked for the acceptance mean to be published with its uncertainty
instead of on its own. Doing that turned up two corrections to the standing
numbers, neither of which needed a single new judge call.

**The standing production figure is not 18.2. It is 16.1 with no uncertainty
attached, and five independent readers of the same ten transcripts make it
12.3 ± 0.3. The threshold is 24.0.**

No live traffic, no paid judge call, no deploy and no write of any kind was
made for this report. Everything below comes from score files and captures that
were already on disk.

## The instrument

`scripts/e2e_acceptance/score_uncertainty.py` reads a run directory of score
files and reports the mean with the interval its repeats justify, per scenario
and in aggregate, plus the rule that follows: **a movement smaller than its own
uncertainty is not a finding.** Two runs can be compared, paired on the
scenario set, and the comparison says outright whether the difference survives.
21 tests cover it in `tests/test_e2e_acceptance_score_uncertainty.py`.

```
uv run python -m scripts.e2e_acceptance.score_uncertainty <run> [--against <run>]
```

## Correction one: every mean published on 2026-08-07 was normalised twice

`comparable` has always meant "drop the wholly non-applicable blocks and
normalise the rest to 30". Until 2026-08-03 the evaluator returned block points
on the nominal block weight, so a scenario with one dead block scored out of 24
and the report multiplied by 30/24 by hand. Commit `808b07d` moved that
division into `calculate_weighted_score` — `normalized_weight` appears in the
score file from then on, and `total_score` has been the comparable /30 figure
ever since. The reports kept multiplying anyway.

It is visible in the stored files without any interpretation. A rule scoring 2
carries `weight_points` 1.5 in the 2026-08-03 run, which is 6/4 on the nominal
weight. The same rule carries 1.875 in both 2026-08-07 runs, which is 7.5/4 —
already normalised. Recomputing the published columns from the stored files
reproduces 18.03 and 18.21 exactly *with* the extra multiplication, and 15.75
and 16.08 without it.

| build | published | actual |
|---|---|---|
| `c977b07` | 18.0 | **15.8** |
| `6a14f2f` | 18.5 | **16.1** |
| `5656c82` | 18.2 | **16.1** |

The conclusion the earlier report drew from these — that three materially
different builds are one number — survives the correction intact. What does not
survive is the distance to the threshold: the gap to 24.0 is 7.9 points, not
5.8. Filed as `tj-swgu.13`.

`read_comparable_score` now reads the scale off the file instead of assuming
one, so both file shapes land on the same axis and neither is normalised twice.

## Correction two: a second reader scores it four points lower again

With paid judge calls declined, the ten stored transcripts were read and scored
directly against the same fifteen criteria, on the same applicability map the
runtime derived, with the arithmetic handed to the product's own
`calculate_weighted_score` rather than done by hand.

```
scenario   deepseek-v4-flash   second reader    delta
S01                    22.3            18.4     -3.9
S02                    19.4            15.0     -4.4
S03                    14.1            11.0     -3.1
S04                    15.9            16.4     +0.5
S05                    16.6            13.1     -3.5
S06                    12.0             7.9     -4.1
S07                    12.2             9.8     -2.4
S08                    18.1             9.4     -8.7
S09                    11.7            10.2     -1.5
S10                    18.8            10.2     -8.6

mean                   16.1            12.1     -4.0
```

Two things are measured here, and they are worth keeping apart. The systematic
part is **−4.0**: one reader is harsher than the other across the board. On top
of that the readings differ by **2.9** more, scenario to scenario. Both numbers
are larger than every build-to-build difference ever published in this stream.

**Where they disagree most is not arbitrary.** S08 and S10 account for both
eight-point gaps, and they are the two conversations that handle their
mechanics well and sell nothing. S08 tracks a mid-conversation correction from
eight people to twelve without losing the budget or the no-quotation
instruction — and across four turns it asks the customer no question, states no
value proposition and proposes nothing. S10 records a CRM opportunity, quotes
the right total and proposes a follow-up, and likewise never asks what the
customer's project needs. The production judge rewarded the tidy summary. The
rubric it is applying asks for consultative selling, and on that reading both
score low.

That disagreement is a finding about the instrument, not a claim that either
reader is right. It is also the single largest source of movement in the number
this stream has been gating on.

## The repeats, and the number they produce

Five independent readers then scored the same ten transcripts blind: separate
instances, the same rubric and applicability map, each unable to see the
others' scores or the production judge's. Fifty scorings.

```
mean 12.3/30 +/- 0.3 (95%, 10 scenarios, 50 scorings, df 40)
judge sd 0.9 per scenario per scoring, pooled across scenarios
```

Per-reader means: 13.2, 12.0, 12.2, 11.8, 12.3. The single careful reading of
the previous section, taken independently of the panel, was 12.1 — inside the
interval.

**The instrument got about four times quieter.** The production judge's
measured deviation on identical text is 3.8; this panel's is 0.9. On the
ten-scenario mean that is the difference between ±3.3 and ±0.3 — between
needing a seven-point move before a scenario can be read, and needing under
one. The epic's own acceptance target of 24.0 is 11.7 points away from 12.3,
which is now a distance the instrument can actually resolve.

Where the panel disagrees with itself is informative: S09 has sd 0.0, all five
readers identical, while S04 has sd 2.1 and a 5.5-point range. S04 is the
scenario the production judge also moved most on. Some conversations are
genuinely hard to score and some are not, and the tool prints which.

**What ±0.3 is and is not.** It is the precision of this panel — how much its
own reading wanders when repeated. It is not accuracy. All five readers are the
same model family under the same prompt, so a bias they share is invisible to
this measurement, and the −3.8 gap to the production judge is not evidence
about which of the two is right. Precision is what an acceptance gate needs to
distinguish builds; correctness of the rubric reading is a separate question
and the fifteen criteria belong to the customer.

The comparison between the panel and the production judge deliberately returns
no verdict: two different judges do not share a noise estimate, so the repeats
of one cannot stand in for the other. The measured difference is −3.8 on the
mean and 4.0 more scenario to scenario.

## Two things this measurement settled for the tasks downstream

**`tj-swgu.11` is confirmed, and it is not a judge problem.** S06 asks for one
exact SKU, forbids alternatives and forbids a quotation. Both readers score it
0 on consultative solution, on the comprehensive proposal and on the bundle or
incentive — the three criteria the customer explicitly ruled out. Two
independent readers agreeing on a zero is what an applicability defect looks
like: the rubric is being applied correctly and the criterion should not have
been applied at all.

**`tj-swgu.10` has a free lever waiting.** `PATH_QUALITY_FINAL` sets no
temperature. `model_settings_for_path` builds `max_tokens`, `timeout` and
`extra_body` and never passes one, so the judge runs at the provider default
rather than at 0 — while the acceptance harness's own bounded judge in
`scripts/e2e_acceptance/evaluators.py` refuses any judge whose temperature is
not 0. That is very likely most of the sd of 3.8. It is recorded on `tj-swgu.10`
rather than applied here, because applying it first would mean the baseline
describes a different instrument.

## The rule, from here on

No conclusion is drawn from a movement smaller than its own uncertainty, and
the bound depends on which instrument took the reading:

| instrument | judge sd | mean carries |
|---|---|---|
| production judge, one pass | 3.8 | ±3.3 |
| five blind readers | 0.9 | ±0.3 |

The tool prints the bound with every run, so a report cannot quietly skip the
check, and it refuses a verdict when a run has no repeats to justify one.

The structural gate remains trustworthy alongside it. Deterministic turns went
15 → 13 → 9 of 29 across the three builds, and that is counted rather than
scored.

## What was changed after this measurement

`tj-swgu.14`, the first slice: rules 6, 7 and 13 now have a per-turn
`consultative_opening_directive` behind a demand-side trigger that reads the
customer request and the typed stage, never the reply. It stands down on a
customer who has narrowed to one exact item, which is the S06 and S09 shape.
The frozen product system prompt did not grow.

Rule 11 is deliberately still at zero. An incentive is a commercial commitment
nobody has authorised, and the sibling comparison directive forbids one
outright. The honest form of that rule is a verified bundle rather than a
discount, and that is a decision for the owner, not a prompt change.
