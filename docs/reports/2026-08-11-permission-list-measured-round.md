# Permission-list measured round: the targeted promises hold, the score movement is inconclusive

Date: 2026-08-11
Beads: `tj-mshi.5`, `tj-riim`, `tj-2p4c`, `tj-9dp2`
Build measured: `6649d2c`
Baseline: protected run `tj-rt7w-round-20260811`
Judge: the root orchestrator, reading blind. No second reader was requested.

## Authorization, calls, and cost

The owner authorized exactly 20 `openai/gpt-5.6-luna` generation calls for
this round, with a per-model harness cap of $1.00 and a two-stage ceiling of
$2.00. The run made exactly **20 Luna calls and zero judging calls**.

Actual cost was **$0.005458** (5,458 micro-USD), compared with the expected
approximately $0.005 and the prior baseline's $0.004661. No second reader,
live traffic, deploy, production mutation, real-user message, push, or model
configuration change occurred.

The frozen scenario digest was
`2ba7e4fe97a3142279eb2d84c8b4cf7c2371f34dff8f83b0710cc99bd6865ab8`,
identical to the baseline. Coverage was 20/20 responses, 20/20 root
evaluations, and 20/20 responses in the customer's language. The root read
all 20 replies and all 300 criteria; it recorded zero red flags.

## Paired result

The paired comparison uses the same frozen openings and the same root judge,
with 10,000 stratified bootstrap samples and seed `20260810`.

| measure | baseline to candidate delta | 95% interval | conclusion |
|---|---:|---:|---|
| Weighted score on the rubric's 30-point scale | +0.32 | -0.86 to +1.82 | inconclusive |
| Raw criterion total | +0.25 | -0.10 to +0.70 | inconclusive |
| Critical failures | 1 to 1 | n/a | did not rise |

The observed score movement is inside its uncertainty. This round therefore
does not support a claim that the permission list improved general first-turn
quality. It does support the narrower stage claim that critical failures did
not rise.

## Reading the two targeted directions

**Unsupported promises.** Dialog 28 no longer promises recruitment routing,
a callback, or a shortlist outcome. It directs the sender to the official
application route and leaves the application with the sender. Dialog 789
still states that Treejar supplies new furniture and does not buy, resell, or
assess customer-owned furniture. The root recorded no red flag on either.
This closes `tj-riim` and preserves the prior customer-owned-furniture fix.

**Supported next steps.** Rules 14 and 15 remained 0 to 0, with zero delta.
The frozen applicability map marked both rules not applicable on all 20
openings, so their candidate applicable count is 0/20. The round cannot test
whether the permission list is too tight or whether those supported promises
would improve a reachable next-step turn. This is an instrument limitation,
not evidence of either success or failure.

## The one public-harness critical

The frozen harness reports one `hallucination` critical on dialog 1067. The
root reading found no unsupported claim: the reply copied a SKU present in the
catalog evidence. The numeric detector extracted an internal digit from that
SKU, while `_allowed_numbers` admits product name, price, and stock but not the
SKU field. This is a deterministic false positive in the measurement ruler,
tracked as `tj-2p4c`.

The ruler and historical output remain unchanged because applicability,
rubric, and scoring logic were frozen for this stage. Accordingly, the report
preserves the public count of 1 and separately records the root's zero-red-flag
reading. The generic harness field remains `accepted: false`; the stage's
pre-registered acceptance was the paired no-rise test, which is 1 to 1.

The public summary also labels the judge as `z-ai/glm-5.2`, although the
protected run-state records `root-orchestrator` and zero judging calls. That
metadata defect is tracked as `tj-9dp2`; provider and cost claims in this
report come from the protected preflight and run-state, not that stale label.

## Protected evidence

Transcript-bearing evidence remains outside Git under
`.git/codex-orchestration/corpus-bridge/tj-mshi-permission-list-20260811/`.
The tracked report contains no customer opening or assistant reply text.
`paired-comparison.json` records the paired aggregates and per-dialog integer
deltas; `root-judgment.json` records the blind root reading.

## Stage conclusion

The stage-specific acceptance is met: 20/20 coverage and language, criticals
did not rise, dialog 28 is honest, and dialog 789 stays fixed after deletion
of the prompt block. The score movement is inconclusive, and rules 14/15 are
unobservable on this frozen first-turn set. No broader quality or conversion
claim is made.
