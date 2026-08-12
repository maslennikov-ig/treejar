# Stage tj-0h5d-deepseek-repair-judge

Status: accepted; `tj-0h5d` closed
Base: `main` at `7b2b659`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — both vendors were measured
against the live endpoint on the repository's own stored requests.

docs-reviewed: updated - the round report and the handoff record the model, the
prompt change and what the judge adds beyond the free repair. `AGENTS.md` and
`README.md` describe none of it.

project-index: reviewed-no-change — no new tracked file outside the stage
directory and no contract key moved.

## Scope

The owner asked to move the repair path to DeepSeek Flash with the prompt fixes
that came out of `tj-lj09`. Both were measured before shipping, and one of the
two turned out to carry almost all of the effect.

## What was wrong, and it was ours

`review_flagged_reply` re-renders every correction and discards it whole if a
flag survives. The prompt asked the judge to "resolve every flag" and never
said what that check was. GLM reworded the flagged promise instead of removing
it and had its answer thrown away twice in four; DeepSeek took the
`cannot_fix` exit two times in three, quoting our own line back — "the
deterministic candidate is not evidence". **One reply in four reached the
customer, on either vendor.** We had been reading that as a model problem.

## What changed

- `REPAIR_JUDGE_MODEL` is `deepseek/deepseek-v4-flash`. Chosen by replay: under
  the same prompt it delivers as often as GLM 5.2 did, for about a fortieth of
  the price and no more waiting.
- The prompt gains two paragraphs: what a resolved flag is, and what
  `cannot_fix` costs the customer. A third tells the judge the deterministic
  candidate is already free of the flagged content and may be followed.
- Two tests pin the prompt sentences and the second-vendor rule.

## What it buys, stated plainly

The shipped configuration was replayed on both flagged replies we hold:
**7 of 8 delivered**, $0.000596 for eight calls, 5.6–10.2s. The one loss was a
20s timeout, which the existing retry covers.

In all seven deliveries the judge returned **the free deterministic repair
verbatim**. So on the two cases we can test, the paid call adds nothing beyond
what the guard already produces — it has simply stopped destroying it. That is
the honest account of the value: the fix is worth 3x the delivery rate and 40x
the price, and the judge's own contribution here is zero.

## The cost of the fix, which is real

Telling the judge it may follow the candidate is what produces the delivery
rate. A version without that sentence was measured at 2 of 4. It is also what
turns the judge into a copier: under the old prompt GLM independently noticed
the reply had invented a delivery city the customer never named, and that catch
is gone. We bought delivery with independence, knowingly.

The remaining case for keeping a paid judge at all is the four grounding
violations that have never fired in 120 stored replies — price, stock
confirmation, service scope, showroom trial — where a wrongly approved reply
costs money rather than a follow-up.

## Verification

- Shipped config, live: dialog 819 3/4, dialog 789 4/4, one 20s timeout.
- Prompt without the candidate paragraph: 2/4 on 819. Prompt as shipped, on
  GLM: 4/4. The paragraph, not the vendor, carries the effect.
- `uv run ruff check src/ tests/ scripts/`, `ruff format --check`, `mypy src/`:
  passed.
- `uv run pytest tests/ -v --tb=short`: 3621 passed, 19 skipped.
- Protected 60-output replay: aggregate `1fc87c04…`, unchanged.
- `scripts/orchestration/run_process_verification.sh`: passed.

## Risks / Follow-ups / Explicit defers

No defer. Two limits: the whole comparison rests on two flagged replies of one
violation class each, and the judge is now demonstrably a copier on both. If
the four unseen violation classes ever fire, that is the first evidence about
whether this judge is worth its call at all.

Paid calls in this stage: 16, $0.001960, under owner authority given in session.
