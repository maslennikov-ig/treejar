# Orchestrator Handoff

Updated: 2026-05-15
Current branch: `codex/tj-long-memory-e2e`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `cf966f0e2345da0154c8f11f57c0c60340ff451e`; GitHub Actions run `25910228955` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh15` fixed GitHub #36/#37, passed short live E2E, and the issues are closed. Details: `.codex/stages/tj-gh15/summary.md`.
- Stage `tj-e2e15` ran a separate long-dialog production E2E stress test on the approved personal number `+79262810921` and found a new blocker.
- Stress conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7`: turn 1 `name-gate` passed, turn 2 bare `Lili` stored name and resumed product planning, turn 3 company detail triggered `z-ai/glm-5|verified-policy` and `escalation_status=pending`.
- After that, turns 4-6 returned manager-notified fallback replies and turn 7 timed out; long-dialog retention did not pass.
- New Bead `tj-e2e15.2` is open as P1: customer detail-only messages during active product/quotation context must not trigger verified-policy handoff.
- Stage summary: `.codex/stages/tj-e2e15/summary.md`; artifact: `.codex/stages/tj-e2e15/artifacts/tj-e2e15.1-stress-failed.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: `tj-e2e15.2` or a new fix stage for the long-dialog detail-capture escalation bug.

Recommended action: use $orchestrator-stage to fix `tj-e2e15.2`, deploy it, clean `+79262810921` again with approval already tied to this testing flow, and repeat the long-dialog E2E stress test through the final summary turns.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-e2e15.2`. Current delivered production release is `cf966f0e2345da0154c8f11f57c0c60340ff451e`; `tj-gh15` is closed, but `tj-e2e15` found a new production blocker in conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7`.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- `tj-e2e15.2` remains open for code fix, deploy, and repeat long-dialog E2E validation.
