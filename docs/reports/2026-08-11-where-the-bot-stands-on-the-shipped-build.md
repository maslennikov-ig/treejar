# Where the bot stands on the shipped build

Date: 2026-08-11
Beads: `tj-vhto`, `tj-0s42`, `tj-4q79`, `tj-2p4c`, `tj-9dp2`, `tj-ge07`
Build measured: `3682203`
Judge: the root orchestrator, reading blind. No second reader was requested.

The owner asked one question — how good is the bot right now — and authorised
one round to answer it. This is that round, and the two things it found that
were not the question.

## Authorization, calls, and cost

Exactly **20 `openai/gpt-5.6-luna` generation calls, zero scoring calls**, and
**one repair-judge call** raised by a flag. Actual cost **$0.005386**. The
frozen scenario digest was `2ba7e4fe…`, identical to all three prior rounds.

Coverage was 20/20 responses and 20/20 in the customer's language. The root
read all twenty replies and all three hundred criteria blind.

No second reader, live traffic, deploy, production mutation, real-user
message, push, or model-configuration change occurred.

## The number

| measure | mean | 95% interval |
|---|---:|---:|
| Weighted score, 30-point scale | **15.3** | 12.6 to 17.9 |
| Raw criterion total, client's convention | **12.8** | 12.0 to 13.5 |
| Critical failures | 1 | — |

The single critical is dialog 1067, and it is the known deterministic false
positive: the reply used a SKU present in the catalog evidence and the numeric
detector read digits inside it. Tracked as `tj-2p4c`. The root reading found no
unsupported claim anywhere in the twenty.

## The cut that actually tells you something

An aggregate across these twenty is close to meaningless, because eleven of
them are a bare greeting where at most 9.6 points are reachable and nine carry
a real request where all 30 are.

| opening | count | attainable | mean | share of ceiling |
|---|---:|---:|---:|---:|
| greeting only | 11 | 9.6 | 9.5 | **99%** |
| a real request | 9 | 30.0 | 22.4 | **75%** |

That is the honest state of the product. On an opening where nothing more is
reachable, the bot takes essentially everything available. On an opening where
a sale is reachable, it takes three quarters of it, and the quarter it misses
is the same quarter every time: it lists the right products and asks about
quantity, and it does not ask what the customer is actually trying to do.

Two of the nine scored a full 30, and both did the same thing — asked how many
people and how they work, rather than which item. That is the difference,
written out.

## What moved, and why it is not a product result

| against | weighted delta | 95% interval | raw delta | 95% interval |
|---|---:|---:|---:|---:|
| previous round `tj-n7p4.5` | −1.52 | −3.71 to +0.24 | −0.60 | −1.35 to −0.05 |
| before both accepted stages | −0.37 | −2.51 to +1.44 | −0.10 | −0.90 to +0.65 |

Criticals were 1 to 1 in both comparisons.

The movement is not diffuse. Five openings account for all of it:

| dialog | weighted | cause |
|---|---:|---|
| 819 | −22.5 | the repair judge's provider failed; the customer got a handoff notice |
| 28 | −12.2 | the same reply shape, read more strictly than last sitting |
| 875, 1291 | −0.7 each | likewise |
| 366 | +5.6 | generation variation |

So the build did not get worse. One infrastructure failure and one stricter
reading did.

**Nothing between the two rounds could have changed a first-turn reply.** The
only code change was `tj-t6ug`, whose guards do not run on a first turn, and
the protected replay proves the rendered text is byte-identical before and
after. A raw delta of −0.60 with an interval excluding zero, on a change that
cannot have had an effect, is a direct measurement of this instrument's floor.

That is the answer to whether the earlier round's +0.50 raw was a result. It
was not.

## The two findings

**The repair judge could not afford the answer it asked for — `tj-0s42`,
`tj-lj09`.** Dialog 819 asked a good, detailed question: a two-person
workstation, mobile drawers, delivery in two to three days, and whether
assembly is included. The reply raised one grounding flag, the single
second-vendor call failed, and D4 did exactly what it was built to do —
replaced the draft with a manager-handoff notice and escalated. The customer
received a sentence acknowledging none of what they asked, and it scored 7.5
against a set mean of 15.3.

The round recorded that failure as `provider_unavailable`. That was wrong, and
nothing in the record had ever established it: two call sites caught every
exception and stamped it with that one label.

Replaying the identical request twelve times on 2026-08-12 — same digest,
`a39e8bd0…` — settles it. The provider was up throughout. Every failure was our
own output schema rejecting a truncated answer. A complete answer from this
model costs 720–1494 completion tokens, of which about 300 are the JSON we
asked for and the rest is reasoning GLM 5.2 bills for and never returns; the
path allowed 800. At 800 the call cannot succeed. At 1200 it succeeded twice in
four. At 2000 it succeeded eight times in eight, worst case 15.3s of the 20s
allowed.

Asking this vendor to stop thinking does not work — `enabled: false`,
`effort: low` and `max_tokens: 256` all left completion around 1430 tokens — so
on that path thinking had to be afforded rather than declined.

**And then the same question asked of the judge's answers — `tj-0h5d`.** Once
the calls stopped failing, we measured what actually reached the customer, and
it was one reply in four. `review_flagged_reply` re-renders every correction
and discards it whole if a flag survives, and the prompt never said so: GLM
reworded the flagged promise instead of removing it and lost the reply twice in
four. The prompt also called the deterministic candidate untrustworthy while
offering `cannot_fix` as the careful answer, and a cheaper second vendor took
that exit two times in three, quoting the line back at us.

Both failures were ours. With the rule stated and `cannot_fix` priced, both
vendors deliver four in four. The path now runs `deepseek/deepseek-v4-flash`,
chosen by replay rather than reputation: same delivery, about a fortieth of the
price, no more waiting. Measured on both flagged replies we hold: **7 of 8
delivered, $0.000596 for eight calls, 5.6–10.2 seconds.**

What we are not claiming is the more useful half. All seven delivered replies
were byte-identical to the repair the deterministic guard produces for free. On
these two cases the paid judge adds nothing — it has stopped throwing the free
answer away, which is the whole gain. And the sentence that produces the
delivery rate is the sentence that turns the judge into a copier: under the old
prompt GLM independently noticed the reply had invented a delivery city the
customer never named, and that catch is gone. Delivery was bought with
independence, knowingly. Two flagged replies is the entire evidence base.

The fallback is right. Reaching for it after one failed call is not, blaming
the vendor for our own budget is worse, and grading a judge on a rule we never
gave it is worst of the three.

**The root judge drifts between sittings — `tj-4q79`.** Dialog 28 lost 12.2
points with no code path to explain it. This reading penalised asking for a
name the customer had just signed, and an Arabic reply that introduces itself
twice; the earlier reading scored those shapes as fully met. Both readings were
blind, both were mine, and they disagree.

This is the 3.8-point cross-judge shift already on record, appearing between
two sittings of the same judge. It bounds what any single round here can claim,
and it is now tracked rather than assumed away.

## What this round cannot say

- **Anything about selling past the first turn.** Rules 14 and 15 — confirm the
  next step, agree the next contact — were applicable on 0/20 again. Every
  frozen set in this project is first-turn only, tracked as `tj-ge07`.
- **Anything against the client's 6.05.** A different judge read that. Our own
  tooling refuses the subtraction, and the cheapest way to unblock it remains
  their evaluator prompt, offered in §8 of their note.
- **Anything about conversion, revenue, or deal size.** Outcomes are outside
  the channel for 86% of the corpus.

The public summary still labels the judge `z-ai/glm-5.2` while the protected
run-state records `root-orchestrator` and zero scoring calls; that metadata
defect is `tj-9dp2` and the numbers here come from the run-state.

## Protected evidence

Transcript-bearing evidence stays outside Git under
`.git/codex-orchestration/corpus-bridge/tj-vhto-round-20260811/`. This report
carries dialog identifiers, integers, and digests only. `paired-comparison.json`
and `paired-vs-prestage.json` record the paired integer deltas and were written
by `scripts/corpus_bridge/pair_rounds.py`, which refuses to pair across judges
or across frozen sets.
