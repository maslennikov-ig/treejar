# Where Noor stands, what we will not claim, and what we need from you

Date: 2026-08-10
Beads: `tj-vz7o`
Status: draft for the client. Nothing here has been sent.

Your corpus changed what we can measure, and it changed two of our own numbers.
This is the honest version of both, written so you can disagree with any part of
it using your own data.

## 1. The number we published before was not comparable with yours

We reported 20.02/30. You report 6.05/30. Those were never the same
measurement, and the fault is ours for not saying so sooner.

Your convention scores all fifteen criteria on every dialogue and lets an
unearned one stand at zero. Ours dropped the criteria that did not apply and
stretched the survivors back to /30 — which is right for comparing one build of
Noor with the next, and wrong for comparing Noor with a person.

Recomputed on **your** convention, the same 53 stored conversations read
**13.55/30**, not 20.02.

Then we found a second problem in our own method, this one larger. Our readers
had been handed a fixed map telling them which criteria applied, so on average
6.7 criteria per conversation carried a zero that nobody had actually looked
for. Re-reading the same 53 conversations with no map, scoring all fifteen every
time — 1590 of 1590 criterion reads present — gives **18.71/30 ± 1.66**. The
correction from 13.55 is **+5.13 ± 1.35**.

That is a measurement correction, not an improvement in the product. Noor did
not change between those two numbers; we did.

## 2. Why we still cannot put 18.71 next to your 6.05

One thing still differs besides the salesperson: the judge. Yours is
`claude-haiku-4.5`. Ours is a panel of blind readers on a larger model. We have
already measured a **3.8-point systematic shift between two judges reading
identical text** — half the gap anyone would want to claim.

So we are not claiming it. The subtraction is refused in our own tooling, in as
many words, until the judge is bridged.

**This is the single cheapest thing you can unblock.** Section 8 of your note
offers your evaluator prompt. With it, we run your judge over our stored
conversations and exactly one thing differs. Without it, any bridge we build has
to be labelled "reconstructed from the rubric anchors, not the client's prompt",
and it will be worth less to both of us.

One thing we can already say in your favour: on the one criterion where ground
truth is mechanical — did the seller name Treejar and themselves — your judge
gives **zero false passes** and 3.2% false failures. Its calibration is sound.

## 3. The claim we are most confident in is not on the rubric at all

Your fifteen criteria do not score whether anyone replied.

In your 1400 dialogues, salespeople gave a later substantive reply to
**8452 of 9477** customer messages — **89.18%**, and **84.22–90.46%** once
clustered over the seven manager labels, because one desk contributes about 67%
of the volume. Median time to first reply: **1080 seconds**, 95% CI 840–1890.

Noor answered **141 of 141** messages across 53 conversations — 100% — with a
median first reply of **15.61 seconds**, 95% CI 9.99–21.51. On 20 freshly drawn
real customer openings, 20 of 20 answered, median **2.5 seconds**.

Separately, and this is the most useful thing we found in your data: **86.5% of
the dialogues carry a WhatsApp Business auto-responder**, and dialogues with it
average 6.40 against 3.79 without. Roughly 43% of the human 6.05 is a template,
not a salesperson. On collecting contact details that template scores **0.76**
and Noor scores **0.02**. On the one criterion that turns a conversation into a
lead, we currently lose to an auto-reply. We would rather tell you that than
have you find it.

## 4. What we will not claim, in any wording

- **Nothing about conversion, revenue, deal size or close rate.** About 86% of
  your outcomes happen off-channel; an outcome is visible in the messages for
  192 dialogues of 1400. There is no outcome variable in this data, so there is
  no claim — not "we expect", not "consistent with".
- **Nothing about Noor closing deals.** Criteria 12, 14 and 15 — contacts,
  confirming the order, agreeing the next contact — were applicable in 1 of our
  53 conversations. The evidence supports a claim about the *opening* of a
  conversation and nothing beyond it.
- **Nothing about a rubric score predicting an outcome.** We have never tested
  that, anywhere.
- Denominators, unprompted: **1247** evaluated, not 1400 — the 153 unscored have
  a median of 2 messages. Five manager groups, one at ~67%. Dialogue boundaries
  cut heuristically at a 7-day pause. Attachments are absent from the export.
  Our 53 conversations are 19 scenarios, not 53 independent ones.

## 5. Opening quality: measured on your real openings, and not yet ready

We took 20 real customer openings from your corpus, stratified by length, seed
recorded, and ran them end to end. Every opening got a reply, every reply was in
the customer's language, and two of the twenty carried a defect serious enough
that no average excuses it: one quoted a starting price with no catalog row
behind it, and one acknowledged a question about assembly without saying who
would answer it.

Both are fixed, and both turned out to have a cause further upstream than the
sentence that failed — our own instructions asked for a price on a turn that had
no catalog result to give one. We will not report a score for the fixed version
until it has been measured; that rerun has not happened.

We also retired our own acceptance threshold rather than quietly lowering it.
It required 20.0/30, and the applicability maps then showed that **11 of the 20
openings top out at 9.6/30** — a short opening simply does not engage enough of
the rubric to score higher. The threshold was unreachable by arithmetic, not by
quality. Every score we publish from now on carries the ceiling that opening
could actually attain, and we compare builds against each other rather than
against an absolute.

## 6. What we need from you

**The one thing that matters most: the Zoho deal export, keyed on
`crm_deal_id`.** Outcomes are visible inside the conversation for only 192 of
1400 dialogues, so today we have no outcome variable at all. Without it we can
say that Noor does what the rubric asks. We cannot say that Noor *sells*, and
we will not pretend otherwise. Everything else on this page is secondary to
this one export.

**The attachments.** "Can you share some pictures" is the most common
unanswered customer request in your corpus, and the export kept the filenames
but not the files. We cannot reproduce or fix that failure without them.

**One question, and it is not a complaint about your rubric.** Across all 1247
evaluated dialogues in seven months, four criteria were almost never earned by
anyone: sincere compliment **0.00**, the "drill and hole" customer job
**0.01**, asking what the customer's company does **0.02**, discount or bundle
**0.05**. That is 8 of 30 points.

We are deliberately *not* concluding that the criteria are wrong. That people
did not do a thing is no evidence that the thing is not worth doing — the
question is who sold, and we cannot answer it until the deal export arrives.
What we would like to know is only this: are those four criteria still part of
the method you want, so that we know whether to keep building toward them?

For context in the other direction: Noor already scores **0.75** on asking what
the company does, against **0.02** across the human corpus.

**Criterion 11, discount or bundle — decided on our side, for information.**
Noor's owner has ruled that she may never offer a discount: a discount is
either a manager's decision or already inside the catalog price. The zero on
this criterion is therefore policy, not a product defect, and we will print
beside every score that policy caps her attainable ceiling at 28/30 rather than
leave an unexplained zero. Where a package is the right answer, Noor assembles
verified rows and states their combined total at the catalog price, with no
price concession anywhere. No decision is needed from you.

**Your evaluator prompt is no longer requested.** We had asked for it in order
to run your judge over our packets and compare. We have since ruled that
comparison out: a score from your reader and a score from ours are on different
scales, and putting them side by side would be misleading in whichever
direction it fell. We measure our own build against itself, on your openings,
with one change at a time.

## 7. What happens next on our side

The acceptance rules are frozen in code before each measurement, so they cannot
be adjusted after seeing a result. Six measured rounds have since run on your
twenty real openings, each changing exactly one thing, and a separate round
covered every Arabic opening your corpus contains. None of that needs a
decision from you.

What does need you is the deal export. Where you disagree with a reading here,
your numbers win — they are your conversations.

---

Handling note: the corpus itself is held outside version control with restricted
permissions and has never been committed. Nothing in this document contains a
customer message, a company name or a deal amount.
