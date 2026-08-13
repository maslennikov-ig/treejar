# Root reading convention

The judge of a measured round is the orchestrating agent, reading blind. The
owner decided on 2026-08-13 that this is the reading they want and that a paid
second reader is not to be bought. That decision only holds if a later sitting
reads to the same standard as this one, so the standard is written here.

This is not a rubric. The rubric is the client's, frozen on 2026-08-10, and
nothing here may change which rules apply or what they are worth. This records
only how the root judge decides between 0, 1 and 2 on a first-turn reply, and
it is derived from the scoring actually applied across the six rounds of
2026-08-12 and 2026-08-13, not invented beside them.

Where a case below conflicts with a reading, the reading is wrong, not the
case. Where a case is absent, score it and add it here.

## The standard that applies to every rule

- **2** — the rule is met as a competent salesperson would meet it.
- **1** — the rule is attempted and something real is missing.
- **0** — the rule is not attempted at all.
- A rule the applicability map marks not-applicable is not scored, and its
  absence is never a defect.
- Score the reply the customer would receive, not the model's draft. The
  canonical opening is part of the reply.
- Never score the same defect twice under two rules. Pick the rule it belongs
  to and leave the other at what it independently earns.

## Rule 1 — greeting, the name Noor, the company Treejar

Deterministic. The opening guard prepends it, so this is 2 unless the reply
does not begin with it. The Arabic opening carries the persona in Latin script
and the company in Latin script; that is still a 2.

## Rule 2 — the introduction is polite and professional

- **1** where the reply leaks our machinery to the customer: naming a catalogue
  lookup, a tool, or an internal step.
- **1** where the reply promises to find something without saying it is not in
  the evidence it has.
- **1** where a reply in one language leaves an English product term untranslated
  inside otherwise fluent Arabic.
- **1** where the reply contradicts itself inside three sentences — sending a
  request elsewhere and then pursuing it anyway.
- **1** where a catalog row is quoted under a family label it does not belong
  to. Added 2026-08-13 from `tj-68au`: a row described in the catalog as a
  coffee table for reception and lounge areas led the answer to a customer who
  asked for an office table. True of the row, false to the customer. This is
  the same shape as `tj-jlx4`.
- **1** where the price anchor is prepended to a message that carries no
  furniture need. Added 2026-08-13 from `tj-68au`: a job application received
  chair and desk prices and then a redirect to the careers channel. It is the
  self-contradiction case above, in the order the guard produces it.
- **Not charged**: an anchor whose price floor no row in the family it names
  can honour. The reply is polite, professional and every figure in it is a
  real catalog row, and the customer cannot see the gap from this message. It
  is a catalog-family defect, tracked as `tj-3jo0`, not a defect of the
  introduction. Recording this because the alternative — charging it — would
  silently re-price most of the frozen twenty on something the model did not
  author and cannot fix.
- Otherwise **2**. Length is not a fault; a bulleted set of priced rows is good
  selling.

## Rule 3 — the customer was asked how they would like to be addressed

- **2** where the reply asks, folded onto the discovery question.
- **2** where the customer signed the opening and the reply does not ask. A
  question already answered must not be asked again, and asking one whose
  answer the reply has just used is worse than not asking.
- **1** where the reply asks a customer who signed.
- **0** where nobody signed and nobody was asked.

## Rule 4 — friendly tone and active listening

The rule is about whether the reply heard the message, so it is scored against
what the customer actually put in it.

- **1** where the customer asked several things and the reply answers some and
  drops the rest silently. Naming a thing as unconfirmed counts as answering
  it; ignoring it does not.
- **1** where the reply mirrors the words back without showing it read them.
- Otherwise **2**. Returning a greeting in its full traditional form is 2, not
  a bonus.

## Rule 5 — genuine interest in the customer's needs

The rule the readers disagree on most, so the line is drawn on the options the
question offers, which is the part the model writes.

- **2** where the question asks what the space has to do, or offers choices
  that are **kinds of work or kinds of space** — one person's desk, a meeting
  room, a reception visitors wait in.
- **1** where the question offers **a list of what we sell**, or is generic
  enough to ask nothing at all ("how can I help you today" and no more).
- **1** where the customer's message contains **no furniture need** — a job
  application, a delivery notification, a cold marketing or investment pitch.
  The rule is charged on those by the frozen rubric and cannot be earned on
  them. That is a property of the set, not a defect, and the rubric is not
  changed for it. It puts rule 5's ceiling on the frozen twenty at 1.95.
- A mixed list is scored by what it leads with. Added 2026-08-13 from
  `tj-68au`: a list that leads plausibly and then turns to catalogue
  categories — "office desks, ergonomic chairs, workstations, meeting-room
  furniture" — is **1**. Chairs are not a kind of space, and one product term
  after the lead settles what the list is. A list that closes on "or another
  product" is **1** whatever it led with.

## Rule 7 — the value of Treejar's offering was explained briefly

- **2** where the offer is stated once, by the canonical opening, and not
  repeated.
- **1** where the reply says what Treejar does a second time in any words,
  including a near-synonym, and including a catalogue breakdown of what we
  supply. A capability list right after the opening is a restatement.
- **1** where the reply begins with a lower-case fragment of the offer clause.
- Naming our line of business in order to **decline** something outside it is
  not a restatement; it is the answer.

## Rule 8 — clarifying questions about the requirements

- **2** for one apt clarification: the thing whose absence actually blocks the
  answer.
- **1** where two or more questions are stacked, even politely.
- **0** where none is asked and none is owed.

## Rule 9 — the job to be done, not only the product

- **2** where the reply asks what the furniture has to achieve: the work done
  in the space, who uses it, what would make the result right.
- **1** where product configuration stands in for the job — a finish, a width,
  a model number offered as if it were the question.
- **0** where no job is reachable, as on a message that carries no furniture
  need at all.

## Cases already settled

These recur on the frozen sets and have a fixed reading.

| Case | Reading |
|---|---|
| A job application on the sales channel | Rules 5, 8 and 9 cannot be earned unless the reply finds a real furniture path; rule 5 stays 1 either way, because the customer's stated need is a job. |
| A delivery or dispatch notification | No furniture need. Rule 8 is 2 only if the reply asks for the order or shipment number, which is the missing fact. |
| A cold marketing or investment pitch | Declining it and naming our line of business is not a rule 7 restatement. A furniture question offered afterwards can earn rule 5. |
| The customer signs the opening | Rule 3 is 2 for standing down, 1 for asking anyway. |
| "How much" with no item named | Asking which item is what answering requires. Rule 5 is 2 only if the options are space-led. |

## Cases considered on 2026-08-13 and deliberately not adopted

`tj-68au` found two shapes that read as defects and were left at **2**, because
the round before it carried the same two shapes and scored them 2. Charging
them now would have produced a paired delta out of the reader's own drift
rather than out of the build, which is the one thing this document exists to
prevent. They are recorded so a later sitting can adopt them deliberately, and
if it does it must re-read the earlier round to the same standard, since
adopting either costs both rounds equally and moves no delta.

- Answering "Yes" to a demonstrative the channel never carried — "do you have
  this type of chair" — and then listing rows, without saying the type was
  never received.
- Promising "the same item in other colours" for a referent that was never in
  the channel, without asking which item.

## What this convention cannot fix

It bounds how one reader varies between sittings. It says nothing about
whether the reader is right. The one measurement of that is
`tj-4q79-two-readers-20260813`: a paid reader of another vendor sat 2.0 raw
points of 30 away per opening on average, agreeing exactly on rules 1, 2 and 8
and disagreeing on 4, 9 and 5 — the three this convention spends most of its
words on, which is the expected place for it to matter.

The consequence stands whatever this document says: a paired delta smaller
than about 2 raw points per opening is inside reader variance. A round is
defended by named defect shapes and per-rule evidence, never by its total.
