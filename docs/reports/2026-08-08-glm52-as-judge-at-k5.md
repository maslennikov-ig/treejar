# glm-5.2 as the quality judge: what its repeats say

Task: `tj-4e5j.7`. Measured 2026-08-08 against the ten stored `5656c82`
transcripts, scored five times each on the English rubric at temperature 0.
Fifty scorings, no live traffic, no production mutation. Run preserved at
`.git/codex-orchestration/noor-e2e-acceptance/remediation-live/tj-4e5j7-glm52-judge-5656c82-20260808`.

## The number

| judge | k | pooled sd | mean /30 | 95% interval |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash` (deployed) | 1 here, 5 earlier | **3.8** | 16.1 | none from this run |
| **`z-ai/glm-5.2`** | 5 | **1.3** | **11.2** | **± 0.4** (df 40) |
| five blind Claude readers (reference) | 5 | **0.9** | 12.3 | ± 0.3 (df 40) |

The instrument is `scripts/e2e_acceptance/score_uncertainty.py`.

## Decision: adopt, on the sd

The incumbent judge carried **± 3.3 on the mean at one pass**. Against a
threshold gap of that era, three materially different builds came out as one
number, and an unchanged S03 scored 15.2, 16.2, 21.5, 21.6, 23.9. That is what
made per-scenario deltas unreadable.

glm-5.2 reads the same transcripts at **sd 1.3**, roughly three times quieter,
and close to what five independent readers achieve at 0.9. At k=5 its mean
carries ± 0.4. A one-point movement in the acceptance mean is now a finding;
under the old judge nothing below about seven points was.

This is not a cost decision, and cost would argue the other way: per evaluation
at the `PATH_QUALITY_FINAL` ceiling, glm-5.2 is $0.0114 against
deepseek-v4-flash's $0.0045 and Luna's $0.0064. The run cost about $0.57.

## Where it sits against the reference panel

Compared run-to-run, both with their own repeats, so the comparison is legitimate:

    mean 12.3 -> 11.2, delta -1.1 +/- 0.5 (95%)

Larger than the noise, so real — and it is a difference between *judges*, not
between builds; the transcripts are identical. Seven of ten scenarios sit inside
the noise. Three move: S04 −2.1, S07 −2.9, and **S05 −4.8**.

So glm-5.2 is slightly stricter than the panel overall, and materially stricter
on S05. That is the thing to look at before trusting a per-scenario reading on
those three. The incumbent sat **+3.8 above** the panel; glm-5.2 sits 1.1 below
it. Agreeing with the reference reading is not proof of correctness — a judge
can be repeatable and wrong, and sd cannot see that — but two instruments built
differently landing within about a point of each other is worth more than one
instrument landing anywhere.

## Re-baseline

**The acceptance mean is 11.2 /30 ± 0.4** under glm-5.2 on the English rubric at
temperature 0.

Against the 24.0 threshold that is a gap of **12.8 points**, not the 7.9 the
corrected deepseek figure implied and not the 5.8 the double-normalised reports
claimed before that. The instrument got quieter and the picture got worse; those
are separate facts, and the second one was always true.

## One defect found in the process

glm-5.2 returns `diagnostics` as a JSON **string** rather than an object.
`judge_agent` runs with `retries=0`, so the first call died on output validation
and the model presented as unusable. Both `diagnostics` and `block_scores` are
recomputed by `finalize_evaluation_result` from the criteria, so the judge's
values are discarded either way; `EvaluationResult` now accepts a stringified
nested object for both. Covered by two tests in `tests/test_quality_evaluator.py`.

Worth noting for any future judge swap: a model that is otherwise fine can be
rejected by a schema detail in a field nobody reads.
