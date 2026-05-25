# Orchestrator Handoff
Updated: 2026-05-25
Current branch: `codex/tj-gh42-quote-context-provenance`

## Current Truth
- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release includes runtime commit `322bee30d667b245a143813dbd5fccbcf120eecf`; GitHub Actions run `26279825756` succeeded, including deploy; `/opt/noor/.release-sha` and `/opt/noor/.release-run-id` read back `322bee30d667b245a143813dbd5fccbcf120eecf` / `26279825756`; production smoke `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7 passed, 0 failed`.
- Stages `tj-gh18`, `tj-gh19`, `tj-gh21`, `tj-gh22`, and `tj-gh23` are delivered; GitHub #11 and Beads `tj-gh22.1` were closed by owner request after production evidence.
- `tj-gh20` remains production `shadow` only: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- `tj-gh23` live E2E on approved `+79262810921` proved quotations `Fr3294`/`Fr3295`, approval handoff, ambiguous CH 616 clarification, and synthetic cleanup.
- Stage `tj-m7wz` is the active local implementation for GitHub #41-#46 quotation context and PDF provenance regressions. Dedicated worktree: `/home/me/code/treejar/.worktrees/codex-tj-gh42-quote-context-provenance`; branch: `codex/tj-gh42-quote-context-provenance`; base `origin/main` commit `29d16ec8d13ef8c7fb367289a27bf49c72026bea`.
- Local `tj-m7wz` fixes cover bare quantity replies after missing-quantity prompts, quote resume from assistant prose confirmations, terse customer details with `individual purchase`, and customer-facing quotation PDF fields that must not use stale CRM/test company/email context.
- Local `tj-m7wz` verification and stage closeout passed after installing `frontend/admin` dependencies in the isolated worktree: ruff, format check, mypy, targeted quote regression pack `82 passed, 122 deselected`, full `pytest tests/` `1136 passed, 16 skipped`, and process verification. Final visible correctness review found no blockers.
- `tj-m7wz` is not yet delivered to production. User authorized live E2E on `+79262810921` after completion, but the fixed commit must be delivered to the runtime before that E2E can prove the production issues are fixed.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended
Next stage id: `tj-m7wz`.
Recommended action: complete `tj-m7wz` delivery, verify deployed runtime, then run live E2E on approved `+79262810921` for GH #41/#42, #43/#46, and #44/#45. Do not close GitHub issues until live evidence is recorded.

## Starter prompt for next orchestrator
Use $orchestrator-stage for the next production task. Current delivered production release is still `322bee30d667b245a143813dbd5fccbcf120eecf` unless freshly verified otherwise. Active local stage `tj-m7wz` on branch `codex/tj-gh42-quote-context-provenance` fixes GitHub #41-#46 quotation context/PDF provenance regressions and passed local gates. Next: deliver the fixed commit, verify runtime, run production smoke, then live E2E on approved `+79262810921` using the previous `tj-gh23` controlled E2E pattern.

## Explicit defers
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Full production follow-up FU1/FU2/FU3 matrix was not fully time-tested before #11 closure; future validation needs explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic.
- Post-quotation pre-acceptance delivery-question answer quality remains a future follow-up candidate.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-m7wz` live E2E remains pending until the fixed commit is delivered to production; tracked by Beads `tj-m7wz`.
