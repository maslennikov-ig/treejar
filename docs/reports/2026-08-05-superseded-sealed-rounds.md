# Superseded sealed rounds

Task: `tj-feet.7`. Recorded 2026-08-05.

The sealed model comparisons of 2026-08-04 and 2026-08-05 are **superseded**.
They stay exactly where they are and are not rewritten. This file is the record
of why they no longer decide anything.

| round | evidence | status |
|---|---|---|
| `20260804/core`, `core-r3`, `background`, `bg-r1`, `bg-r3` | protected, outside Git | superseded |
| `20260805/core-r4`, `bg-r4` | protected, outside Git | superseded as a decision; retained as the calibration source for `tj-feet.4` |

## Why

Two independent reasons, either of which is sufficient.

**The fixtures they ran on were defective.** All 8 critical failures of
`core-r4` fell in `S01` and `S04`, the two cases `tj-feet.7` repairs.

- `S01` required the model to explain how the package covers a twenty-person
  office and never supplied a desk capacity. Answering required inventing a
  per-desk occupancy; not answering failed the instruction. The case punished
  both branches, so its verdicts measured the trap rather than the model.
- `S04` asserted in its system prompt that verified catalog facts had been
  received, supplied not one attribute, and offered no lookup tool. Every
  attribute a model cited there was necessarily unsupported.
- `DK-4` implied ten seats in `S01` and was described as a four-person desk in
  `S05`. One SKU, two capacities, inside one fixture set.

**The instrument that scored them was defective.** `tj-feet.4` replaces it. The
superseded rounds averaged five dimensions into one number and used a single
undifferentiated critical-failure flag; against the ten-case anchor set that
instrument reaches 7 of 10 verdicts.

## What this does and does not invalidate

The **selection** is superseded. `core-r4` named `openai/gpt-5.6-luna` the winner
on the ground that every other candidate failed a hard-profile gate; since most
of those gate failures came from the two defective fixtures, that reasoning no
longer stands on its own. `tj-feet.8` re-runs the comparison on the repaired
fixtures under the new rubric.

The **evidence** is retained and still load-bearing. `core-r4` is the source of
the `tj-feet.4` anchor set: ten hand-labelled responses whose claim structures
are recorded in `scripts/model_battle_anchors.py`. Superseding a decision does
not invalidate the transcripts it was taken from.

Scores from the superseded rounds and scores from `tj-feet.8` are **not
comparable** and must never be presented side by side without this statement.
They use different fixtures and a different rubric, and the new rubric reports
three separate axes where the old one reported one blended number.

## The repairs

| fixture | defect | repair |
|---|---|---|
| `S01` | demanded coverage, supplied no capacity | every catalog row carries `seats_per_unit`; `DK-4` is a four-person desk at 5 units, `covered_seats` is 20, total AED 29,000 within the AED 30,000 budget |
| `S04` | claimed facts were received, supplied none | four real specification field paths supplied in the conversation turn that "received" them; the case still tests the consent gate and nothing else |
| `DK-4` | ten seats in `S01`, four in `S05` | four seats everywhere |
| `AX-E1` | AED 800 in `S01`, AED 1,000 in `S05` | AED 800 everywhere; `S05` total becomes AED 15,600 |

The `AX-E1` price split was not in the original defect list. It is the same
class — one SKU carrying two truths across a fixture set — and repairing only
its `DK-4` instance would have left the class open, so it is closed here rather
than deferred.

`S04`'s supplied attribute set is deliberately short. A model that cites one of
the four supplied field paths is grounded; anything beyond them is still a
fabrication, so the case keeps its discriminating power instead of trading a
trap for a giveaway.

## Verification

```sh
uv run pytest tests/test_scripts_model_battle_fixtures.py -q
```

12 regressions. On the pre-repair fixtures 6 of them fail; all 12 pass after the
repair. They assert fixture properties rather than model behaviour, so they cost
nothing and fail loudly if a future edit reintroduces a trap.

Frozen `AC-01..AC-30` and its digest are untouched; the E2E acceptance manifest
suite passes unchanged.
