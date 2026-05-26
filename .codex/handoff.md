# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `codex/tj-final27-port-current`

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
- `tj-final27.4` through `.8` useful work has been selectively ported from stale `origin/codex/tj-final27-acceptance-integration` onto current `main@50a1b52` in branch `codex/tj-final27-port-current`; old handoff/orchestration drift was intentionally not ported.
- Local final27 port verification passed: targeted suites `50+55+7+15`, combined targeted suite `127 passed`, backend `ruff`/format/`mypy`, frontend admin `npm ci`/lint/build, no-stage process verification, and full `pytest` (`1177 passed, 19 skipped`). Local `npm ci` emitted a Node engine warning because Node `v24.15.0` is outside `>=22.12.0 <23`.
- Stage-scoped process verification for `tj-final27` is blocked by legacy artifacts that predate the current v2.14 artifact schema; the command reports missing frontmatter keys on older artifacts and legacy `status: deployed` in `tj-final27.11.md`.
- No deploy, production config mutation, `scripts/verify_wazzup.py`, broad production suite, scheduled AI Quality Controls, live voice/media/payment/referral test, or real customer conversation has been run for this final27 port.

## Next recommended
Next stage id: `tj-final27`.
Recommended action: push `codex/tj-final27-port-current` for review/CI, decide whether to normalize legacy `tj-final27` artifacts for stage-scoped closeout, then decide whether to merge/deploy and whether referrals are approved or explicitly excluded.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from branch `codex/tj-final27-port-current`. The selective final27 `.4`-`.8` port has passed local targeted/backend/frontend/full pytest/no-stage process verification. Stage-scoped verification is blocked by legacy `tj-final27` artifact schema drift, not by the ported code. Preserve the current port, do not bring back stale source-branch handoff/orchestration drift, and request explicit authorization before deploy/live tests.

## Explicit defers
- `tj-mmj8`: Beads closure pending explicit owner approval only.
- `tj-4cm4`, `tj-8ma2`, `tj-nzob`: production E2E follow-up bugs.
- `tj-b4n` / GitHub #24 remains provider-blocked pending official Wazzup typing endpoint.
- FU1/FU2/FU3 production follow-up matrix needs approved copy/templates.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- `tj-final27.9`: final acceptance still needs merge/CI/deploy decision, possible legacy artifact normalization for stage-scoped closeout, and explicit approval for any live voice/media/final E2E or production nonfunctional drill.
