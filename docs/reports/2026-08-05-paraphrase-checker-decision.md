# The claim-level paraphrase checker: measured, and not adopted

Task: `tj-feet.9`. Measured 2026-08-05. Round `20260805/paraphrase-r1`,
protected evidence outside Git. Probe set `noor-paraphrase-probe/v1`, checker
`noor-paraphrase-checker/v1`. Total spend **$0.0081** across three runs.

**Decision: do not adopt as a blocking check now.** The checker works. What is
missing is a measured problem for it to solve, and the acceptance criterion this
task was written with cannot be met by any checker.

## Why the counter-set could not answer this

`tj-feet.5` put the unsupported-fact rate at 0.000 (0/42) on the chosen model.
The acceptance criterion says adoption happens only if the checker *beats the
`tj-feet.5` baseline on unsupported-fact rate*. Nothing beats zero. Measured
against the set this task was told to use, the checker is unfalsifiable in the
useful direction and would be judged entirely on its false blocks.

So the checker was measured on a set built for it instead, and the criterion is
answered on its merits rather than on its arithmetic.

## The probe set

24 probes, 12 pairs, English and Arabic, balanced 12 widened against 12
faithful. Each is one atomic claim against the one stored value it rests on.

No probe carries a number, SKU, price or stock. That is the specification's
constraint and it is enforced by a test rather than trusted: the claim contract
and the numeric grounding checks already own those, and a paid second opinion on
them is cost without cover.

The widened probes add a capability (*a synchronised tilt that adjusts
automatically to your posture*), a duty rating (*reinforced steel frame built
for heavy daily use*), a performance property (*scratch-resistant laminate top*),
a health outcome (*mesh back that prevents back pain*), a range of adjustment,
and a durability guarantee. The faithful probes reword without adding, and one
pair deliberately says *strictly less* than the value — *the frame is metal*
against a stored *steel frame* — because a generalisation is the near-boundary
case a strict checker blocks wrongly.

## Results

Three repetitions per probe, temperature 0, so 72 verdicts per candidate.

| | usable | TPR | TNR | false-block | median latency | cost per claim |
|---|---|---|---|---|---|---|
| `openai/gpt-5.6-luna` | 72/72 | **1.000** (36/36) | **1.000** (36/36) | **0.000** (0/36) | 2470 ms | $0.000041 |
| `deepseek/deepseek-v4-flash-0731` | 72/72 | 1.000 (36/36) | 0.972 (35/36) | 0.028 (1/36) | 1971 ms | $0.000038 |

Per language:

| | EN TPR | EN TNR | AR TPR | AR TNR |
|---|---|---|---|---|
| `gpt-5.6-luna` | 1.000 | 1.000 | 1.000 | 1.000 |
| `deepseek-v4-flash` | 1.000 | 1.000 | 1.000 | 0.944 |

Every verdict was stable across all three repetitions. The cheap candidate's one
error is `F04-ar`: it blocked *سطح العمل من اللامينيت* against a stored *سطح
لامينيت*, which is the same surface named with a different noun. The single
observed false block is in Arabic, which is the language the cited verifier
evidence base never covered.

## The artefact that would have produced the wrong conclusion

The cheap candidate was first run at a 200-token cap and returned **empty
content on 19 of 72 calls**. Seventeen of those nineteen were widened probes.
Read at face value that is *the cheap checker cannot detect widening*, and it is
not true: at a 900-token cap the same model, same probes, same temperature
answered 72 of 72 and scored as above. The cap was truncating the model
mid-reasoning.

It is recorded because the production form of that failure is worse than a wrong
answer. A checker that silently returns nothing, disproportionately on the claims
that most need checking, reads as *nothing to report*.

## Why it is still not adopted

**Nothing measured says widening is happening.** Across 42 counter-set responses
and 60 sealed-round responses on this model, the observed unsupported-fact rate
is 0.000 and no reviewed response widened a value that existed. The probe set
proves the checker catches widenings that were *constructed for it*; it does not
show that the assistant produces them.

**The cost is latency, not money.** At $0.000041 per claim the spend is
irrelevant — a three-claim turn costs $0.00012. The price is roughly 2.0 to
2.5 seconds median and up to 5 seconds at p90, per claim, on the customer's turn.
Claims checked in parallel still pay the slowest one; checked in series a
three-claim turn pays 6 to 7 seconds. That is a real cost against an unmeasured
benefit on a WhatsApp conversation.

**A perfect score on 24 hand-built probes is weak evidence, and it is mine.** I
wrote the probes and I labelled them, so the set carries my idea of what widening
looks like. Two candidates separated by a single verdict means the set is not
hard enough to rank checkers, and a checker cannot be accepted on a set that
cannot fail it.

## What would change the decision

1. A measured widening rate above zero on responses that were not built to
   contain one — from harder grounding cases or from reviewed real traffic.
2. Adoption in **flag-for-review** form rather than rewrite, which the task's
   own design names as the fallback when the false-block rate is a concern. A
   flag costs the same call and no customer-visible risk.
3. A probe set built by someone other than the person judging it, hard enough
   that a checker can fail it.

Until then this is a recorded negative result, which the acceptance criterion
explicitly allows. The instrument, the probe set and the runner are committed and
re-runnable, so revisiting costs a command rather than a rebuild.

## Not claimed

Two candidates, 24 probes, three repetitions, one judge who also authored the
probes, one day. TPR and TNR are reported on a synthetic set and do not estimate
performance on real traffic. Latency was measured over a residential WSL
connection to OpenRouter and is an upper bound on what a server would see, not a
production SLA.
