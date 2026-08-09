# Spec: the templates are the gap, and the number is now two numbers

Written 2026-08-09 to hand the work on. Everything below is measured unless it
says otherwise, and where it is a hypothesis it says so.

## Where things stand

Production runs `af4db16`. Gates green: ruff, ruff format, mypy over 167
sources, pytest `3359 passed, 19 skipped`, `run_process_verification.sh` OK.

**The acceptance figure is two figures now, and neither is the old one.**
Measured at `ac36265`, two independent reads per packet across six readers,
41 packets from 13 scenarios × 3 runs plus S09/S10 once:

| shape | mean /30 | applicable rules | scenarios |
|---|---|---|---|
| project | **19.95 ± 0.93** | 11.0 | 4 |
| transactional | **20.77 ± 4.41** | 7.6 | 11 |

Reader disagreement is **1.96** mean |A−B|, down from 2.86 when two readers
carried 26 packets each. The load hypothesis held.

**24.0 is retired as a single threshold** and `scripts/e2e_acceptance/score_by_shape.py`
refuses to print one number. The reason is arithmetic: the fork made rules 6, 10
and 13 correctly inapplicable to an ordinary order, `calculate_weighted_score`
normalises what remains back up to /30, and two conversations scored a perfect
30 over the eight easy rules alone. A score over eight rules and a score over
fifteen are not the same measurement.

**The rubric is frozen** (`tj-07bs`). Five changes in one week, every one of
which raised the number, the last from 16.5 to 21.4 with no build change at all.
No figure before 2026-08-09 compares with any figure after it.

## The organising insight, found twice independently

`tj-ja1v`, filed 2026-08-07, separated the acceptance results on one variable:
who wrote the turn. Scenarios where every substantive turn was model-written
averaged 24.8; scenarios where a deterministic route replaced at least one turn
averaged 13.3.

This week rediscovered the same thing from the customer's side, three times,
without looking at that issue:

- **The name gate.** A deterministic first turn asking only for a name. Both
  research reports named it the worst opening available on this channel, one
  giving it verbatim as its example of what not to do. 34% of real customers
  open with a bare greeting and 36% never send a second message, so a third of
  conversations spent their only reply on it. Partly fixed: the reply now
  carries what Treejar can do and an anchor price from the catalog before it
  asks. Price now appears on turn 1 in 5 of 5 realistic scenarios, against 0 of
  5 before, and rule 7 went from 0.08 to 1.66 after two days of prompt work had
  moved it not at all. **A guarantee beat a directive.**
- **`detail-capture`.** Fired on the turn completing the name gate and returned
  "Thanks, I've noted name: Omar." while the customer's opening question sat
  stored and unanswered. Fixed at `af4db16`.
- **`showroom-location`.** Matched the bare word "office" and answered "for a
  small office, 4 people" with a Google Maps link. Fixed at `351c0e9`.

**Treat `tj-ja1v` as the spine of the remaining work.** It is P0, it is two days
older than everything here, and every finding since has been an instance of it.

## What to do, in order

### 1. `tj-jxv7` — the resumed question gets a question back (P1, start here)

The empty acknowledgement is gone; the answer still is not. "hi do u have ch616
in black" → name gate → "Omar" now reaches the model, which replies "Hi Omar!
Could you confirm the quantity you need?" instead of saying whether the SKU
exists, at what price, with how much stock. All three are one tool call away.

**Concrete hypothesis to test first, cheap and checkable:** `combined_text` is
rewritten to the stored question *after* `_turn_runtime_directives` has already
selected directives, so the resumed turn may carry none. Same shape as the
`tj-2m5m.8` finding. Check the directive list on that path before writing
anything.

**Done when:** the resumed turn answers availability and price for a SKU the
catalog holds, verified in a live conversation, not only in a unit test.

### 2. `tj-ja1v` — the templates (P0, the largest remaining gap)

Do not delete the routes; they exist because the model was unreliable on facts.
The pattern that worked on the name gate is the pattern to repeat: **keep the
deterministic guarantee, and let it carry what a salesperson would carry.** The
opening guard now states the value proposition deterministically, which is why
rule 7 moved when two days of directives could not.

Routes observed scoring badly: `stock-price-options`, `service-availability`,
`saved-context-summary`, `exact-quote-missing-details`, `exact-quote-deterministic`,
`selection-confirmation`, `sales-opportunity`, `verified-catalog-functional-failure`.

**Done when:** each route either carries an acknowledgement, a verified fact and
a next step, or stands down to the model when it has nothing to add. Measured on
the transactional baseline of 20.77, not on a new rubric.

### 3. `tj-2m5m.10` — grow the realistic set (P1)

Five scenarios exist (`R01`–`R05`) and they found two defects on their first
run that the frozen ten could not see. Their shape came from 74 real openings:
34% bare greeting, median 53 characters, median two customer turns.

Worth adding, still absent: a customer who sends two messages and vanishes, a
voice-note transcript with no punctuation and a wrong SKU, an Arabic customer
who switches to English mid-thread, and a customer who asks only about delivery.

**Constraint:** `S01`–`S10` stay frozen as the regression set with their own
number and no threshold. The realistic set is where a target eventually gets
set, per the owner's decision of 2026-08-09.

### 4. `tj-2m5m.4` — the widening, now that it is forked (P0 but blocked in practice)

Rule 10 is 0.88 and applies only on the project fork. Re-measure before touching
it: the fork changed both what it means and how often it is charged.

### 5. `tj-swgu.11` and `tj-swgu.12`

`.11` is largely delivered by the applicability corrections — a criterion the
customer ruled out is now not applicable. Verify and close rather than rebuild.
`.12` wants a baseline re-established from stored transcripts; the two baselines
above supersede it, so close it against them.

## Rules of engagement, learned the hard way this week

1. **Rubric changes and build changes never ship in the same measured round.**
   This is the one that cost the most: five rubric changes made the number move
   without the bot moving, and nothing before 2026-08-09 is comparable now.
2. **Compare a shape with itself.** Never one shape with another, never either
   with a pre-fork figure. `score_by_shape.py` enforces this by refusing to
   print a single number.
3. **A condition on the world is a guard; a condition on what Noor thinks she
   already did is a leak.** Four rules died on their own escape clauses. Five
   tests hold those clauses out; do not reintroduce the pattern.
4. **Generation is stochastic by owner decision.** Compare k runs per scenario
   per side, never one. Measured within-scenario sd is about 1.7.
5. **Read two transcripts by eye every round.** Every finding that mattered this
   week — the S08 echo, the "office" routing, the empty acknowledgement — came
   from reading, not from a number.
6. **The model reads the customer; code owns the catalog.** Numbers the customer
   gives are extracted by the model through `record_customer_requirements` and
   validated by code. Numbers the customer receives come from a catalog row and
   the model never authors them.
7. **A deterministic guarantee beats a directive** where the behaviour is
   unconditional. Rule 7 proved it.

## Authority

None is currently granted. Push, deploy, live acceptance runs, paid OpenRouter
calls, model-config changes and production mutation each need a fresh, explicit
grant from the owner, and each was granted and spent separately during
2026-08-08 and 2026-08-09.
