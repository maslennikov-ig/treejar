# Production acceptance after `tj-swgu`, 2026-08-07

The second run of the day, on the build that carries the whole
"let the model write the sentence" epic. Same ten scenarios, same instrument,
same isolated test recipient, scored by the product's own evaluator.

**Result: 18.5/30 comparable against a threshold of 24.0. Not accepted.**

The morning run on `c977b07` was 18.0. So the headline moved by half a point,
and that number hides both a real improvement and a real regression.

## What the build under test was

```
repository_commit     6a14f2fdd307e2d5f43397027c6f6e43e2252210
ci_run_id             github-actions-31182783949
endpoint              https://noor.starec.ai
app_version           0.4.0
migration_head        2026_06_04_customer_memory
main_model            openai/gpt-5.6-luna
fast_model            deepseek/deepseek-v4-flash
authorization_id      tj-ee5f-live-20260807t133345z
authority_receipt     255d6412
```

All ten scenarios ran on this one release. Three later commits fix defects this
run exposed and are not in it; they are named below.

## The one unambiguous win: functional correctness

**Two functional failures became zero.**

- **S08** carried the customer's raw correction sentence into the "Products and
  quantities" slot of a template. That template is gone, the turn is
  model-written, and it now reads "3 × LUMA 9719-4 workstations" — the parsed
  requirement. The scenario is fully model-written for the first time and its
  score went 8.3 → 14.6. `tj-g51h` closed.
- **S05** printed a coverage line contradicting the line above it, dropped a
  whole product family, and leaked a doubled backslash from a supplier
  packaging note. All three are fixed and visible in this run's output: the
  workspace family now says "no verified option within budget yet" before its
  gap line, and the name renders with one backslash. `tj-v41l` closed.
- **S08 turn 2** answers "do you provide delivery and assembly in Dubai?"
  directly instead of escalating to a manager. That was `tj-rily`.

External effects read back clean. S09 created contact, sale order Fr3711 with
one line of 4 × CH 616 NEW black at AED 295.00, and delivered the PDF. S10 wrote
the CRM deal and created no quotation, which is what that scenario requires.
Cleanup: four draft sale orders from the day's runs voided with readback, the
test contact deactivated, the deal retained for audit.

## Per scenario

| | raw | comparable | morning | delta |
|---|---|---|---|---|
| S01 | 19.4 | 24.2 | 25.6 | −1.4 |
| S02 | 19.4 | 24.2 | 24.2 | 0.0 |
| S03 | 23.1 | 28.9 | 25.4 | **+3.5** |
| S04 | 18.2 | 22.8 | 14.6 | **+8.2** |
| S05 | 17.3 | 17.3 | 17.3 | 0.0 |
| S06 | 7.9 | 7.9 | 7.9 | 0.0 |
| S07 | 18.8 | 23.5 | 24.0 | −0.5 |
| S08 | 14.6 | 14.6 | 8.3 | **+6.3** |
| S09 | 12.6 | 12.6 | 15.0 | −2.4 |
| S10 | 9.3 | 9.3 | 17.9 | **−8.6** |

Mean comparable **18.5**, mean raw 16.1. Five scenarios below 20.

`comparable` excludes wholly non-applicable blocks and normalises the remainder
to 30, matching every previous report.

## The consultative directive worked

S04 is the clearest result in the run: **14.6 → 22.8** with no template
involved either time. The evaluator's complaint in the morning was that the bot
compared exactly the two items asked about, recommended one, and stopped. A
per-turn directive on comparison turns — acknowledge the team, name what the
workspace still needs, ask one question — moved it 8.2 points without touching
the frozen product prompt and without a single new unsupported fact.

That is the epic's thesis holding where it was tested directly.

## Where it did not hold, and why

**S10 lost 8.6 points and it is not a defect.** The evaluator marked down five
discovery and consultation criteria that had scored 1 in the morning and score 0
now: interest in the customer's needs, Treejar's value, clarifying questions,
the "drill and hole" principle, complete solution. Nothing about those turns got
worse; the judge read a short transactional thread more harshly the second time.
S01 moved −1.4 and S07 −0.5 on unchanged behaviour for the same reason. The
judge is `deepseek-v4-flash` and its run-to-run spread on this set is worth
about a point either way per scenario — which is most of the headline
difference between 18.0 and 18.5.

**The action-route rewrite fires, and is then usually refused.** This is the
substantive finding. The wrap works exactly as designed — the write happens
first, the model writes the sentence, and the sentence is discarded unless every
verified number survives it. In this run the model dropped facts almost every
time:

```
selection-confirmation   dropped numbers ['295.00', '36', '5900.00']   x2
selection-confirmation   dropped numbers ['295.00', '3540.00', '36']
selection-confirmation   dropped numbers ['295.00']
exact-quote-deterministic  dropped numbers ['3708' .. '3711']          x4
sales-opportunity        invented numbers ['1100']
```

`exact-quote-deterministic` dropped the quotation number itself — a reply that
says the quotation is ready without saying which one. `selection-confirmation`
consistently drops the unit price and the live stock figure. Both refusals are
the guard doing its job; both mean the customer got the template.

S06 and S10, the two scenarios that did not move at all, are exactly the two
whose remaining template is `selection-confirmation`.

It is not hopeless: an intermediate probe on the same code produced a
model-written `sales-opportunity` turn naming the company, product, value,
budget and decision timeline, and it passed the guard. The rewrite succeeds
sometimes and fails more often than it succeeds.

## Turn provenance, now a number rather than a reading

```
10 scenarios, 3 model-written throughout; 13 of 29 turns from a deterministic route
```

Morning: 2 of 10 and 15 of 29. The tool that prints this is new
(`scripts/e2e_acceptance/route_provenance.py`); the data was in every capture
all along.

## Three defects this run found in the new code

Each was found by the logging added for exactly this purpose, and each is fixed
and pushed but **not in the build measured above**:

- The rewrite guard treated a number said earlier in the conversation as an
  invention. It rejected every `sales-opportunity` rewrite for "inventing" the
  quantity, total and SKU the customer had chosen two turns earlier.
- The pre-policy phase had no model runner, so one of the two paths into
  `selection-confirmation` silently returned template text and logged nothing.
- The guard required every uppercase run to survive, so a reply saying
  "recorded in Zoho" instead of "recorded in the CRM" was refused. And the
  "00" in "295.00" counted as an identifier a reply had to reproduce.

## A defect in the harness, not the product

S09 and S10 deliberately use the bare test recipient, so they share one
conversation. Nothing resets it between rounds, and six diagnostic probes ran
through it during the day: by the time it was scored it held 67 messages. Both
scenarios were re-run on freshly reset conversations before the numbers above
were taken. Any future round has to reset between S09 and S10 and after any
probe, or those two scores are meaningless.

## What would move the number now

Not more routes, and not the judge. The gap is concentrated:

1. `selection-confirmation` and `exact-quote-deterministic` refuse their own
   rewrites because the model will not carry every figure. The directive now
   lists the figures explicitly, which halved the misses but did not close them.
   Either the model needs the itemised block handed to it as a block to keep, or
   the guard needs to accept a rewrite that keeps the total and the quantity
   while dropping a derivable unit price. That is a product decision about what
   the customer must be told, not a technical one.
2. S06 and S09 are scored down for not consulting on turns where the customer
   explicitly forbade it. Their scores are mechanical, not evidence about
   dialogue quality, and they cost the mean about two points between them.

The epic's own acceptance is not met and the morning's 18.0 is superseded by
this 18.5 as the standing evidence.
