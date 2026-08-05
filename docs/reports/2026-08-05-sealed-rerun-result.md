# The sealed re-run on repaired fixtures

Task: `tj-feet.8`. Executed 2026-08-05 under owner authorization. Round
`20260805/core-r5` and `20260805/bg-r5`. Protected evidence stays outside Git.

Scored under `noor-claim-rubric/v1`. **Not comparable** with the superseded
rounds of 2026-08-04 and 2026-08-05: different fixtures, different rubric, three
axes where there was one blended number.

## The result

Core slot, 60 scored responses, complete unique model/case/repetition matrix:

| model | responses | groundedness | tool obedience | conversational quality | critical failures | gate |
|---|---|---|---|---|---|---|
| `openai/gpt-5.6-luna` | 18 | **1.00** (24/24) | 1.00 | 0.867 | **0** | **pass** |
| `deepseek/deepseek-v4-flash-0731` | 18 | 0.96 (24/25) | 1.00 | 0.864 | 1 | fail |
| `z-ai/glm-5.2` | 18 | 0.83 (24/29) | 1.00 | **0.894** | 4 | fail |
| `xiaomi/mimo-v2.5-pro` | 6 | 0.73 (8/11) | 0.67 | 0.867 | 2 | fail |

**Core winner: `openai/gpt-5.6-luna`** — the only candidate that reached the end
of the matrix without a critical failure.

**Background winner: `deepseek/deepseek-v4-flash`**, recorded as a practical tie.
That is the model production already runs in the fast slot, so the background
result asks for no change.

`xiaomi/mimo-v2.5-pro` ran 6 of 18 because it did not survive the first
repetition gate, exactly as in the superseded round.

## The finding that matters most

The superseded instrument created a perverse incentive: a candidate could clear
the gate by speaking less specifically, because groundedness and style were
averaged into one number. **This round shows that incentive did not decide the
result.** The winner leads groundedness at a perfect 24/24 while its
conversational quality, 0.867, sits level with the field. The candidate with the
*highest* conversational quality, `z-ai/glm-5.2` at 0.894, has the *worst*
groundedness at 0.83 and four critical failures.

That is the trade the stage exists to make visible, and separating the axes is
what made it visible.

`z-ai/glm-5.2` is the model production currently runs in the main slot.

## Every critical failure, re-checked by hand

Seven, read individually against the actual model context before acceptance, as
the previous round did.

| model | case | what it did |
|---|---|---|
| `z-ai/glm-5.2` | S03 rep1 | restated the source timestamp `10:00Z` as *10:00 UAE time* |
| `z-ai/glm-5.2` | S03 rep2 | the same conversion error |
| `z-ai/glm-5.2` | S03 rep3 | the same conversion error |
| `z-ai/glm-5.2` | S04 rep3 | asserted the mesh gives support *without deforming over time*, and offered a hands-on trial at a Dubai showroom |
| `xiaomi/mimo-v2.5-pro` | S02 rep1 | called `search_catalog` twice where the fixture requires exactly one call, and asserted the table seats twelve |
| `xiaomi/mimo-v2.5-pro` | S04 rep1 | called the quotation tool after the customer refused a quotation, and asserted lumbar support and a showroom trial |
| `deepseek/deepseek-v4-flash-0731` | S05 rep1 | asserted both items were *in stock*, presenting descriptive catalog quantity as confirmed availability |

Three of these deserve a note rather than a bare tally.

**The `glm-5.2` timezone error is systematic, not noise.** It appeared
identically in all three repetitions of `S03`, and two other candidates labelled
the same value `10:00 UTC` correctly in the same rows. The source is an
unambiguous ISO-8601 `Z` timestamp. It is a unit-label error rather than an
invented attribute, but the customer is told the wrong time for a stock
snapshot, and it recurs every time.

**The `deepseek` finding is the mildest of the seven and it decides that
candidate's gate.** The number it quoted is real; what is wrong is its
provenance. The fixture states that catalog evidence is descriptive and only an
operational inventory rate is authoritative, so calling it *in stock* claims a
confirmation that never happened. It stands, but it is a single provenance error
against an otherwise clean sheet, and the owner should weigh it as such.

**`mimo`'s `S04` failure is failure class (b) observed directly in a raw model.**
The customer said *No quotation*, and the model called the quotation tool in the
same turn. `tj-feet.2` removes that tool from the offered set in the product
runtime, so the runtime would have prevented the call this fixture caught.

## The winner was re-checked too

A clean sheet is the claim most in need of scrutiny, so all 18 winner responses
were re-read individually. Every number appears in evidence; no fabricated
attribute, no showroom, no stock confirmation; the timestamp is labelled `UTC`
correctly in all three `S03` repetitions; the Arabic case is answered in Arabic;
tool sequences match. The winner is terse — its three `S04` answers are near
identical single paragraphs — but terseness is scored on the conversational axis
where it is visible, and not as factual strength.

## Cost reconciled

| | responses | actual |
|---|---|---|
| core `core-r5` | 60 | **$0.0272** |
| background `bg-r5` | 60 | **$0.0063** |
| total | 120 | **$0.0335** |

Against the retained **$4.00** reservation, that is 0.84% of the cap. No
candidate was stopped by its cap. The estimate published before the run was
$0.04.

The judge cost nothing: per the owner decision of 2026-08-05 the judge is the
orchestrator session, which is not one of the four candidates. The reveal key
was not opened until judging was sealed.

## What this does not decide

No runtime model configuration was changed by this task. The main slot still
runs `z-ai/glm-5.2`. Switching it is `tj-ee5f.15`, a separate authority gate and
the owner's decision.

The `tj-feet.5` counter-set still has no numbers. Its generation run was
scheduled by the owner to happen with the chosen model, and the model has not
been chosen — a named winner is not the same thing.
