# Stage tj-399z-measured-round

Status: accepted
Base: `main` at `517f7f6`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — the round runs repository-local
code against pinned protected evidence.

## Goal

Run one measured `openings-20` round after `tj-3jo0`, `tj-7vhq`, `tj-b8il` and
`tj-zewi`, read it blind, and pair every applicable rule against `tj-68au`.

## Result

The root read the round blind before opening the baseline. Coverage is 20/20
generated, 20/20 read, 20/20 in the customer language, with zero critical
failures. Thirteen openings reached their own ceiling.

| Rule | tj-399z | Ceiling | tj-68au | Delta |
|---|---:|---:|---:|---:|
| 1 | 2.00 | 2.00 | 2.00 | 0.00 |
| 2 | 1.95 | 2.00 | 1.90 | +0.05 |
| 3 | 2.00 | 2.00 | 2.00 | 0.00 |
| 4 | 1.95 | 2.00 | 2.00 | -0.05 |
| 5 | 1.80 | 1.95 | 1.85 | -0.05 |
| 7 | 1.95 | 2.00 | 2.00 | -0.05 |
| 8 (n=6) | 1.83 | 2.00 | 2.00 | -0.17 |
| 9 (n=6) | 2.00 | 2.00 | 2.00 | 0.00 |

Rules 6, 10, 11, 12, 13, 14 and 15 are not applicable in this opening-only
rig. Rule 13 is not applicable on all twenty and did not move.

Raw mean is 12.8 of the unchanged 13.2 mean ceiling, 95% interval 12.2–13.4.
Weighted mean is 15.2. The 14 openings in the 9.6 band average 9.4; the six in
the 30.0 band average 28.9. Paired against `tj-68au`, raw delta is -0.15 per
opening (95% -0.35 to +0.05) and weighted delta is -0.28 (95% -0.60 to 0.00).
Both are far inside the measured 2.0 raw-point reader gap.

## Defect shapes

- Gone: dialog 28 no longer receives the price anchor. Rule 2 moved 1 to 2 on
  that dialog and no other rule on it moved. This is `tj-7vhq` working.
- Validated without a score change: the AED 491 workstation floor is credible
  beside the priced workstation rows. No new anchor-family bead is needed;
  this is `tj-3jo0` working.
- Unchanged: dialog 436 still presents a non-work table under the office-table
  family, so rule 2 remains 1 there. The same family-mismatch shape was present
  in `tj-68au`.
- Unchanged: dialogs 420 and 1000 still use product-led discovery lists under
  rule 5. New on dialog 442: another product-led list (`tj-j62b`).
- New: dialog 807 repeats the value proposition as a capability list
  (`tj-593w`); dialog 819 silently drops requested needs (`tj-1orh`); dialog
  1067 stacks the clarification with two name questions (`tj-b8px`).
- Arabic punctuation is correct on dialog 1291 and does not affect scoring.

## Cost and protected evidence

Owner authorization covered 20 Luna calls and at most 20 repair-judge calls.
Actual: 20 Luna, zero repair-judge, zero scoring-judge, no second reader;
`$0.006473`. Protected artifact:
`/home/me/code/treejar/.git/codex-orchestration/corpus-bridge/tj-399z-round-20260814`.

## Verification

- Preflight: 19 priced, 1 withheld; AED 250 / 491; retrieval `29123d5f…`.
- Replay: current `1b425bd1…` against frozen `1fc87c04…`; the same 7 expected
  differences on dialogs 28, 875 and 1291.
- Ruff, format and Mypy passed; process verification passed.
- First full pytest exposed four traceability digest failures caused solely by
  moving `.codex/orchestrator.toml` to this stage: 3794 passed, 20 skipped, 4
  failed. The sanctioned current-state re-pin updated three digest fields; all
  four focused failures then passed. Final full pytest returned exactly to the
  baseline: 3798 passed, 20 skipped, 0 failed.
- Canonical stage closeout: corpus-bridge group 67 passed, 1 skipped; stage
  readiness and process verification passed.

docs-reviewed: updated — handoff and this stage carry the durable result.
project-index: reviewed-no-change — no runtime entrypoint or module moved.
graph-reviewed: no-change-needed — Graphify is not initialized.

## Explicit defers

`tj-j62b`, `tj-593w`, `tj-1orh` and `tj-b8px` are bounded product defects from
this stochastic draw and are outside the measured-round scope. Nothing else is
unfinished.
