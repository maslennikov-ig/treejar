# Stage tj-vhto-current-build-round

Status: accepted; `tj-vhto` closed
Base: `main` at `3682203`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — the frozen repository
acceptance harness, protected stored runs, and one existing provider client.

docs-reviewed: updated - one tracked report,
`docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md`, and the
handoff now carries the current number, the measured instrument floor, and the
three defects the round found. `AGENTS.md` and `README.md` describe neither the
harness nor the rubric, so neither needed a change.

project-index: reviewed-no-change — one new script beside the existing
corpus-bridge tools and one new report beside the existing ones. No directory
changed shape and no contract key moved.

## Scope

The owner asked how good the bot is right now, and declined the multi-turn set
as over-engineering for that question. One round on the frozen twenty at the
shipped tip, judged blind by the root, no paid second reader.

## Execution

Root-owned. The reading was completed before the paired comparison was
computed, so no delta could steer the scoring.

## Result

| measure | mean | 95% interval |
|---|---:|---:|
| weighted, 30-point scale | 15.3 | 12.6 to 17.9 |
| raw, client's convention | 12.8 | 12.0 to 13.5 |
| critical failures | 1 | known false positive `tj-2p4c` |

Cut by attainable ceiling, which is the only cut that means anything on this
set: greeting-only openings 9.5 of 9.6 reachable (99%), openings with a real
request 22.4 of 30 (75%). The missing quarter is one behaviour — the bot lists
the right products and asks quantity, and does not ask what the customer is
trying to do. The two openings that scored 30 both asked it.

## What the round measured that was not the question

The only code change since the previous round was `tj-t6ug`, whose guards do
not run on a first turn, and the protected replay proves the rendered text is
identical. Yet the paired raw delta was −0.60 with an interval excluding zero.
That is this instrument's floor, measured directly, and it retires the earlier
round's +0.50 raw as a result.

Five openings carry all the movement. Dialog 819 at −22.5 is a repair-judge
provider failure, and dialog 28 at −12.2 is the same reply shape read more
strictly than in the previous sitting.

## Acceptance boundary

Twenty authorised generation calls and no paid scoring reader; complete
coverage and language; every delta attributed to a named cause or refused;
no claim the first-turn set cannot support.

## Verification

- preflight recorded `judge_model: root-orchestrator`; `--second-reader` was
  never passed.
- 20 Luna calls, 1 repair-judge call, 0 scoring calls, $0.005386.
- 20/20 responses, 20/20 language, 300/300 criteria read blind.
- pairing by `scripts/corpus_bridge/pair_rounds.py`, which refuses to pair
  across judges or across frozen sets.
- `uv run ruff check src/ tests/ scripts/`: passed.
- `uv run ruff format --check src/ tests/ scripts/`: passed.
- `uv run mypy src/`: passed over 174 source files.
- `uv run pytest tests/ -v --tb=short`: 3609 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh`: passed.

## Risks / Follow-ups / Explicit defers

No defer. Three defects tracked: `tj-0s42` the repair judge has no retry;
`tj-4q79` the root judge drifts between sittings by more than the deltas being
reported; `tj-ge07` no frozen set has a second turn.
