# Judged-repair measured round: clean turns stayed untouched

Date: 2026-08-11
Beads: `tj-n7p4.5`, `tj-n7p4`, `tj-2p4c`, `tj-9dp2`
Build measured: `0764ce2`
Baseline: protected run `tj-rt7w-round-20260811`
Judge: the root orchestrator, reading blind. No second reader was requested.

## Authorization, calls, and cost

The owner authorized exactly 20 `openai/gpt-5.6-luna` generation calls for
this round and only the repair-judge calls raised by those replies. The round
made exactly **20 Luna calls, zero repair-judge calls, and zero scoring calls**.

Actual round cost was **$0.005444** (5,444 micro-USD). Together with the stage-1
round ($0.005458) and the single stage-2 repair-path proof ($0.001265216), both
stages cost **$0.012167216** against the authorized $2.00 ceiling. Stage 2 used
1 of at most 25 authorized repair-judge calls.

The frozen scenario digest was
`2ba7e4fe97a3142279eb2d84c8b4cf7c2371f34dff8f83b0710cc99bd6865ab8`,
identical to the baseline. Coverage was 20/20 responses, 20/20 root
evaluations, and 20/20 responses in the customer's language. The root read
all 20 replies and all 300 criteria blind and recorded zero red flags.

No second reader, live traffic, deploy, production mutation, real-user
message, push, or model-configuration change occurred.

## Repair-path result

| event | count |
|---|---:|
| removal flags | 0 |
| repair-judge calls | 0 |
| approvals | 0 |
| corrections | 0 |
| cannot-fix results | 0 |
| rejected corrections | 0 |
| manager fallbacks | 0 |
| provider failures | 0 |
| before/after rewrite comparisons | 0 |

This is the intended clean-turn behavior: no flag means no second-vendor call
and no edit to model-written customer text. Because the frozen twenty raised
no removal flag, there was no rewrite to compare. The separate protected
60-output replay in `tj-n7p4.3` remains the triggered-path proof: its one flag
made one repair call, produced one accepted correction, and the root read that
correction beside the text it replaced.

## Paired result

The paired comparison uses the same frozen openings and the same root judge,
with 10,000 stratified bootstrap samples and seed `20260810`.

| measure | baseline to candidate delta | 95% interval | conclusion |
|---|---:|---:|---|
| Weighted score on the rubric's 30-point scale | +1.16 | -0.28 to +3.00 | inconclusive |
| Raw criterion total | +0.50 | +0.05 to +1.10 | positive on this sample |
| Critical failures | 1 to 1 | n/a | did not rise |

The weighted movement is inside its uncertainty. The raw ruler moved upward,
but the repair path did not fire in this round, so that movement cannot be
attributed to model-written repairs. No broader quality or conversion claim is
made. The pre-registered stage claim is narrower and passes: critical failures
did not rise, clean turns made no repair call, and no deterministic removal
changed their visible text.

Rules 14 and 15 remained unobservable: both were applicable on 0/20 openings
and scored 0 to 0. That instrument limitation is unchanged.

## The one public-harness critical

The frozen harness reports one `hallucination` critical on dialog 1067. The
root reading found no unsupported claim: the reply used a SKU present in the
catalog evidence. The numeric detector reads digits inside that SKU but its
allowlist omits the SKU field. This known deterministic false positive remains
tracked as `tj-2p4c`; the frozen ruler was not changed during measurement.

The baseline also has one critical, on a different dialog, so the public count
is 1 to 1. The root separately recorded zero red flags in the current twenty.
The public summary's stale GLM judge label remains tracked as `tj-9dp2`;
protected state proves `root-orchestrator` and zero scoring calls.

## Protected evidence and conclusion

Transcript-bearing evidence remains outside Git under
`.git/codex-orchestration/corpus-bridge/tj-n7p4-repair-round-20260811/`.
The tracked report contains only dialog identifiers, aggregates, counts, and
digests. `paired-comparison.json` records paired integer deltas;
`root-judgment.json` records the blind root reading; and
`repair-reading-pack.json` is empty because no rewrite occurred.

The round meets `tj-n7p4.5`: coverage and language are complete, criticals did
not rise, every triggered event and fallback class is counted at zero, every
rewrite was read because there were none, and cost stayed far below authority.
