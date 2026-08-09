# Two independent research reports, and the one thing they both say we get wrong

Two models were given the same brief and answered separately. They agree far
more than they differ, and where they agree they contradict something we
actually do. This is the cross-check against our own measurements, and what it
changes.

Sources, in `docs/Research/`:
`2026-08-09-methodology-research-A-ranked-decision-snap-jtbd-bant.md` and
`2026-08-09-methodology-research-B-snap-spine-compressed-spin-challenger.md`.

## What both concluded, independently

| | report A | report B |
|---|---|---|
| Spine | SNAP | SNAP |
| Question engine | Jobs-to-be-done, one question | SPIN, compressed to one question |
| Reserved for large projects | Challenger, project fork only | Challenger, project fork only |
| Explicitly rejected as a spine | SPIN, Sandler, MEDDIC, Solution Selling | SPIN, Sandler, MEDDIC, Solution Selling |
| Price and stock | answer first, do not gate | answer first, do not gate |
| Fork | on quantity or complexity | on quantity **or** complexity, never a magic number |
| The one construct with real evidence | adaptive selling (Franke & Park) | adaptive selling (Franke & Park) |
| The 15-rule checklist | third keep, third adapt, third drop | a good library, a bad quality target |

Both are candid that the named methodologies have thin independent evidence.
The only construct either will vouch for is **adaptive selling** — behave
differently for different customers — and both cite the same meta-analysis for
it. Neither claims SNAP is proven; both say its prescriptions match our measured
reality, which is a weaker and more honest claim.

## The finding that matters most, and it is about us

Both reports name the same cardinal error, and one of them gives it verbatim as
its example of what not to do:

> Hi! Welcome to ABC Furniture 😊
> May I know your good name please?

That is our name gate. `src/llm/opening_guard.py` sends it deterministically on
the first turn of every conversation where the customer's name is unknown.

Measured against our own data that is worse than it sounds. **34% of real
customers open with a bare greeting and nothing else, and 36% never send a
second message.** So for a third of conversations, the single reply they will
ever receive is a request for their name.

Then we checked what a customer actually sees, and when:

```
packet    first turn      first price or product
R01       name-gate       turn 3
R02       name-gate       never
R03       name-gate       never
R04       name-gate       never
R05       name-gate       turn 3
S01       name-gate       turn 3
S02       name-gate       turn 2
S05       name-gate       turn 2
S07       name-gate       turn 2
```

Nine of nine conversations spend turn one on the name. On the realistic set, not
one shows a price before turn three and three never show one at all.

**The real median conversation is two customer messages. So the median customer
never sees a product or a price.** That is not a scoring problem, it is the
business problem, and no amount of directive tuning reaches it.

## The second finding: our own R01 shows the failure whole

The realistic run captured it end to end:

```
customer: Hi
Noor:     Hello, I'm Noor from Treejar. May I know your name so I can address you properly?
customer: Sara
Noor:     I can help with products, prices, stock, delivery, or quotations. What do you need?
customer: need chairs for the office
Noor:     [three real chairs, prices, stock, "how many do you need?"]
```

Turn three is good. Turns one and two are the two turns most customers get, and
both are spent asking the customer to do work. Report B's prescription for
exactly this case is a single message that introduces, names what we can do
*right now*, and offers an anchor price with one easy question:

> Hi 👋 Noor from Treejar. I can help with price, live stock and UAE delivery
> and installation. Chairs from AED 140, workstations from AED 1,800 — are you
> looking at chairs, desks, or a full office?

## What the reports say about the fifteen rules

Both would cut the checklist substantially. The three we have spent the most
effort on are the three they would drop or fork:

- **Rule 6, sincere compliment.** Both say drop it on a transactional order.
  Report B: a QA rule demanding a compliment produces "That's a great choice!"
  on every SKU, which is not rapport but a recognisable template. We measured it
  at 0.27 of 2 and have been trying to fix it. It is worth **2.03 points** we
  should delete rather than chase.
- **Rule 10, comprehensive solution.** Both say fork it: genuinely valued on a
  project, friction on a seven-chair order. We charge it in 52 of 52 scorings.
  Worth **3.26 points**, the largest single item on our own loss table, and the
  research says most of it should not be charged at all.
- **Rule 13, company activity.** Both say project fork only. We narrowed it
  yesterday to conversations that stay open-ended; the research would narrow it
  further.

They also both say what we half-built by accident: rule 11 as a **package price,
never a discount**, is the correct reading, and rule 3 should never cost a turn.

## Where the research and our runtime already agree

Worth stating, because it means yesterday's work was pointed the right way:

- We stopped inventing price ranges and now answer budget questions from catalog
  rows. Both reports insist price answers come first and be truthful; report A
  cites a field experiment that transparency raises purchase intent.
- We moved rule 11 to a verified package. Both name discounting as the wrong
  engine, and package price as the right one.
- We gave the model the four facts to gather and one recording tool instead of
  regexes. Both warn against interrogation; the recording tool is what lets one
  folded question do the work of four.
- Rule 15's applicability now separates "declined the paperwork" from "not
  buying today". Report B independently says a follow-up should exist only when
  there is a real date or event, not as a mechanical ritual.

## What this changes, in order of value

1. **The name gate has to go, or move.** This is the highest-value change
   available and it is not a prompt tweak: it is a deterministic guard in
   `opening_guard.py`. The name can be asked for later, folded into a message
   that has already been useful, or taken from the WhatsApp profile. **Owner
   decision needed** — it touches the first thing every customer sees.
2. **The first reply must carry an anchor price.** "Chairs from AED 140,
   workstations from AED 1,800" is answerable from the catalog and turns a
   greeting into a useful reply.
3. **Fork the conversation** on quantity or complexity, and stop charging
   rules 6, 10 and 13 on the transactional side.
4. **Change what we measure.** Both reports independently propose replacing
   conversation-level checklist scoring with something closer to: did the first
   reply carry utility, was the explicit question answered, was every question
   worth its turn, did the conversation reach a quotation. Report B's phrasing is
   the sharpest — measure **time to first useful reply**, not time to first
   reply.

## The caveat both reports volunteer, and we should keep

Neither claims proof. There is no controlled trial of SNAP against SPIN in
asynchronous B2B furniture sales, and both say so plainly. Report B's
recommendation is explicit about it: our own production dataset should outweigh
any methodology author's claim. That is the same rule we have been working by
all week, and it is why the next step is a measured comparison rather than
another rewrite.
