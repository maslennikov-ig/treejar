# The first run that saw the directives: +2.0, and three rules that did not move

Every dialogue directive written since `14881b5` had been shipped without ever
meeting a live conversation. On 2026-08-08, with owner authority for the deploy
and the run, `a830001` went to production and was measured. This is what came
back.

Run: ten scenarios against the deployed runtime, S01-S08 three times each,
S09 and S10 once. 26 transcripts, 52 scorings by two independent blind readers.
Evidence at `.git/codex-orchestration/noor-e2e-acceptance/remediation-live/`
under `tj-2m5m-accept-a830001-20260808-r{1,2,3}` and `tj-2m5m-panel-a830001-20260808`.

## The number

```
mean 13.43 -> 15.39
paired delta +1.95 +/- 1.58 (95%, n=10 scenarios)
gap to 24.0: 8.6
```

The interval clears zero, so the movement is real. It clears it by a margin
thinner than it looks, and the next section says why.

| scenario | baseline | now | delta |
|---|---|---|---|
| S01 | 18.40 | 16.72 | −1.68 |
| S02 | 15.75 | 17.97 | +2.22 |
| S03 | 15.10 | 16.77 | +1.67 |
| S04 | 17.00 | **20.50** | +3.50 |
| S05 | 17.30 | 15.77 | −1.53 |
| S06 | 6.75 | 7.35 | +0.60 |
| S07 | 15.50 | **22.65** | **+7.15** |
| S08 | 9.50 | 11.45 | +1.95 |
| S09 | 8.85 | 11.25 | +2.40 |
| S10 | 10.20 | 13.45 | +3.25 |

Baseline is the stored `5656c82` panel under the corrected applicability map, so
both sides are charged for the same rules.

## Two noise sources, now separated — and the panel is the louder one

This is what the repeated runs were for.

**Generation noise is small.** The same scenario run three times moved by a
within-scenario sd of **0.84** on average, 2.05 at worst (S02). S04 and S06
returned the same score all three times. So the owner's decision to leave
`PATH_CORE_CHAT` unpinned costs about a point of scatter per scenario — real,
manageable, and now measured rather than assumed.

**Reader noise is larger, and worse than last round.** The two readers differ by
a mean of **2.86** points on the same transcript, up to 6.0 on S05 and 5.2 on
S08. The previous panel measured sd 0.9. The likely cause is load: each reader
scored 26 packets here against 10 before. Whatever the cause, it has to be said
plainly — **the instrument was noisier this round than the thing it measured.**
The headline delta survives only because it averages 2-6 scorings per scenario
before the pairing.

Treat +1.95 as the best available estimate and not as a precise one. The
per-rule findings below rest on 52 scorings each and are much firmer than the
total.

## What actually changed, rule by rule

| rule | applies | before | now |
|---|---|---|---|
| 3 asked how to address | 34/52 | 1.40 | **2.00** |
| 5 genuine interest | 52/52 | 1.25 | **1.71** |
| 9 drill and hole | 52/52 | 0.90 | **1.25** |
| 10 comprehensive solution | 52/52 | 0.40 | 0.54 |
| **11 discount, bundle or bonus** | 18/52 | **0.00** | **0.33** |
| 15 next contact date | 20/52 | 0.25 | **0.50** |
| 6 compliment or thanks | 52/52 | 0.40 | 0.27 |
| **7 Treejar's value proposition** | 52/52 | 0.10 | **0.08** |
| **13 what the client's company does** | 22/52 | 0.00 | **0.00** |

**Rule 11 broke zero for the first time.** It had been 0.00 in every one of 70
prior scorings — 20 on the panel, 50 on the paid judge. Quoting the pieces as
one package at their combined verified total is a thing Noor can actually do,
and a discount never was.

**Rule 15 doubled** where it applies, so proposing a named day instead of an
open ending lands.

**Rules 6, 7 and 13 did not move at all.** They are the three the 2026-08-07
directive was written for, they have now had a live run, and rule 13 is still
**0.00 across all 22 scorings where it applies** while rule 7 sits at 0.08 of 2.
Searched directly rather than through the readers: across all 26 transcripts the
value proposition appears **0 times** and the company question **0 times**. That
is total absence, not partial compliance, and it turned out to have a mechanical
cause — see the next section.

## Why: two escape clauses, both mine

Ruled out first, in order. **Not a deploy gap:** both directives are present in
`/opt/noor` at `a830001`, checked inside the running container. **Not an early
return:** the `_turn_runtime_directives` call site sits directly under the main
`try:` in `process_message`, not in a rare branch, and the scenarios that miss
the moves carry the plain `openai/gpt-5.6-luna` label with no route suffix, so
they took none of the earlier returns. **Not the tool layer:** the v4 runtime
evidence shows `search_products` returning on the same turns.

The cause was in the directive's own wording.

**Rule 7 was self-cancelling.** `src/llm/opening_guard.py` prepends
"Hello, I'm Noor from Treejar." to every first turn. The directive said *"if you
have not already said it in this conversation, say what Treejar is"* — a
condition the guaranteed opening satisfies inside the very reply the directive
is trying to change. It asked for something it had already excused.

**Rule 13 was starved by its own bound.** *"Keep the whole reply to at most one
question: if you are already asking one for another reason, fold this into it or
leave it for the next turn."* There is always a more urgent product question, so
the company question was always the one deferred — on every turn, forever.

Both are now fixed. Naming Treejar and saying what Treejar offers are stated as
different acts, with the greeting explicitly not discharging the second. The
company question rides in the same sentence as whatever else Noor needs to know
and counts as one question. The bound itself stays: the transcripts are not
interrogations, and that is the bound working.

Two tests encode the finding so it cannot come back, and the fix is a hypothesis
until the next run measures it — the target is the value proposition and the
company question no longer being 0 of 26.

Rule 6 sits in the same family but had no hard escape clause, so it is not
explained by this.

## S08, unchanged

The scenario the substantive-reply directive was written against still opens
with a bulleted restatement of the customer's own requirement and still closes
by handing back a next step Noor holds the tools to perform:

> Confirm the availability, unit pricing, and delivery/assembly charges for
> three walnut units, then check whether the total fits within the AED 6,000
> budget

It scored +1.95, so something moved, but the specific defect did not. This one is
**not** explained by the escape clauses above: `substantive_reply_directive` has
no condition to satisfy and fires on all four of S08's turns. It stays open.

One false lead worth recording. The per-turn `runtime_execution_evidence`
reports `tool_names: null` on every turn of every scenario — which looks like
"Noor never opened the catalogue" until you notice it also reports null for S07,
where she quotes three products with verified prices and stock. The field is
simply not populated. It is not evidence of anything.

## The harness fix that made repeats possible

`tj-r1vk` is closed. S09 and S10 must reach the real protected chat — S09 sends
a PDF there, S10 records an opportunity — so they cannot take the per-run phone
suffix the other eight use, and they had been accumulating every round into one
conversation. The runner now calls the product's own reset service before each:
the old conversation is renamed with an `#archived-` suffix, closed, its
escalations resolved, and a fresh one opened. Nothing is deleted. Verified in
this run — every one of the 26 transcripts has its own conversation containing
exactly its own turns.

## The cap, stated rather than hidden

S09 and S10 ran **once**, not three times. Repeating them would multiply real
business effects — a quotation PDF sent to the test chat, a CRM opportunity
recorded — and nobody has authorised that. Their deltas therefore carry no
repeat protection and should be read as observations. The other eight carry
three runs each.
