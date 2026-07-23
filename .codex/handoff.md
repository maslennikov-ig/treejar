# Orchestrator Handoff
Updated: 2026-07-23
Current branch: `codex/tj-av22-stabilization`
Current stage id: `tj-av22`

## Current Truth
- Active stabilization epic: `tj-av22`.
- Integration branch: `codex/tj-av22-stabilization`.
- Planning task `tj-g6m4` produced the technical design, implementation plan,
  Beads hierarchy, and root-orchestrator prompt.
- Design:
  `docs/superpowers/specs/2026-07-23-noor-stabilization-design.md`.
- Plan:
  `docs/superpowers/plans/2026-07-23-noor-stabilization.md`.
- Prompt:
  `docs/prompts/2026-07-23-noor-stabilization-orchestrator.md`.
- Implemented locally: public Redis debug removal, truthful Redis/DB health,
  owner-safe Zoho refresh locks, bounded OAuth retry/quarantine, exact-ID
  escalation reconciliation, conservative Docker maintenance and heartbeat,
  privacy-safe runtime monitoring, delivery-aware Telegram cooldown, latency
  phase evidence and summary-after-text ordering, and deliberate retirement of
  the never-functional public `501` routes.
- Inbound processing now uses an immutable durable Redis processing list, an
  owner-token lease longer than the ARQ job timeout, and a started/completed
  execution guard. Active guards do not expire while a durable copy exists;
  terminal processing-list deletion and guard TTL are one atomic Redis
  transition. Cancellation keeps the raw batch recoverable; completed work is
  not replayed; uncertain post-side-effect recovery is quarantined.
- Runtime monitoring now includes payload-free depth and idle age for orphaned
  `wazzup_msgs:*` and `wazzup:inbound:processing:*` lists even without an ARQ
  job.
- Durable release, health, Zoho recovery, latency, and inbound runbook
  documentation is aligned with the implementation.
- Independent final review `tj-av22.9` passed after one correction round. The
  explicit combined review `tj-av22.10` then found one P1 and two P2 gaps; all
  were corrected and independently delta-reviewed. Its final verdict is
  `PASS / LOCALLY RELEASE-READY`, with active `P0/P1/P2/P3=0`.
  Process verification, Ruff, format, Mypy, and the full suite pass locally
  (`1513 passed, 19 skipped`). Release/closeout `tj-av22.3` remains blocked
  only at the production authorization boundary.
- Production deployment, readback, real external-message tests, escalation
  apply, cron installation, and live latency proof have not been performed.
- Fresh read-only production recheck still returns version `0.1.0`, Redis-only
  health, and HTTP `200` for `/api/v1/debug/redis` (body discarded). The latest
  `main@89f9a560` CI run `30002801189` failed only in four orchestration-runtime
  guard tests; the integration branch contains their root fixes and passes the
  expanded process-verification suite plus the full canonical gate.
- Cleanup audit `tj-rt42` found nine old worktrees with no commits unique from
  `main`, plus large local caches. Nothing was deleted because cleanup requires
  explicit approval.
- On 2026-07-23 the user explicitly authorized visible spawned subagents for
  this epic. Delegation remains adaptive: the orchestrator chooses the working
  shape from current evidence. The plan's candidate streams are guidance, not a
  prescribed schedule.
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
Recommended action: reconcile the remaining approval-gated Beads, then ask for
the exact merge/push, deployment, and production-readback approval. Do not
deploy or mutate production before that approval.

## Starter prompt for next orchestrator
Use $orchestrator-stage to continue `tj-av22` from the current integration
branch. Read the accepted `tj-av22.10` artifact and stop at the merge/push,
deployment, live-readback, and cleanup approval gates.

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
