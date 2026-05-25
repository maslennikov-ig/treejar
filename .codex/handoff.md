# Orchestrator Handoff
Updated: 2026-05-25
Current branch: `codex/tj-gh42-quote-context-provenance`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Production release: `6d91fde34f85936bb018d9ac0a778a918c05c066`; GitHub Actions run `26404203850`; smoke passed `7 passed, 0 failed`.
- Stages `tj-gh18`, `tj-gh19`, `tj-gh21`, `tj-gh22`, and `tj-gh23` are delivered; GitHub #11 / Beads `tj-gh22.1` were closed by owner request after production evidence.
- `tj-gh20` remains production `shadow` only: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- Stage `tj-m7wz` delivered GitHub #41-#46 quotation context and PDF provenance fixes from worktree `/home/me/code/treejar/.worktrees/codex-tj-gh42-quote-context-provenance`.
- `tj-m7wz` live E2E on approved `+79262810921` passed for quote resume, bare quantity, and reviewer-found mixed item-correction-plus-details; final quotation `Fr3307` used explicit fields only.
- Production synthetic cleanup for `tj-m7wz` is complete: 15 matching conversations are `closed`, `escalation_status=none`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended
Next stage id: none selected.
Recommended action: continue with the next owner-prioritized Beads/GitHub task; do not reopen `tj-6eb` unless scope changes.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Re-orient on Beads/GitHub, check production runtime `6d91fde34f85936bb018d9ac0a778a918c05c066`, then select the next acceptance-testing issue.

## Explicit defers
- `tj-b4n` / GitHub #24 remains provider-blocked pending official Wazzup typing endpoint.
- FU1/FU2/FU3 production follow-up matrix still needs explicit FU1 EN/AR text and approved Wazzup WABA FU2/FU3 templates.
- Post-quotation pre-acceptance delivery-question answer quality remains a future follow-up candidate.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
