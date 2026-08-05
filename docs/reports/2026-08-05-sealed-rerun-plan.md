# The sealed re-run, and what it costs

Task: `tj-feet.8`. Prepared 2026-08-05. **Not run.** The provider calls are their
own authority gate and have not been requested.

## What is ready

- Repaired fixtures (`tj-feet.7`): `S01` supplies the capacity it demands an
  explanation of, `S04` supplies the attributes it claims were received, `DK-4`
  is a four-person desk everywhere and `AX-E1` is AED 800 everywhere.
- The claim rubric (`tj-feet.4`): four claim types, three separately reported
  graders, pinned as `noor-claim-rubric/v1`.
- The scoring path detects a claim-rubric scores file and reveals it into three
  axes per model beside the selection score. A superseded round still loads
  through the old path.
- The claim gate moves `hard_gate_passed` only, so the deterministic objective
  score is untouched and a fabricating model cannot be selected on style.

## What the run costs

The estimate in the specification — *roughly one dollar per round* — is wrong by
two orders of magnitude for candidate spend. The actual figures from the
superseded round, summed from `accounting.cost_usd` in its own evidence:

| round | responses | actual candidate spend |
|---|---|---|
| `20260805/core-r4` | 60 | **$0.0274** |
| `20260805/bg-r4` | 54 | **$0.0062** |
| both | 114 | **$0.0336** |

Per model in the core round: `z-ai/glm-5.2` $0.0206, `xiaomi/mimo-v2.5-pro`
$0.0029, `openai/gpt-5.6-luna` $0.0020, `deepseek/deepseek-v4-flash-0731`
$0.0019. The reservation was $4.00, four models at a $1.00 flat cap, and none
came close to it.

The dollar-scale figure in the specification almost certainly included the paid
judge. Owner decision of 2026-08-05 removed that: the judge is the orchestrator
session and costs no provider spend.

**Estimate for the re-run: $0.04, with the same $4.00 reservation retained as
the cap.** The repaired fixtures add roughly sixty tokens to `S04` and one
catalog row to `S01`, so the change against the superseded round is immaterial
at this scale.

The same arithmetic applies to the `tj-feet.5` counter-set, which was estimated
at about two dollars when that question was put to the owner. At the measured
rate of about $0.0011 per response for the production main model, fourteen cases
over three repetitions is about **$0.05**, not $2. The owner's decision to run
it only after the model is chosen was made on ordering, not cost, and stands;
the number is corrected here so it is not carried forward wrong.

## The procedure

1. **Preflight, no model calls.**
   ```sh
   uv run python -m scripts.model_battle --profile core-hard-2026-08-03 \
     --suite sales --preflight-only --output-dir <round-dir>
   ```
2. **Generation.** The paid step. Complete unique model/case/repetition matrix,
   blind labels, reveal key written to the private plaintext directory.
3. **Judging.** The orchestrator reads `sales_blind_review.json` only. The reveal
   key is not opened, so blindness is mechanical. Each response is scored under
   `noor-claim-rubric/v1`: one claim object per asserted attribute, tool
   obedience, conversational quality.
4. **Seal, then reveal.**
   ```sh
   uv run python -m scripts.model_battle --score-only \
     --blind-scores <scores.json> --seal-blind-scores --output-dir <round-dir>
   ```
5. **Manual re-check.** Every critical failure is read by hand against the actual
   model context before acceptance, as the previous round did. That re-check is
   what found the two judge errors and the three fixture defects.
6. **Reconcile** actual spend against the $4.00 reservation.

## What the run must report

Three axes per model with their denominators, the four claim types, and the
selection score. Not one quality figure.

The result is **not comparable** with the superseded rounds and must never be
shown beside them without that statement: different fixtures, different rubric,
three axes where there was one blended number.

## Authority

Not granted. The paid provider calls of step 2 need current explicit
authorization naming that action. Nothing else in this stage requires it, and no
runtime model configuration is changed by this task — the model decision after
the winner is named is the owner's, through `tj-ee5f.15`.
