# The escape-clause audit, and what our test is not measuring

Two questions from the owner on 2026-08-08: are we boxing the model in, and is
the mistake in the tests rather than the bot? Both were answered with
measurement. The short answers: **no, the model is not boxed in** — and **yes,
the tests are partly wrong**, in a way worth fixing before the next round.

## Are we over-constraining the model? No, and here is the measurement

Directives are **2 353 characters against a 6 929-character base prompt** — a
quarter of the instruction on an opening turn, one directive of 828 characters
on an ordinary one.

More to the point, the model still writes freshly. Comparing the same scenario
across the three repeats of the `a830001` run, character-level similarity is
**0.34**, where 1.00 is word for word. Wording, structure and argument order all
change every time.

And the correlation runs the encouraging way. **S07** is the least repetitive
(0.12 similarity between runs) and the highest scoring at 22.65. **S08** is the
most repetitive (0.63) and among the worst at 11.45. Freedom is not the risk
here.

## The real risk is a different one: rules that die quietly

The failure mode we have now hit four times is not rigidity. It is a
conditional clause the model can satisfy by its own judgement, which turns an
instruction into a dead letter that nobody can see from the outside.

Audited every directive in the runtime — five in `claim_contract.py`, eight in
`engine.py` — and sorted every conditional sentence into two kinds:

**Safe: conditions on the world.** "If a detail is unconfirmed, say so." "Do not
claim anything has been scheduled unless a tool call did it." "If Zoho cannot
confirm the item, escalate." These are checkable outside the model's own head,
and none of them has misfired.

**Dangerous: conditions on the assistant's own past behaviour or judgement.** The
model is both the actor and the judge of whether it already acted, so the
condition is always satisfiable. Four found, all now removed:

| clause | rule it killed | now |
|---|---|---|
| "if you have not already said it in this conversation" | 7 — value proposition | "in this reply", greeting explicitly does not discharge it |
| "at most one question ... or leave it for the next turn" | 13 — company | folded into the same sentence, counted as one |
| "and you do not know what their company does" | 13, the other half | knowing the name is not knowing the line of work |
| "whose **whole content** is a restatement" | S08's echo | what the reply *adds*, and padding an echo with a promise is still an echo |

The third and fourth are new here. The fourth is the one that matters: S08
survived a directive written against it because its turns are a restatement
*plus* "I'll keep these details in mind" — so the restatement was never the
*whole* content and the prohibition never bound. That was the defect left
unexplained by the previous report.

Two more hedges went with them: "once per conversation" and "if the setup is
**plainly** missing a piece" — same family, softer, and rules 6 and 10 are the
two that remain weak. Five tests now hold the escape clauses out.

**The rule to work by:** a condition on the world is a guard; a condition on
what Noor thinks she already did is a leak.

## Is the mistake in the tests? Partly yes

Measured our ten scenarios against how customers actually write to this number
in production. 74 real openings, test traffic excluded.

| | real customers | our scenarios |
|---|---|---|
| opening over 100 characters | 9 of 74 (12%) | 8 of 10 (80%) |
| opening over 150 characters | 5 of 74 (7%) | 2 of 10 |
| median opening length | 53 chars | 126 chars |
| bare greeting or emoji, nothing else | **25 of 74 (34%)** | **0 of 10** |
| no product word at all in the opening | 20 of 74 (27%) | 0 of 10 |
| median customer turns per conversation | 2 | 3 |

**Conversation length is fine.** The scenarios are 2–4 customer turns and the
real median is 2, so the probes are not unrealistically short — which also means
they are not unrealistically long, and the checklist's late blocks genuinely
cannot be reached in a typical conversation.

**Content is not fine.** A third of real customers open with "Hi" and nothing
else. Another quarter write something short with no product in it. We test
neither. Every one of our ten scenarios opens with a fluent, specific,
well-punctuated brief that names products and usually a budget and a headcount.
We have been tuning a bot for a customer who does not exist.

## And the rubric is being used for something it was not written for

`docs/06-dialogue-evaluation-checklist.md` is a **manager's scorecard for a
complete sales conversation**: fifteen rules running from the greeting through
collecting contact details to confirming the order and agreeing the next
contact. Its own interpretation table calls 20–25 "good, minor gaps, structure
preserved".

We apply it to two-to-four-turn WhatsApp exchanges, most of which end before a
sale is anywhere in view. The applicability map absorbs some of that, and two
corrections on 2026-08-08 absorbed more, but a structural mismatch remains.

**S06 is the clean demonstration.** The customer asks for the exact live price
and stock of one SKU, twelve units, and explicitly rules out a quotation and
alternatives. Noor gives exactly that, in three lines, correctly. It scores
**7.35 of 30** — the lowest of the ten — because the customer forbade nearly
everything the checklist rewards. That is not a bad reply. It is a good reply
being marked against a rubric for a different conversation.

## The plan

**Done already** (directive audit fixes, tested, not yet measured):
the four escape clauses above, plus the two hedges.

**Needs an owner decision before the next run** — three of them, in the section
below.

**Then, in order:**
1. Split the reader load, four readers at 13 packets each rather than two at 26.
   The panel measured 2.86 mean disagreement last round against 0.9 before, and
   a two-point improvement is invisible to an instrument that noisy.
2. Re-run at k=3 on S01–S08 and once on S09/S10, same as before, so the
   comparison stays paired against 13.4.
3. Read two transcripts by eye each round. Both findings that mattered this
   week — the S08 echo and the S06 mismatch — came from reading, not from the
   number.
