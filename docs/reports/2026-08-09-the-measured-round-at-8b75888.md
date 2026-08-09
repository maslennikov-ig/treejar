# The measured round at `8b75888`

2026-08-09. Deployed, run and scored under owner authority granted the same day.
Every figure comes from the run described here. Where a number did not move by
more than its own uncertainty, this report says it did not move.

## The instrument

53 packets: 17 scenarios x 3 runs, plus `S09` and `S10` once each because they
have irreversible external effects — a PDF to the protected test chat and a CRM
opportunity — and the baseline counted them once for the same reason.

Two independent blind reads per packet across **9 readers**, 11 to 12 packets
each. Load is the variable that drives reader disagreement, and it is held below
the 13 that produced 1.96 last round. **Reader disagreement this round: 1.58**,
the lowest recorded.

Applicability was not left to the readers. It was computed from stored
conversation state by `_build_applicability_assessment` inside the deployed
container, read-only, and handed to every reader as a frozen map. All 106 reads
honoured it: **zero contract violations**.

The rubric did not change. `AC-01`–`AC-30` and the applicability contract frozen
on 2026-08-09 are untouched, so this round is comparable with the baselines.

## The headline: the number did not move

| shape | `ac36265` | `8b75888` | delta |
|---|---|---|---|
| project (4 scenarios) | 19.95 ± 0.93 | **20.02 ± 1.00** | +0.06 |
| transactional (same 11 scenarios) | 20.77 ± 4.41 | **21.16 ± 3.49** | +0.40 |

Both deltas are far smaller than their own uncertainty. By the rule this project
already wrote down — no movement smaller than its own uncertainty is evidence —
**this build is not distinguishable from the last one in aggregate.**

The transactional figure is stated over the eleven scenarios the baseline
contained. The four added this round would otherwise have been silently mixed
into the comparison, and they are hard: including them the same set scores
**18.94 ± 3.74 over 7.6 applicable rules across 15 scenarios**, and that is the
number the next round compares against, not 21.16.

## What did move, and what it is worth

**`R03`: 9.00 → 20.63.** Runs of 8.7, 8.7, 9.6 against 19.7, 19.7, 22.5, with a
within-scenario sd of 1.34 this round. Every run of the new build beats every
run of the old by more than ten points. This is `tj-jxv7` — the SKU written
without a space that classified as a service question — and it is the only
movement in the round attributable to one named change. The turn that used to
reply *"Could you confirm the quantity you need?"* now says *"Operative Office
Chair CH 616 NEW black — AED 295, 36 in stock"* and asks one question.

**Rule 13: 0.00 → 0.75** over the same 12 charged reads. Nothing else in the
round touches rule 13, so this is attributable. The guard fired on 3 of 53
packets, which is how narrowly the rule is charged. What it fixed is visible in
`S01` turn 2: *"the facilities manager at Cedarline Test Offices, a test-office
company"* — a line of work invented from a company name — became the company
named and the question actually asked. It is 0.75 and not 2 because the customer
has to answer for the criterion to be met, and in these scenarios they do not.
Asking is necessary and not sufficient.

**Rule 11: 0.28 → 0.00, and the guard built for it never ran.** Measured rather
than assumed: the string the guard emits appears in 0 of 53 packets.
`_verified_package_total_line` reads `deps.verified_catalog_selections`, which is
written in exactly one place inside the catalog-decision tool path, so on an
ordinary selling turn it is empty and the guard returns nothing. The guarantee is
built and unreachable. `tj-wvo4`.

## The finding that matters more than the delta

The four scenarios added this round are the shapes production actually shows,
and they score like this:

| scenario | | score |
|---|---|---|
| `R07` | voice note with a SKU the catalog does not hold | **7.35** |
| `R06` | two messages, then the customer is gone | **8.10** |
| `R09` | delivery and nothing else | **10.50** |
| `R08` | Arabic that switches to English mid-thread | 25.33 |

Against `S03` at 25.65, `S04` at 28.48 and `R02` at 29.07. Three of the four
realistic shapes score around a third of what the fluent, well-formed scenarios
score. `R04`, the voice note already in the set, sits with them at 7.95.

That is the gap. It is not a rubric artefact — the applicable-rule counts are 6
to 8, the same range as the transactional scenarios that score in the twenties.
The bot is good at the customer who writes a brief and poor at the customer who
writes four words and leaves.

## Two regressions this round cannot explain

`S07` fell 28.13 → 21.55 and `R05` fell 28.13 → 24.40, both outside the overlap
of their own runs. Read by eye, `S07` is a content choice: asked for *"only
relevant office-furniture categories that Treejar actually carries"*, the old
reply named four categories and the new one names three SKUs — two coffee tables
with one unit each and an executive chair, to a research facility that asked
about fume hoods.

Two causes are ruled out by test rather than by argument. The classifier change
was disabled and every `S07` and `R05` turn reclassified identically: zero
differences. The guard did not touch either — no reply was trimmed, no package
line exists anywhere in the run, and no company question appears in either
scenario.

What is not ruled out is that `af4db16` shipped between the baseline and this
round and has never been measured on its own. **This round measures a build, not
a diff.** `tj-jlx4`.

## What this round is worth, stated plainly

One fix is proven and large. One guard works and is worth 0.75 where it applies.
One guard does not run at all. The aggregate did not move, and the honest
reading is that the route work of `tj-ja1v` has not yet been shown to be worth
anything — the routes it changed fire on a minority of turns, and a minority of
turns cannot move a mean that carries ±3.5.

The realistic set is where the headroom is, and it is now measured.
