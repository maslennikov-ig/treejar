# Orchestrator Handoff

Updated: 2026-05-15
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `2b86b0366fde0358fed255e8da3c89aacedf556f`; GitHub Actions run `25932016725` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh15` fixed GitHub #36/#37, passed short live E2E, and the issues are closed. Details: `.codex/stages/tj-gh15/summary.md`.
- Stage `tj-e2e15` ran a separate long-dialog production E2E stress test on the approved personal number `+79262810921` and found a new blocker.
- Stress conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7`: turn 1 `name-gate` passed, turn 2 bare `Lili` stored name and resumed product planning, turn 3 company detail triggered `z-ai/glm-5|verified-policy` and `escalation_status=pending`.
- After that, turns 4-6 returned manager-notified fallback replies and turn 7 timed out; long-dialog retention did not pass.
- Stage `tj-e2e16` is deployed and live E2E verified: neutral detail capture, durable sales memory, saved-context summary, and high-risk handoff blockers.
- Final live E2E conversation `ae1c7a38-d7e6-401c-a520-07a0a480cd2e` retained name/company/address/products/quantities/delivery timing/assembly with escalation `none` and pending escalations `0`.
- Stage summary: `.codex/stages/tj-e2e15/summary.md`; artifact: `.codex/stages/tj-e2e15/artifacts/tj-e2e15.1-stress-failed.md`.
- Fix summary: `.codex/stages/tj-e2e16/summary.md`; artifacts: `.codex/stages/tj-e2e16/artifacts/tj-e2e16.1-3.md`, `.codex/stages/tj-e2e16/artifacts/tj-e2e16.4-5-live-e2e.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: none for tj-e2e16.

Recommended action: monitor normal production behavior; no remaining tj-e2e16 delivery action.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next distinct production issue. Current delivered production release is `2b86b0366fde0358fed255e8da3c89aacedf556f`; `tj-e2e16` is closed after live E2E.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- none for `tj-e2e16`.
