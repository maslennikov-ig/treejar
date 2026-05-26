# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `main`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `main@000798e` includes the selective `tj-final27.4`-`.8` port and was pushed on 2026-05-26.
- GitHub Actions run `26447020048` passed changes, lint, tests, type-check, and deploy for `000798e`.
- Read-only production smoke after deploy passed: `/api/v1/health` OK with Redis OK, products `200`, conversations auth guard `403`, quality auth guard `403`, dashboard auth guard `401`, admin metrics auth guard `401`, webhook empty payload `200`, admin `200`.
- `tj-mmj8` Fr3309 is merged, deployed, production-smoked, and live E2E verified on `+79262810921` with isolated suffixes `tj-mmj8-fr3309-*`.
- Core evidence: slash `Fr3310`, multiline `Fr3311`, low-confidence confirm `Fr3312`, labeled fields `Fr3313`; PDFs preserve `Lilia`, `LLD`, `Lfdsf@kfsl.ru`, and expected address.
- Later ambiguous `individual / dubay 2 street 7` did not overwrite company `LLD`.
- All 7 synthetic Fr3309 conversations were closed; cleanup readback `active=0`, `escalated=0`.
- `tj-mmj8` remains `in_progress` only pending explicit Beads closure approval; evidence supports closure.
- Detailed evidence lives in `.codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md`.
- Out-of-scope bugs opened: `tj-4cm4` exact SKU clarification resume, `tj-8ma2` sales-order quote resume, `tj-nzob` comma-separated brief company parsing.
- `tj-gh20` remains production `shadow` only.
- `tj-final27.4` through `.8` useful work has been selectively ported from stale `origin/codex/tj-final27-acceptance-integration` and merged to `main@000798e`; old handoff/orchestration drift was intentionally not ported.
- Local final27 port verification passed: targeted suites `50+55+7+15`, combined targeted suite `127 passed`, backend `ruff`/format/`mypy`, frontend admin `npm ci`/lint/build, no-stage process verification, and full `pytest` (`1177 passed, 19 skipped`). Local `npm ci` emitted a Node engine warning because Node `v24.15.0` is outside `>=22.12.0 <23`.
- Legacy `tj-final27` artifacts have been normalized and merged locally; stage process verification now passes. Local `main` is ahead of `origin/main` with docs/orchestration-only commits.
- Referral search refresh on 2026-05-26 found no client-approved mechanics in client docs, stage artifacts, handoff notes, or Beads. Existing docs only define referral scope and request missing discount/bonus/activation parameters; internal implementation defaults are not approval.
- Approved 2026-05-26 bounded text E2E started: smoke `8/0`, chat canary passed, SKU `00-07024023` returned `310.65 AED` and stock `12` after name-gate, then run stopped on `tj-final27.17` price-objection misread as selected item. Current suffix readback: `2` conversations, `0` pending.
- `tj-final27.17` fix is merged locally to `main`: strip `[smoke:*]` before purchase-selection parsing. RED/GREEN, targeted tests, `tests/test_llm_engine.py` (`218 passed`), ruff, format-check, mypy, and stage process verification passed.
- No production config mutation, deploy, push, `scripts/verify_wazzup.py`, broad production suite, scheduled AI Quality Controls, live voice/audio/payment/referral/feedback branch, or real customer conversation has been run for this refresh.

## Next recommended
Next stage id: `tj-final27`.
Recommended action: push/deploy/retest `tj-final27.17` before widening final E2E. Keep referrals blocked until the client approves rules or explicitly excludes the module.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue from local `main`; it is ahead of `origin/main` with final27 docs/orchestration commits and `tj-final27.17`. Production still runs `main@000798e` until push/deploy completes. Request approval before widening beyond the narrow retest.

## Explicit defers
- `tj-mmj8`: Beads closure pending explicit owner approval only.
- `tj-4cm4`, `tj-8ma2`, `tj-nzob`: production E2E follow-up bugs.
- `tj-b4n` / GitHub #24 remains provider-blocked pending official Wazzup typing endpoint.
- FU1/FU2/FU3 production follow-up matrix needs approved copy/templates.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion; no approved mechanics found in repo evidence as of 2026-05-26.
- `tj-final27.9`: final acceptance still needs `tj-final27.17` deploy/retest or explicit defer, further live E2E approval, and approval for any live voice/media/payment/referral/feedback branch or production nonfunctional drill.
