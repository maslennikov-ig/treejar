# Luna/GLM acceptance on frozen real openings

Date: 2026-08-10

Beads: `tj-vz7o.10`
Selection seed: `20260810`

## Outcome

This round does **not** support the statement that the opening experience is
ready for client acceptance.

The frozen set contains 20 of 629 evaluated natural-text customer openings,
five from each of four length strata. Exactly 20/20 openings received a
non-empty `openai/gpt-5.6-luna` response, and exactly 20/20 responses received a
valid `z-ai/glm-5.2` evaluation. No live traffic, production mutation, customer
message, deploy, or push was used.

After correcting a deterministic numeric-normalization defect in the harness,
two critical failures remain in 2/20 openings: **10.0%, Wilson 95% CI
2.8%–30.1%**. One response asserted an unsupported starting price when its
catalog evidence was empty. One acknowledged an assembly request but did not
answer it or clearly commit to verification.

## Measured result

| Measure | Result | Denominator and interval |
|---|---:|---|
| Luna response coverage | 20/20, 100% | 20 frozen openings; fixed-set coverage 100%–100% |
| GLM evaluation coverage | 20/20, 100% | 20 Luna responses; fixed-set coverage 100%–100% |
| Correct-language responses | 20/20, 100% | 20 frozen openings; fixed-set coverage 100%–100% |
| Luna time to first reply | 2.508 s median | 20/20 replies; stratified-bootstrap 95% CI 2.310–2.948 s |
| Project weighted score | 11.9/30 | 20 openings; stratified-bootstrap 95% CI 10.2–13.7 |
| `raw_total`, scored by GLM | 11.0/30 | 20 openings; stratified-bootstrap 95% CI 10.4–11.6 |
| Remaining critical failures | 2 in 2/20 openings | 10.0%; Wilson 95% CI 2.8%–30.1% |
| Luna model cost | $0.004581 total | exactly 20 calls |
| GLM model cost | $0.181726 total | exactly 20 calls |

The protected preflight and run evidence is under
`<git-common-dir>/codex-orchestration/corpus-bridge/tj-vz7o-luna-glm-20260810`
with directory/file modes 0700/0600. It records the model identities, provider
model identities, call journal, usage, costs, prompt/configuration digests, and
the transcript-bearing records. The tracked repository contains no opening or
response text.

## What the first automatic result got wrong

The first deterministic pass reported seven critical flags across 6/20
openings. Five flags across five openings were false numeric-grounding failures:
the response repeated a price serialized as an integer instead of a zero-decimal
number, dimensions embedded in a product name, or a deadline range from the
opening. The facts were present in that opening's injected evidence.

The analyzer now canonicalizes equivalent numeric formatting and reads numeric
facts from the evidence fields actually shown to Luna. Re-analysis makes no
model or catalog call, preserves the original protected output, and leaves two
critical failures across 2/20 openings. The rubric and
`_build_applicability_assessment` are unchanged.

## Why the score threshold cannot be used

Before calls, this stage proposed accepting only when the lower bound of the
weighted-score interval reached 20.0/30. The measured applicability maps expose
that as a bad gate: 11/20 openings have six applicable rules spanning only two
rubric blocks. Under the frozen `calculate_weighted_score` low-coverage rule,
all 11 have a deterministic maximum of 9.6/30 even if every applicable rule
scores 2/2. Only 9/20 openings can reach 30.0/30.

The gate was not changed after seeing the result. It failed and is retired from
decision use. `tj-vz7o.10.2` must freeze a shape-aware gate before any paid
rerun. This is a defect in this round's acceptance design, not evidence that the
set or frozen scorer should be rewritten.

## Two responses read by eye

Two protected opening/response pairs were read in full; no text was copied into
Git.

- In one long, specific request, Luna greeted and identified itself well and
  captured the main needs. It then listed products too early, was inconsistent
  about how certain stock information was, left the assembly question
  unresolved, and assumed a location that had not been confirmed.
- In one very vague product request, Luna safely withheld an irrelevant catalog
  answer, asked useful clarifying questions, and asserted no unsupported number.
  The answer was sound but somewhat templated and asked several questions at
  once.

The manual read agrees with the corrected critical gate: the system can produce
a strong safe opening, but the two remaining failure modes are real enough that
they cannot be averaged away.

## What can and cannot be said to the client

The earlier response-operations claim remains supported: humans replied to
1,223/1,358 customer openings with a median first reply of 1,080 seconds (95%
CI 840–1,890 seconds), while the stored Noor packets replied to 53/53 openings
with a median of 15.61 seconds (95% CI 9.99–21.51 seconds), across 19 scenarios.
This new isolated round adds 20/20 Luna replies with a 2.508-second median (95%
CI 2.310–2.948 seconds) over the 20 frozen openings.

It does not support a conversion, revenue, deal-size, close-rate, or
off-channel-outcome claim. It also does not remove the client-judge confound:
the selected human baseline is `raw_total` 5.60/30 (95% manager-cluster CI
3.91–6.45) over 20 dialogues and five manager groups, but it was scored by the
client's judge. The Luna value above was scored by GLM. Those numbers must not
be compared as though only the salesperson changed.

## Beads disposition

- `tj-vz7o.3`, `tj-vz7o.6`, and `tj-vz7o.7` remain closed.
- `tj-vz7o.4` remains open: authority for exactly 53 Haiku calls was explicitly
  declined, and no Haiku call was made.
- `tj-vz7o.5` remains open and dependent on `tj-vz7o.4`.
- `tj-vz7o.8` and `tj-vz7o.9` remain drafted and unsent.
- `tj-vz7o.10` remains open because this round did not pass.
- `tj-vz7o.10.1` tracks the two remaining product failures.
- `tj-vz7o.10.2` tracks the shape-aware acceptance gate required before a
  rerun.
