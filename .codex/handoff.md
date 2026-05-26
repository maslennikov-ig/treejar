# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Production runtime readback: `428f360d7e8a97f936cf0eb2084d4aa6ecaf6801`, run `26441317711`.
- Production smoke passed after readback: `7 passed, 0 failed`.
- `main` includes later orchestration-only commits `3413c3f` and `7d528b8`; deploy was skipped, so runtime remains `428f360`.
- `tj-mmj8` Fr3309 is merged, deployed, production-smoked, and live E2E verified on `+79262810921` with isolated suffixes `tj-mmj8-fr3309-*`.
- Core evidence: slash `Fr3310`, multiline `Fr3311`, low-confidence confirm `Fr3312`, labeled fields `Fr3313`; PDFs preserve `Lilia`, `LLD`, `Lfdsf@kfsl.ru`, and expected address.
- Later ambiguous `individual / dubay 2 street 7` did not overwrite company `LLD`.
- All 7 synthetic Fr3309 conversations were closed; cleanup readback `active=0`, `escalated=0`.
- `tj-mmj8` remains `in_progress` only pending explicit Beads closure approval; evidence supports closure.
- Detailed evidence lives in `.codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md`.
- Out-of-scope bugs opened: `tj-4cm4` exact SKU clarification resume, `tj-8ma2` sales-order quote resume, `tj-nzob` comma-separated brief company parsing.
- `tj-gh20` remains production `shadow` only.

## Next recommended
Next stage id: `tj-4cm4` or `tj-8ma2`.
Recommended action: close `tj-mmj8` after explicit owner approval, then fix `tj-4cm4`, `tj-8ma2`, or `tj-nzob` from `origin/main` in an isolated workspace.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from handoff and the `tj-mmj8` production E2E artifact. Do not reopen Fr3309 unless new evidence contradicts it. Select one focused Beads task (`tj-4cm4`, `tj-8ma2`, or `tj-nzob`), work from `origin/main` in isolation, write RED tests first, run gates, and request explicit authorization before deploy/live tests.

## Explicit defers
- `tj-mmj8`: Beads closure pending explicit owner approval only.
- `tj-4cm4`, `tj-8ma2`, `tj-nzob`: production E2E follow-up bugs.
- `tj-b4n` / GitHub #24 remains provider-blocked pending official Wazzup typing endpoint.
- FU1/FU2/FU3 production follow-up matrix needs approved copy/templates.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
