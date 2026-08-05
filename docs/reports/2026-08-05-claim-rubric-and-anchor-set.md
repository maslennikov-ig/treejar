# The claim rubric and its anchor set

Task: `tj-feet.4`. Built 2026-08-05 against the sealed round `20260805/core-r4`.

## What was wrong

The superseded instrument asked one judge for five 1–5 scores and one
`critical_failure` boolean, then averaged all five into a single quality number.
Two consequences, both observed in the round:

- A labelled assumption carrying a confirming question was scored a critical
  failure with `factual_trust` 1, while a vaguer assertion that named catalog
  attributes which did not exist scored `factual_trust` 4 and was not flagged.
  The instrument was measuring specificity, not fabrication.
- Because the five dimensions were summed, a well-written false claim could
  outscore a terse true one. Speaking less precisely was a winning strategy.

All 8 critical failures of the round fell in `S01` and `S04` — the two fixtures
`tj-feet.7` repairs — which is itself evidence that the instrument was reacting
to fixture defects as much as to model behaviour.

## What replaces it

`scripts/model_battle_rubric.py`. The judge supplies observations about each
claim; the code decides what they mean. Nothing in it calls a provider, so a
verdict is reproducible from its observations and any disagreement is locatable
at a specific claim rather than at a score.

### Four claim types

| type | requirement | verdict when unmet |
|---|---|---|
| `catalog_fact` | exact SKU, field path present in the retrieved row, wording within the stored value | fail, critical |
| `derived_fact` | source values present plus a shown deterministic computation | fail, critical |
| `explicit_assumption` | visible marker **and** a confirming question | **pass** unless it contradicts known data |
| `recommendation` | appropriateness | never a groundedness failure |

The load-bearing rule is the reclassification. An "assumption" without a visible
marker or without a confirming question is scored as the `catalog_fact` it is
imitating. Without that, the taxonomy would be a loophole: every fabrication
could be relabelled into the protected category.

### Three graders, never summed

- **groundedness** — passing grounded claims over grounded claims scored, with
  the denominator reported. A response that asserts nothing checkable reports
  `None`, not a perfect score.
- **tool obedience** — required call missing, forbidden call made, effect claimed
  without a successful call, sequence mismatch. Each is critical on its own.
- **conversational quality** — clarity, concision, persuasion, next step.

There is deliberately no total. Good style cannot offset a false fact, and
terseness cannot register as a factual error.

## Pinned versions

| | value |
|---|---|
| rubric | `noor-claim-rubric/v1` |
| anchor set | `noor-claim-anchors/v1` |
| judge | this orchestrator session, `claude-opus-5[1m]` |
| judged round | `20260805/core-r4` |
| candidates in that round | `z-ai/glm-5.2`, `deepseek/deepseek-v4-flash-0731`, `openai/gpt-5.6-luna`, `xiaomi/mimo-v2.5-pro` |

Owner decision of 2026-08-05: the judge is the orchestrator, not a paid provider
call. Provider spend is reserved for candidate models.

The non-candidate requirement still holds — the judge is not one of the four
models under comparison, so self-preference bias by construction is excluded.
A different bias is not excluded and is recorded here plainly: the same session
that implements the guards also grades them. Two things bound it. Grading is
done against blind labels, and the reveal key was never read. And every anchor
carries its rationale, so the owner can overturn any label without re-running
anything.

## The anchor set

Ten responses from `core-r4`, labelled by hand against their actual model
context. `scripts/model_battle_anchors.py` holds pointers and claim structures,
never captured wording — the sealed evidence stays outside Git.

| pointer | anchor verdict | superseded verdict | |
|---|---|---|---|
| `S01/rep3/C` | pass | critical | ✗ |
| `S01/rep3/B` | critical | critical | ✓ |
| `S01/rep3/A` | pass | pass | ✓ |
| `S01/rep1/A` | critical | critical | ✓ (cited a different claim) |
| `S01/rep1/C` | critical | pass | ✗ |
| `S01/rep1/D` | critical | critical | ✓ (tool axis only) |
| `S01/rep1/B` | pass | pass | ✓ |
| `S04/rep2/C` | critical | pass | ✗ |
| `S04/rep2/B` | critical | critical | ✓ |
| `S04/rep2/A` | critical | critical | ✓ (tool axis only) |

### Agreement

- Rebuilt rubric against the anchors: **10 / 10**.
- Superseded instrument against the anchors: **7 / 10 (0.70)**.

The first number is weak evidence on its own — the rubric and the anchor labels
come from the same judge, so it mainly proves the rules were encoded as written.
The second is the informative one: the rebuild changes three of ten verdicts,
and each of the three is a case the round got wrong in a way that shaped the
result.

Both are asserted by tests, so a future change to either the rules or the
anchors has to state which it is changing.

### The two verdicts the rebuild exists to fix

**`S01/rep3/C`, wrongly failed, now passes.** It stated a per-desk workstation
count behind an explicit approximation marker and closed by asking whether that
split was right, offering an alternative. The scenario carries no desk capacity,
so the claim contradicts nothing known. `tj-feet.1` shows the production catalog
carries no capacity field either, which makes a marked assumption the *correct*
behaviour here rather than a tolerated one.

**`S04/rep2/C`, wrongly passed, now fails.** It appealed to the SKU's "verified
catalog features" and named two attribute qualities in a scenario that supplies
no catalog attributes at all. It read as cautious because it was vague, and the
superseded instrument rewarded exactly that.

### Three findings that fall out of the labelling

- `S01/rep1/C` claimed the package covers all twenty people without ever stating
  the desk multiplier that conclusion needs. Hiding the missing number is not
  safer than stating it; the rubric scores it as an unshown `derived_fact`.
- `S01/rep1/A` was correctly failed for the wrong reason — the instrument cited a
  suggestion of future add-on categories, which is a `recommendation`, while the
  actual failure was a bare capacity assertion in the same reply. This is the
  second judge error the manual re-check found.
- `S01/rep1/D` and `S04/rep2/A` each failed two axes, and the instrument recorded
  only the tool one. `S04/rep2/A` is failure class (b) observed directly: the
  reply says it will not prepare a quotation and calls the quotation tool in the
  same turn. `tj-feet.2` removes that tool from the offered set.

## Verification

```sh
uv run pytest tests/test_scripts_model_battle_rubric.py -q
```

20 regressions cover the four claim types, the reclassification rule, axis
separation in both directions, the empty-denominator case, both anchor flips and
both agreement numbers.
