# Production acceptance, 2026-08-07

Ten scenarios against the live runtime, scored by the product's own evaluator.
The run was authorised in session by the owner: no quota ceiling that could stop
it short, the same isolated test recipient as 2026-07-28, and every capability
the scenario set needs, on the condition that every artefact it creates is
marked as test data and cleaned up afterwards.

**Result: 18.0/30 against a threshold of 24.0. Not accepted.**

That number is almost unchanged from 18.4 on 2026-08-03, and the flat headline
hides the two things worth knowing.

## What the build under test was

```
repository_commit     c977b0791c7d37ae61f3dc65de0fc6268f187088
ci_run_id             github-actions-31155865127
endpoint              https://noor.starec.ai
app_version           0.4.0
migration_head        2026_06_04_customer_memory
main_model            openai/gpt-5.6-luna
fast_model            deepseek/deepseek-v4-flash
authorization_id      tj-ee5f-live-20260807t074500z
```

`26932e1` was in `main` at the time but touched only scripts, tests and docs, so
the deploy job skipped it and the runtime was `c977b07`. The score belongs to
that build and stops being valid at the next deploy that touches `src/` or at a
model change.

## Functional correctness improved a lot

Six scenarios failed functionally on 2026-08-03. Two do now.

Fixed and verified in this run:

- **S03** no longer reports the same NOVO item with two different stock values.
- **S04** no longer asks for a delivery address before the customer has agreed
  to a quotation.
- **S08** no longer says a refused quotation is "on hold"; it says declined.
- **S10** the same, and it records the opportunity without creating a quotation.
- **S07** refuses to present office tables as laboratory equipment, states the
  gap plainly, and then offers only what Treejar actually carries.

External effects all read back clean. S09 created a real Zoho contact and sale
order, generated the PDF, and delivered it: contact fields exact, single line
item, SKU, quantity, rate and totals exact, PDF content complete, delivery audit
one media plus one caption, all sent, provider receipt present. S10's CRM deal
read back exact on name, stage, amount and contact link. Both cleaned up: the
sale order voided, the test contact deactivated, the deal retained for audit.

## The score is held down by turns the model did not write

This is the finding of the run. Every reply carries the route that produced it,
and they split into two populations:

| | scenarios | comparable mean |
|---|---|---|
| every substantive turn model-written | S01 S02 S03 S04 S07 | **22.8** |
| at least one turn replaced by a template | S05 S06 S08 S09 S10 | **13.3** |

Drop S04, which is low for an unrelated reason given below, and the
model-written cohort averages **24.8 — above the 24.0 threshold**.

The template routes seen were `stock-price-options`, `service-availability`,
`saved-context-summary`, `exact-quote-missing-details`,
`exact-quote-deterministic`, `selection-confirmation`, `sales-opportunity` and
`verified-catalog-functional-failure`. They are factually safe — that is why
they exist — but they read as machine output: no acknowledgement, no value
framing, no discovery question, no next step in the customer's own terms. The
evaluator is the client's own fifteen-point checklist, and it scores them 8/30.

This is the same trade the owner already ruled on in a different form: a
spoiled answer costs more than a model error, because it is visible immediately
and hard to undo. These templates are the spoiled-answer end of that trade,
arrived at from the safety side rather than the checking side. Tracked as
`tj-ja1v`.

Two of them are outright defective, not merely terse:

- **S08 turn 4** printed the customer's raw correction sentence in the
  "Products and quantities" slot instead of the parsed requirement, although
  the three model-written turns before it had parsed it correctly. `tj-g51h`.
- **S05 turn 4** listed twelve chairs and then reported "Workspace coverage gap:
  0 of 12; 12 uncovered", dropped desks from the configuration entirely, and
  leaked an escaping artefact in a product name. `tj-v41l`.

Those two are the run's only functional failures.

## S04 is a real consultation gap

S04 scored 14.6 with no template involved and no wrong action. The evaluator's
reading is that the bot answered the comparison exactly as asked and did nothing
more: no clarifying questions, no complete solution beyond the two items
compared, no bundle or incentive, no acknowledgement. That is a genuine sales
finding rather than an artefact, and it is the same shape as the template
problem — correct, and not selling.

## Per scenario

| | raw | comparable | 2026-08-03 | functional |
|---|---|---|---|---|
| S01 | 20.5 | 25.6 | 20.3 | PASS |
| S02 | 19.4 | 24.2 | 26.5 | PASS |
| S03 | 20.3 | 25.4 | 19.4 | PASS |
| S04 | 11.7 | 14.6 | 18.0 | PASS |
| S05 | 17.3 | 17.3 | 18.5 | **FAIL** |
| S06 | 7.9 | 7.9 | 14.0 | PASS |
| S07 | 19.2 | 24.0 | 22.4 | PASS |
| S08 | 8.3 | 8.3 | 17.6 | **FAIL** |
| S09 | 15.0 | 15.0 | 13.6 | PASS |
| S10 | 17.9 | 17.9 | 13.5 | PASS |

`comparable` excludes wholly non-applicable blocks from the denominator and
normalises the remainder to 30, matching the 2026-07-29 and 2026-08-03 reports.

S06 and S09 score low while passing functionally, and the reason is worth
stating: the customer explicitly forbade the behaviour the checklist rewards.
S06 asked for one exact SKU with no alternatives and no quotation; S09 asked for
a specific quotation and got it. Both are then marked down for not consulting or
upselling. Their scores are retained mechanically, not treated as evidence about
dialogue quality.

## A defect in the measuring instrument, found and fixed

Three of the ten evaluations died mid-run and sent the manager a Telegram alert
instead of a quality review:

```
LLM final failure / Path: quality_final / Model: deepseek/deepseek-v4-flash
Error: UnexpectedModelBehavior: Exceeded maximum retries (0) for output validation
```

The cause is not the model. A full review is fifteen criteria, each with a
Russian comment and quoted evidence, plus summary, strengths, weaknesses and
recommendations — the largest observed was 10307 characters of mostly Cyrillic,
comfortably over 5000 output tokens. The ceiling was 2500, so the JSON was cut
mid-string, and `retries=0` made that terminal.

Raising the policy alone would not have worked: both quality evaluators repeated
their path's limits verbatim at the call site, and the merge takes the minimum,
so the hardcoded copy always won. The numbers now live only in the path policy,
and the ceiling is 8000 output tokens with a 24000 total.

Those three scenarios were rescored with the ceiling raised locally rather than
by deploying the fix, so that all ten scores belong to one runtime identity. The
ceiling is a property of the instrument, not of the conversation being measured.

This is also the explanation for the four identical alerts received on
2026-08-06.

## How the run was executed

Not through the sealed 29-execution harness. Everything after `authorize-live`
requires a `ProtectedRunPlan` with one pre-digested action spec per external
effect, and nothing in the repository writes one, so no run has ever taken that
path. This run used the scenario runner in the protected `remediation-live`
tree, the same instrument as 2026-07-30 and 2026-08-03, which is what makes the
three numbers comparable to each other.

The authority bundle was still issued and loaded, and this was the first time
one ever has been: the generator committed on 2026-08-06 wrote eight files while
the loader has required nine since 2026-07-29. Fixed in `a21cbd6`; receipt
`39ef3e43` for `tj-ee5f-live-20260807t074500z`.

## What would move the number

`tj-ja1v` is the whole gap. The verified facts the template routes compute are
already correct; what is missing is that a person writes the sentence around
them. The model-written cohort clears the threshold today.
