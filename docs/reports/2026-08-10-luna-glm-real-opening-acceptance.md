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
| Project weighted score | 11.9/30 — **not a level**, see below | 20 openings of two different ceilings; stratified-bootstrap 95% CI 10.2–13.7 |
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
decision use. This is a defect in this round's acceptance design, not evidence
that the set or frozen scorer should be rewritten.

## Why 11.9/30 is not a level, and what replaced it

The same arithmetic that retired the gate disqualifies the aggregate. Eleven of
the twenty openings can attain at most 9.6/30 and nine can attain 30.0, so their
mean is an average of two incommensurable numbers and no opening could have
scored it. It is reported above only because withdrawing a published figure in
silence is worse than labelling it.

`tj-vz7o.10.2` is now frozen, before any rerun, and states no absolute score at
all:

- 20/20 responses, 20/20 evaluations, 20/20 in the customer's language.
- Zero critical failures. A fabricated figure is a defect at any score, so this
  is the one absolute and it is not a threshold that can be tuned.
- Score decided by a **paired delta** over the same twenty openings and the same
  judge, reported per attainable ceiling. `attainable_weighted_score` derives the
  ceiling from the frozen scorer itself, so it cannot drift from the scorer it
  describes.

Two facts make an absolute level impossible here rather than merely awkward: the
mixed ceilings above, and the judge. GLM does not bridge to the client's
`claude-haiku-4.5` on any figure, so no level measured with it can be read as
readiness against the client's own numbers. A paired comparison survives both.

## Two numbers that must never be subtracted

`18.71/30` (`tj-vz7o.3`) and `11.0/30` (this round) are both labelled
`raw_total`, both dated 2026-08-10, and they are **not comparable in either
direction**. Two things differ at once, not one:

- **The judge.** 18.71 came from a blind Claude reader panel; 11.0 came from
  `z-ai/glm-5.2`. This project has already measured a 3.8-point systematic shift
  between two judges on identical text.
- **The set.** 18.71 is 53 stored packets over 19 hand-built scenarios; 11.0 is
  20 real customer openings — the zone where the failure was measured in the
  first place, at R06 8.10 and R07 7.35 against R02 29.07.

Read as a drop, that pair says the bot got worse. Nothing here supports that,
and nothing here refutes it either. The comparison simply was not made.

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
- `tj-vz7o.10.1` closed: both failures fixed, with a third found while fixing
  them. See below.
- `tj-vz7o.10.2` closed: the acceptance contract above is frozen in
  `ACCEPTANCE_CONTRACT`, before any rerun.

## What the two failures turned out to be

Both were real, and neither was an artefact of the harness. Both were traced to
a cause upstream of the sentence that failed.

**The invented price** was invited by our own prompt. The greeting stage rule
said, in as many words, "if they only greeted you, name what Treejar supplies
and give one category with its starting price from the catalog" — on a turn
where no catalog lookup has happened and no row exists. The model was asked for
a fact the turn could not supply, and supplied one. The rule now says every
price comes from a `search_products` result in that same reply, and with no
result the price waits a turn.

That fixes the cause; the guarantee behind it was missing too. `GroundingViolation`
had three members and all three were text patterns, so none of them could see
that no row stood behind a figure. `UNVERIFIED_PRICE` is the first that is told
what was actually verified. It is deliberately narrow: it runs only when the turn
touched no catalog at all, because a per-row price claim belongs to the claim
contract, and a blunter rule here would strip real quotations — a worse defect
than the one being fixed.

**The deferred assembly question** needed no new fact, only a named owner. The
reply said stock, drawer options and assembly "still need confirmation", which
was true and told the customer nothing about whether anyone would find out.
`commit_to_what_you_deferred` adds the missing half-sentence next to the
deferral rather than at the end after the questions. Stock is deliberately
excluded: promising to go and check stock is a `FUTURE_STOCK_CHECK` violation
that grounding removes on purpose, and a guard that adds a sentence the next
guard deletes is worse than no guard.

**The third finding: the harness measured the model plus one guard.** It applied
`apply_opening_guard` and stopped, where production also runs the deferral guard
and `enforce_grounding_output` before a customer sees anything. Neither failure
above was caused by that gap — both survive the full pipeline, which is how they
were confirmed real — but a round that reports a defect production would have
filtered cannot be told from a real one afterwards. The harness now applies the
shipped guards, and a test holds it there.
