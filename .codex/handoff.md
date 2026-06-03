# Orchestrator Handoff
Updated: 2026-06-03
Current branch: `codex/tj-gh48-e2e-service-interruption-fix`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `tj-gh48.8` service-interruption hotfix is deployed at runtime commit
  `3d91e54a8de36fa379ac6e2ec1bfcf778cace11e`; Actions run `26841843489`
  and production smoke passed (`8 passed, 0 failed`).
- Production remains `dialogue_kernel_mode=shadow`; do not enable enforce without
  explicit approval and production evidence.
- Post-deploy live E2E on synthetic profile
  `+79262810921#tj-gh48-eaf-20260603055821` verified the delivery/assembly
  interruption now returns `z-ai/glm-5|service-availability` with no escalation.
- Same E2E verified kernel shadow trace fulfills the stored product-preference
  frame (`workspace_preference=open`), but customer-visible legacy response is
  still generic because enforce is not enabled.
- Synthetic conversation `ec3c9c10-4677-4a0b-9a7b-d0e8e51c5fef` was closed;
  no synthetic escalation existed; real base phone conversation was not mutated.
- Stage evidence is in `.codex/stages/tj-gh48/summary.md` and
  `.codex/stages/tj-gh48/artifacts/`.
- Beads `.2`-`.6` and `.8` are closed; `tj-gh48.7` deferred for enforce
  rollout.
## Next recommended
Next stage id: `tj-gh48`.
Recommended action: decide whether to enable narrow `product_selection` enforce
after reviewing shadow evidence; do not enable globally.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue `tj-gh48` from
`/home/me/code/treejar/.worktrees/tj-gh48-impl`; read repo contracts, summary,
and artifacts. Current branch is `codex/tj-gh48-e2e-service-interruption-fix`.
Do not deploy, push, enable enforce, or close #11 without explicit approval.

## Explicit defers
- Beads `tj-gh48.7`: enforce rollout remains deferred pending production
  evidence.
- GitHub #11 remains open and blocked on policy answers.
