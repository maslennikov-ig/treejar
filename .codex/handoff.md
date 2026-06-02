# Orchestrator Handoff
Updated: 2026-06-02
Current branch: `codex/tj-gh48-expected-answer-frames-impl`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- No deploy, production mutation, production config change, live WhatsApp E2E,
  remote push, PR creation, or merge to `main` was performed in `tj-gh48`.
- Production should remain `dialogue_kernel_mode=shadow` unless a later
  explicitly approved rollout enables a narrow enforce flow.
- Stage `tj-gh48` implementation is local on
  `codex/tj-gh48-expected-answer-frames-impl`, based on fresh `origin/main`
  commit `428deed`.
- Implemented expected-answer frame schema/reducers, deterministic matcher,
  runner graph, engine capture/bridge, replay fixtures, and review fixes.
- Engine now captures frames for product preference, SKU quantity, quote
  details, post-quote approval, and name gate prompts.
- Product-preference frame routing is customer-visible only when the kernel is
  usable in `enforce` mode with an allowlisted `product_selection` flow.
  `shadow` and unallowlisted `enforce` remain telemetry-only.
- Independent review findings were processed: shadow/unallowlisted routing,
  plural blockers, ordinal source refs, required-slot fulfillment, typed payload
  extraction, broader frame capture, and docs drift were fixed.
- Delegated matcher and runner worktrees were merged into the implementation
  branch and removed after clean status.
- Local evidence is in `.codex/stages/tj-gh48/summary.md` and
  `.codex/stages/tj-gh48/artifacts/`.
- Latest full local suite after frontend dependency repair:
  `1207 passed, 19 skipped`.

## Next recommended
Next stage id: `tj-gh48`.
Recommended action: finish local stage closeout on
`codex/tj-gh48-expected-answer-frames-impl`; if approved later, merge/push using
the repo delivery policy. Production deploy, smoke, shadow E2E, live WhatsApp
E2E, and enforce rollout all require explicit current-task approval.

## Starter prompt for next orchestrator
Use `$orchestrator-stage`. Continue `tj-gh48` from
`/home/me/code/treejar/.worktrees/tj-gh48-impl` on branch
`codex/tj-gh48-expected-answer-frames-impl`. Read `AGENTS.md`,
`.codex/orchestrator.toml`, `.codex/handoff.md`,
`.codex/stages/tj-gh48/summary.md`, and the tj-gh48 artifacts. Do not deploy,
mutate production, run live WhatsApp E2E, enable enforce, push, create a PR, or
close #11 without explicit approval.

## Explicit defers
- Beads `tj-gh48.7`: production deploy/smoke, production shadow E2E, live
  WhatsApp E2E, and any enforce rollout are deferred pending explicit approval.
- GitHub #11 remains open and blocked on policy answers; do not close it from
  `tj-gh48` evidence alone.
