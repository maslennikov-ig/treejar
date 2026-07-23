# Orchestrator Handoff
Updated: 2026-07-23
Current branch: `codex/tj-av22-stabilization`
Current stage id: `tj-av22`

## Current Truth
- Active stabilization epic: `tj-av22`.
- Planning task `tj-g6m4` produced the approved technical design, implementation
  plan, Beads hierarchy, and root-orchestrator prompt.
- Design:
  `docs/superpowers/specs/2026-07-23-noor-stabilization-design.md`.
- Plan:
  `docs/superpowers/plans/2026-07-23-noor-stabilization.md`.
- Prompt:
  `docs/prompts/2026-07-23-noor-stabilization-orchestrator.md`.
- P1 scope: public Redis debug exposure (`tj-9c94`), Zoho OAuth/inbound batch
  reliability (`tj-p9ui`), pending escalation reconciliation (`tj-ymi3`),
  failure visibility (`tj-av22.1`), and latency (`tj-15m`).
- P2 scope: Docker maintenance (`tj-092y`), truthful health (`tj-38l5`),
  incomplete public `501` contracts (`tj-av22.2`), and local orchestration
  residue (`tj-rt42`).
- Integration/release/closeout `tj-av22.3` depends on all implementation and
  cleanup children.
- On 2026-07-23 the user explicitly authorized visible spawned subagents for
  this epic. The orchestrator chooses the useful number, scope, and timing of
  agents. The plan contains advisory candidate streams rather than a prescribed
  wave schedule.
- Canonical runtime remains `https://noor.starec.ai`.
- Graphify is not configured; `graphify-out/GRAPH_REPORT.md` is absent.

## Audit Baseline
- Local canonical gates were green at audit time: Ruff, format, Mypy, and full
  pytest (`1431 passed, 19 skipped`).
- Production was generally available, but the audit found a public raw-Redis
  debug route, one Zoho OAuth-shaped incoming-batch loss, 33 pending escalation
  rows, a non-running maintenance cron, incomplete health, weak failure
  visibility, historical 17–42 second latency, and three public `501` routes.

## Next recommended
Next stage id: `tj-av22`.
Recommended action: execute the checked-in orchestrator prompt. Start with local
triage, then choose delegation and sequencing from current evidence. Do not
deploy or mutate production until the explicit approval gate.

## Starter prompt for next orchestrator
Use $orchestrator-stage and the prompt at
`docs/prompts/2026-07-23-noor-stabilization-orchestrator.md`.

## Approval gates
- Ask before deploy/staging or production mutation.
- Ask before applying escalation reconciliation or sending real Telegram/
  WhatsApp tests.
- Ask before deleting worktrees/branches/caches or changing credentials/scopes.
- Preserve existing untracked user files.

## Explicit defers
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
