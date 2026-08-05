# Teaching the marked assumption: the paired counter-set result

Task: `tj-feet.6`. Measured 2026-08-05 on `openai/gpt-5.6-luna`, the model now
serving the main slot. Round `20260805/counterset-r2`, protected evidence
outside Git. Cost **$0.0052** for 42 responses.

## What changed

Nothing in any factual guard, and nothing in the product system prompt, which
the stage contract freezes. Three code changes, all per-turn:

1. `requests_sizing_judgement()` in `src/dialogue/claim_contract.py` reads the
   **customer request** — never the reply — for a stated headcount plus a
   suitability question, in English and Arabic.
2. `sizing_assumption_directive()` is added to that turn's runtime directives.
   It tells the assistant to answer, to do the arithmetic in the open, to mark
   the sizing as an assumption carrying one confirming question, to give the
   confirmed details alongside, and to close with a concrete next step. It also
   repeats that capacity is not a catalog fact.
3. The repair pass no longer pushes the refusal it exists to prevent. Its
   withheld branch used to say only *the catalog does not state them* for every
   path. Capacity paths are now split out and re-offered as a marked assumption;
   every other path keeps the old partial-answer wording.

The trigger deliberately catches the `K02` control as well as the `C04` target.
Narrowing it to miss the control would have been tuning the instrument to the
test. Whether the directive holds the line there is reported below as a measured
result, not assumed as a design property.

## A calibration finding that comes first

The published `tj-feet.5` baseline scored persuasion at 3.262 and next step at
3.833. Re-scoring the **same stored baseline responses** in this pass gives
2.548 and 3.429.

The responses did not change; the judge's calibration did, across two sessions.
That makes the published figures unusable as a before-number for this comparison,
and it is a property of any single-judge instrument, this one included.

So both rounds were re-scored together in one sitting under one rubric, and it
is that paired re-score which is reported here. The published baseline stays
where it is, superseded rather than rewritten, and must not be shown beside these
numbers.

## The seven metrics, paired

Same 14 cases, same model, three repetitions, 42 responses per round.

| | metric | baseline | with the directive |
|---|---|---|---|
| 1 | unsupported-fact rate | 0.000 (0/42) | **0.000** (0/42) |
| 2 | false-refusal rate | 0.200 (6/30) | **0.000** (0/30) |
| 3 | unnecessary-hedge rate | 0.000 (0/42) | 0.000 (0/42) |
| 4 | task completion | 0.767 (23/30) | **1.000** (30/30) |
| 5 | guard deleted a correct claim | n/a, denominator 0 | n/a, denominator 0 |
| 6 | persuasion | 2.548 (n=42) | **3.071** (n=42) |
| 7 | next_step | 3.429 (n=42) | **3.667** (n=42) |
| | control compliance | 1.000 (12/12) | 1.000 (12/12) |

By language, on the two axes that moved:

| | baseline EN | round 2 EN | baseline AR | round 2 AR |
|---|---|---|---|---|
| persuasion | 2.476 | 3.190 | 2.619 | 2.952 |
| next_step | 3.238 | 3.810 | 3.619 | 3.524 |

## The decomposition that makes the result readable

Only two of the seven case families had their prompt changed at all: `C04` and
`K02`, the ones whose request earns the directive. The other five went to the
provider with a byte-identical prompt, so their movement is generation noise and
gives the comparison its own error band.

| | changed prompt (12 responses) | identical prompt (30 responses) |
|---|---|---|
| persuasion | 2.000 → 4.000, **+2.000** | 2.767 → 2.700, −0.067 |
| next_step | 3.083 → 4.333, **+1.250** | 3.567 → 3.400, −0.167 |

The effect on the cases the change touches is an order of magnitude larger than
the drift on the cases it does not. The identical-prompt band moved slightly
*down*, which is worth stating plainly: at temperature 0 a provider still is not
deterministic, and most of that band is two one-line Arabic `K01` answers that
came back terser than last time.

## What the answers look like now

All six `C04` responses open with a marked assumption, do the division in the
open, give price, total and recorded stock, and end with a question that confirms
the assumption. All six previously declined. Failure class (c) in miniature: the
labelled assumption that used to be refused now ships, and the bare capacity
assertion still cannot.

Two honest caveats.

**The assumption is reverse-engineered from the customer's number.** Asked
whether two desks suit twenty people, the model assumes ten people per desk —
which is exactly the figure that makes the answer *yes*. It is marked, it is
confirmable, and the confirming question carries the real content, so it is not a
fabrication. But it is agreeable by construction, and a customer who does not
read the marker gets a yes. The directive does not, and cannot, force the
assumption to come from anything about the desk, because nothing about the desk
is in the catalog.

**The control got softer, without failing.** `K02` demands a written
confirmation of a seat count. All twelve control responses still refused to
supply it, in both rounds. But the shape changed: baseline `K02` was a flat
decline, and now it is a decline followed by the assumption arithmetic. One of
the six, `K02-en` repetition 3, opens *I can confirm this in writing as an
assumption, not a catalog-confirmed seating capacity* — the sentence completes
correctly and the reply then assumes two people per desk rather than ten, so it
never asserts what was demanded. It is scored compliant. It is also the closest
this set has come to a regression, and it is the thing to watch if the directive
is widened.

## What was not touched

No factual guard was loosened. The claim contract, the quotation-consent
withdrawal of `tj-feet.2` and the row verification of `tj-feet.3` are unchanged;
this task only stopped the runtime from asking for a refusal the contract had
already approved an answer for. Metric 1 stayed at zero and control compliance
stayed at 1.000 while metrics 2, 4, 6 and 7 all improved, which is the outcome
the acceptance criterion asks for and not a trade against it.

The product system prompt did not grow. The directive is 566 characters on the
turns that earn it and absent on every other turn, and a test pins that bound.

## Gates

Run on the combined tree after the change:

- `uv run ruff check src/ tests/` — passed
- `uv run ruff format --check src/ tests/` — 333 files already formatted
- `uv run mypy src/` — no issues in 166 source files
- `uv run pytest tests/ -q` — **2959 passed, 19 skipped**

That run also repaired a regression this stage had introduced and not noticed:
`.codex/stages/tj-ee5f/traceability-manifest.json` pins whole-file digests of
`.codex/orchestrator.toml` and `.codex/handoff.md`, both of which the repository
contract declares to be current state. Pointing `current_stage_id` at `tj-feet`
was enough to break three of that stage's manifest tests. The two digests were
re-pinned; no criterion, locator or frozen Beads record changed. The underlying
defect is that a frozen manifest pinned two deliberately mutable files, and it
belongs to the `tj-ee5f` stream to decide on — recorded as `tj-feet.11`.

## Not claimed

One model, 14 cases, three repetitions, one judge, one day. The judge is the
orchestrator session, which is why the calibration drift above is reported rather
than hidden: a single judge scoring two rounds in separate sittings does not
produce comparable numbers, and only the paired re-score here does. The
improvement is measured on requests answerable without a missing field, not on
customer traffic. The guards' cost in deleted correct claims remains unobserved,
not proven absent.
