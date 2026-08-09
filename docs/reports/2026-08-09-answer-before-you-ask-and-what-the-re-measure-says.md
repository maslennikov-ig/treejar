# Answer before you ask, and what the re-measure says about the widening

2026-08-09. Delivering the ordered plan in
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`.
Every figure below comes from stored evidence or from a test in this
repository. Nothing here has met live traffic; the last paragraph says what
that costs.

## 1. The resumed question: the filed hypothesis was wrong, and the cause was one layer earlier

`tj-jxv7` named a hypothesis and asked for it to be checked first. It does not
hold. `combined_text` is rewritten to the stored question at `engine.py:16241`
and `_turn_runtime_directives` runs at `engine.py:16877`, so the resumed turn
does see its own text. Checking it cost one probe and saved writing the wrong
fix.

What actually happened is upstream of the directives. `classify_question` read
`"hi do u have ch616 in black"` as `service_low_risk`, because the message
carries no product word and `_NUMBER_RE` needs a word boundary in front of its
digits, which `ch616` does not give it. The turn then ran on the verified-answer
branch under its own directives — *answer only from the FAQ facts already
provided*, *do not invent any prices* — against an empty FAQ. None of the turn
directives was attached at all, including the one that forbids a reply which
adds nothing. A customer asking whether we stock a chair we do stock was asked
for a quantity, and the code that would have stopped that was never reached.

This is the second half of `tj-6f4z`. That issue fixed `_sku_lookup_variants`
so a compact SKU reaches the catalog row; the classifier that decides whether
the turn is about a product at all was never told.

Fixed: a SKU written without a space is a product signal. The letters and the
digits must be adjacent, because allowing a separator would read `"for 12"` and
`"AED 300"` as SKUs; the spaced and hyphenated forms already classify as
product. Cyrillic letters count, since 7 of 920 Treejar SKUs begin with
Cyrillic `СН`.

Measured after the fix, in `tests/test_llm_engine.py`: the resumed turn carries
`substantive_reply_directive` and the consultative opening, and carries neither
service-branch directive.

## 2. The routes: answer first, then ask

`tj-ja1v` is the spine, and three of the eight routes it named are already
gone. Of the five left, four already write their prose through the model over
figures the code owns. The two that did not were the two that only asked.

**`product-quantity-clarify`** said *"I have these product references:
CH 616 NEW black. Please confirm the quantity for each item so I can check
availability and prepare the next step."* The price and the live stock the
customer had just asked for were one catalog row away. It now reads the row and
says the price and the stock, then asks the quantity — which is a real question,
because the total depends on it. Where nothing resolves against the catalog the
old wording stands, since then there genuinely is nothing to add.

**`exact-quote-missing-details`** and **`quote-resume-missing-details`** asked
for a name, a company and a delivery address without ever saying what the
quotation would be for or what it would come to. The items and quantities were
already resolved when the route was reached. They now state what the quotation
covers, at what unit price and total, and then ask.

Both lookups are read-only and both are wrapped: a lookup failure costs the
fact, never the turn.

The contract is now recorded per route in `src/llm/deterministic_routes.py`. A
route that owns a customer-visible turn carries a verified fact, acknowledges
what the customer just said, or escalates — or it asks and gives nothing, which
is the shape that scored 13.3 against 24.8. `ROUTES_THAT_ONLY_ASK` names the
eight that still do, written out rather than derived, so a new one cannot join
it without that list changing in the same commit. `sales-fallback` is the one
worth revisiting: two of its three branches ask the customer to go and find a
competitor's specifications rather than naming a comparable catalog row.

## 3. The realistic set grew by four

`R06`–`R09` added to the protected runner, to the shapes the ordered plan
named and the first five do not reach: a customer who sends two messages and
leaves without answering anything; a voice note carrying a SKU the catalog does
not hold; Arabic that switches to English mid-thread; a delivery question and
nothing else. `S01`–`S10` are untouched.

## 4. The re-measure: rule 9 is not the problem any more, and rule 13 is total

`tj-2m5m.4` said re-measure before touching it. Done, from the stored panel
scores at `ac36265` — 82 reads over 41 packets, two readers each, no live
traffic and no judge calls. Cost is what the packet's score would gain if that
one rule went to full marks, averaged over the reads where it is charged.

| rule | | charged | mean /2 | cost /30 |
|---|---|---|---|---|
| 6 | a sincere compliment | 24/82 | 0.42 | 2.03 |
| 8 | clarifying questions | 76/82 | 1.63 | 0.56 |
| 9 | the job to be done | 70/82 | **1.51** | 2.30 |
| 10 | a solution beyond the request | 24/82 | 0.88 | 2.37 |
| 11 | a discount, bundle or bonus | 18/82 | **0.28** | 3.22 |
| 13 | what the company does | 12/82 | **0.00** | 2.25 |
| 14 | confirm the next step | 2/82 | 1.00 | 1.50 |

Rules 14 and 15 are charged twice each. Those two rows are noise and are shown
only so the table is not read as complete.

Three things follow, and the first two change the plan:

**Rule 9 has moved from 0.40 to 1.51.** `tj-2m5m.4` was filed on r9 at 0.40
and r10 at 0.54 costing 5.10 points together. Half of that issue is closed.
The consultative directives did land here.

**Rule 13 scores zero on every read where it is charged.** Twelve reads, six
packets, not one above zero. That is not a gradient, it is a directive that
never fires. The instruction exists and is explicit — *knowing the company's
name is not knowing its line of work* — and it is worth exactly nothing. Rule 7
was in this position before the name gate started carrying the value
proposition deterministically, and moved 0.08 to 1.66 when a guarantee replaced
it. This is the same shape and the next candidate for the same treatment.

**Rule 11 is the worst-scoring charged rule at 0.28.** It was settled on
2026-08-08: the owner declined a discount, so the directive offers a package of
verified rows at their combined total. That directive is not landing either.

Rule 10 at 0.88 over 29% of packets is confirmed as the ordered plan stated it,
and it is now the third-largest of these, not the first.

## 5. Two transcripts read by eye, and what they say

Rule 5 of the engagement list, and it earned its place again. `R02` and `R04`
from the `ac36265` packets, second turn each, both model-written — no route is
involved and none of the work above touches this path.

`R04`'s customer wrote *"hello we are moving to a new office in business bay
next month and i need desks and chairs for about 14 people plus something for
the meeting room what can you do and how fast"*. The reply bullets that
requirement straight back — 14 desks, 14 chairs, a meeting table — and then asks
four numbered questions: desk style, meeting-room capacity, look or budget,
move-in date. No product was searched. No SKU, no price, no stock. *How fast*
went unanswered. Every number in the reply is one the customer supplied.

`R02` does the same in three questions instead of four.

Three written rules forbid this and none of them bound. The system prompt says
to ask for missing facts *inside the conversation, never as a form*. The
consultative directive caps the whole reply at one question. The substantive
directive says restating what they told you is not an addition, and that if a
tool can look something up now, this reply does it rather than handing it back.
Four numbered questions and no catalog row breaks all three, on the opening
shape a third of real customers arrive in. Filed as `tj-6tx6`.

The opening guard is the counter-example that makes the point: the anchor line
*"Chairs from AED 99, desks and workstations from AED 154"* is there on turn 1
of both, because it is a guarantee and not an instruction.

## What this round did not do

It did not change the rubric. `AC-01`–`AC-30` and the applicability contract
frozen on 2026-08-09 are untouched, so this build stays comparable with the two
baselines: project 19.95 ± 0.93 over 11.0 applicable rules, transactional
20.77 ± 4.41 over 7.6.

It did not act on rule 13, rule 11 or the form. All three are directive
failures whose fix is a deterministic guarantee, and none can be shown to have
worked without a deploy and a repeated run. Writing one now would put an
unmeasurable change into the same round as the route work and leave nobody able
to say which moved the number. `tj-odeq`, `tj-wvo4` and `tj-6tx6` carry them,
each with its own acceptance criterion. That is a decision the owner should
make with the table above in front of them, not a gap.

It has not met a live conversation. `tj-jxv7` asks for its fix to be verified
in one, and `tj-ja1v` asks to be measured on the transactional baseline of
20.77. Both need an acceptance run, which is live traffic and needs its own
grant. Until then every effect here is a headroom estimate.
