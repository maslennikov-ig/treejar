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
- Local `tj-m7wz` fixes cover bare quantity replies after missing-quantity prompts, quote resume from assistant prose/availability confirmations, terse customer details with `individual purchase`, and customer-facing quotation PDF fields that must not use stale CRM/test company/email context.
- `tj-m7wz` first deploy `474583c79815ce7aac52d8558f89e49cf375f85c` / run `26399538830` succeeded; smoke passed; live #41/#42 passed on `+79262810921#tj-m7wz-qty-20260525a`.
- Live #43/#45 found residual availability-prose parsing gap: `Lil / individual purchase / 2 street` was stored as customer details but also misread as `2 x street`; local hotfix test now covers this and full pytest after hotfix passed `1137 passed, 16 skipped`.
- `tj-m7wz` second hotfix deploy and live E2E rerun are pending; do not close GitHub #41-#46 yet.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended
Next stage id: `tj-m7wz`.
Recommended action: deliver the `tj-m7wz` hotfix, verify deployed runtime, then rerun live E2E on approved `+79262810921` for GH #43/#46 and #44/#45. Do not close GitHub issues until live evidence is recorded.

## Starter prompt for next orchestrator
Use $orchestrator-stage for the next production task. Active stage `tj-m7wz` on branch `codex/tj-gh42-quote-context-provenance` has first deploy evidence for `474583c79815ce7aac52d8558f89e49cf375f85c` and a local hotfix for the live availability-prose gap. Next: deliver the hotfix commit, verify runtime/smoke, then rerun live E2E on approved `+79262810921`.

## Explicit defers
- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- Full production follow-up FU1/FU2/FU3 matrix was not fully time-tested before #11 closure; future validation needs explicit FU1 EN/AR free-form text configuration and approved Wazzup WABA FU2/FU3 template ids/codes for English and Arabic.
- Post-quotation pre-acceptance delivery-question answer quality remains a future follow-up candidate.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-m7wz` live E2E remains pending until the fixed commit is delivered to production; tracked by Beads `tj-m7wz`.
