# Orchestrator Handoff
Updated: 2026-06-02
Current branch: `codex/tj-gh48-expected-answer-frames-impl`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `tj-gh48` is local-only: no deploy, prod mutation/config change, live
  WhatsApp E2E, push, PR, merge to `main`, or #11 close was performed.
- Production remains `dialogue_kernel_mode=shadow` unless a later approved
  rollout enables a narrow enforce flow.
- Implementation branch is based on fresh `origin/main` commit `428deed`.
- Implemented expected-answer frame schema/reducers, matcher, runner graph,
  engine capture/bridge, replay fixtures, and review fixes.
- Engine captures frames for product preference, SKU quantity, quote details,
  post-quote approval, and name gate prompts.
- Product-preference frame routing is customer-visible only for usable
  `enforce` + allowlisted `product_selection`; `shadow` and unallowlisted
  `enforce` stay telemetry-only.
- Reviewer fixes covered shadow gating, plural blockers, ordinal source refs,
  required-slot fulfillment, typed payload extraction, broader frame capture,
  and docs drift.
- Stage evidence is in `.codex/stages/tj-gh48/summary.md` and artifacts.
- Beads `.2`-`.6` are closed; `tj-gh48.7` is deferred for rollout/prod E2E.

## Next recommended
Next stage id: `tj-gh48`.
Recommended action: delivery/rollout only with explicit approval: merge, push,
deploy, prod/live E2E, or enforce rollout.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue `tj-gh48` from
`/home/me/code/treejar/.worktrees/tj-gh48-impl`; read `AGENTS.md`,
`.codex/orchestrator.toml`, `.codex/handoff.md`, stage summary, and artifacts.
Do not deploy, mutate prod, run live WhatsApp E2E, push, PR, enable enforce, or
close #11 without explicit approval.

## Explicit defers
- Beads `tj-gh48.7`: prod deploy/smoke, prod shadow E2E, live WhatsApp E2E,
  and enforce rollout are deferred pending approval.
- GitHub #11 remains open and blocked on policy answers.
