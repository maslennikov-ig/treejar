# Orchestrator Handoff
Updated: 2026-05-26
Current branch: `codex/fr3309-brief-details`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- Production release still needs fresh readback before deploy; last known deployed release: `6d91fde34f85936bb018d9ac0a778a918c05c066`, GitHub Actions run `26404203850`, smoke `7 passed, 0 failed`.
- Stage `tj-mmj8` is local-only: Fr3309 unordered brief parsing is implemented and locally verified on branch `codex/fr3309-brief-details`; it is not deployed or live-tested.
- Beads `tj-mmj8` is in progress and tracks Fr3309: preserve `Lilia`, `LLD`, `Lfdsf@kfsl.ru`, `2 street` from ordered brief replies.
- Local verification passed after `frontend/admin npm ci`: Fr3309 targeted tests `6 passed`, `tests/test_llm_engine.py` `216 passed`, ruff, format check, mypy, and full pytest `1149 passed, 16 skipped`.
- First full pytest attempt failed only because the isolated worktree lacked `frontend/admin` `esbuild`; after `npm ci`, it passed.
- No GitHub issue mutation, production deploy, production smoke, or live WhatsApp send was performed for `tj-mmj8`.
- Stage `tj-m7wz` remains the last delivered/deployed quotation-context release; its live E2E created `Fr3307`.
- `tj-gh20` remains production `shadow` only: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended
Next stage id: `tj-mmj8-delivery`.
Recommended action: after explicit owner authorization, merge/deploy `codex/fr3309-brief-details`, run production smoke, then replay the Fr3309 pattern on an approved controlled number; do not send WhatsApp messages to Lidia’s number without explicit approval.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue `tj-mmj8`: verify branch `codex/fr3309-brief-details`, confirm production runtime drift, then request/confirm authorization before deploy and live E2E.

## Explicit defers
- Beads `tj-mmj8`: deploy, production smoke, and live Fr3309 replay are pending explicit owner authorization.
- `tj-b4n` / GitHub #24 remains provider-blocked pending official Wazzup typing endpoint.
- FU1/FU2/FU3 production follow-up matrix still needs explicit FU1 EN/AR text and approved Wazzup WABA FU2/FU3 templates.
- Post-quotation pre-acceptance delivery-question answer quality remains a future follow-up candidate.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
