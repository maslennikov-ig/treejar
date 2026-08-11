# The round after the cleanup: nothing moved, and one reply promised what it cannot do

Date: 2026-08-11
Beads: `tj-rt7w.7`, `tj-vz7o.12`, `tj-riim`
Build measured: `33c8f1f`
Judge: the orchestrating agent, reading blind. No second reader was paid.

## What was authorised and what it cost

The owner authorised 20 Luna calls and 20 GLM calls (about $0.18), then chose to
drop the second reader and have the round judged only by the agent. So: exactly
**20 `openai/gpt-5.6-luna` calls and zero judging calls**, on the frozen
seed-`20260810` set of 20 real customer openings.

Actual cost **$0.004661**. No live traffic, no deploy, no production mutation,
no message to a real person, nothing pushed.

The scenario digest is `2ba7e4fe…`, identical to the stored baseline's, so this
is the same twenty openings.

## Why there is no paired score delta

The stored baseline was scored by `z-ai/glm-5.2`. This round was scored by the
agent. The project's own frozen rule forbids comparing across judges, and
`score_uncertainty.py` refuses it in code, for a measured reason: two judges
reading the same texts differed by **3.8 points systematically**. A delta across
that boundary would be reporting the judge, not the build.

So this round reports its level beside the attainable ceiling, and becomes the
baseline for the next round on the same judge. What can be compared across the
judge boundary is compared below, and nothing else is.

## The result against the contract frozen before the run

| | frozen requirement | observed |
|---|---|---|
| Luna responses | 20/20 | **20/20** |
| Evaluations | 20/20 | **20/20** |
| Correct language | 20/20 | **20/20** |
| Critical failures | **zero** | **1**, in 1/20 |

The round therefore **does not pass its own acceptance**, and it is `tj-rt7w.7`'s
fourth criterion that fails, not the first three.

| measure | result | denominator and interval |
|---|---:|---|
| Weighted score | 15.7/30 — **not a level**, see below | 20 openings of two ceilings; stratified bootstrap 95% CI 13.2–17.9 |
| `raw_total` | 12.8/30 | 20 openings; 95% CI 12.2–13.4 |
| Share of attainable ceiling, 11 short openings | **99%** of 9.6 | mean 9.5 |
| Share of attainable ceiling, 9 richer openings | **77%** of 30 | mean 23.1 |
| Time to first reply | 1.598 s median | 20/20; 95% CI 1.466–1.908 s |

Eleven of the twenty openings are a bare greeting, where eleven of the fifteen
criteria cannot be reached in a first reply at all. On those the bot is at 99% of
what the rubric allows it to earn. Averaging the two bands into one number would
be arithmetic, not a measurement, which is why the aggregate above is labelled
and not used.

## The failure

**Dialog 28.** A job application arrives on the sales channel. The reply says it
will *"route your application and CV to the appropriate team for review"* and
that *"if shortlisted, the team will contact you regarding next steps."* Noor has
no routing capability and nothing supports either promise. It is the same class
as the used-furniture service promise `tj-rt7w.1` removed, and the deterministic
detector cannot see it: every number is grounded and the language is right.

The presentation is broken too — the reply signs off *"Kind regards, Noor,
Treejar"* and then the name question is appended after the signature.

**This is not attributable to the cleanup.** The stored `8e50dea` reply on the
same opening did the honest thing: it said it could not handle recruitment
through the sales channel and named the official route. Nothing in the
`tj-rt7w` epic touches recruitment, and Luna is stochastic; one draw each. It is
a live defect regardless of cause, and it is `tj-riim`.

## What the round says about the cleanup, which is what it was for

The structural work does not show up in the behaviour, which is the expected
result and the one worth stating plainly:

- **Zero of the twenty replies is a new failure of the kind the epic touched.**
- The one defect the epic *did* fix is fixed **in the live path**, not only in
  the stored replay. Dialog 789 asked whether Treejar buys used office tables.
  The baseline answered *"Yes, Treejar can help you sell or assess an office
  table you already have"* and asked for photos and an asking price. At
  `33c8f1f`: *"Treejar supplies office furniture, but we don't buy, resell,
  broker, value, or assess customer-owned furniture"*, then it offers to help
  furnish instead. `tj-rt7w.1` holds outside the test suite.
- The three known defects that were **not** in scope reproduce exactly as
  recorded, which is what a behaviour-preserving refactor should do to them.

## The three that reproduced, from `tj-vz7o.12`

- **Dialogs 28 and 875.** The customer signs their name, the reply opens by
  using it, and then asks *"And how should I address you?"*. Still open, and
  still needs the engine check before anyone adds a guard: the harness always
  passes `customer_name=None`.
- **Dialogs 436 and 1067.** A named category and a detailed product question,
  and neither reply quotes a row or a price. New this round: the behaviour is
  **inconsistent, not absent** — 366, 442, 692 and 819 all quoted priced catalog
  rows on the same run. Whatever selects the quote is the thing to look at, not
  the greeting rule.
- **Dialog 420.** *"SIZE ?"* with no referent is still answered about *"this
  cabinet"*, an item the customer never named. The dimensions are grounded in
  the injected evidence, so only the referent is invented, which is exactly why
  no detector sees it.

## What we do not claim

- **No paired delta against the previous round.** Different judge.
- **No absolute /30 level.** Two ceilings, and the rubric's own arithmetic
  forbids averaging them into one.
- **Nothing about conversion, revenue, or close rate.** One turn, no outcome
  variable.
- **Nothing about the cleanup improving quality.** It was not supposed to. The
  claim is that it changed nothing, and the evidence for that is the guard and
  policy sources being byte-identical, 3557 tests green, 31 stored raw outputs
  replaying to an identical digest, and this round finding no new defect of the
  kind the epic touched.

## The instrument

The judge is the orchestrating agent by default now, not by instruction.
`scripts/corpus_bridge/real_opening_acceptance.py` stops after the generation
arm and writes a blind reading pack; `ingest-judgment` takes the reading back
through the same scoring, applicability and critical-failure code the paid
reader would have fed. Paying a second reader takes `preflight --second-reader`,
and it adds a scale beside the agent's reading rather than replacing it.
