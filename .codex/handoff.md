# Orchestrator Handoff
Updated: 2026-07-23
Current branch: `main`
Current stage id: `tj-rt42`
Current stage status: accepted and closed

## Current Truth
- Stabilization epic `tj-av22` and release task `tj-av22.3` are accepted and
  closed. Their technical release boundary is complete; separately
  approval-gated operational follow-ups remain active.
- Integration branch `codex/tj-av22-stabilization` was fast-forwarded into
  `main`.
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
  (`1513 passed, 19 skipped`).
- `main` was pushed and GitHub Actions run `30028216974` passed lint,
  type-check, tests, and deployment. Production activated exact release
  `2213a06800a156f6d511af26072ea17f16178ef2`; a predecessor rollback backup was
  created.
- Production health returns `200`, version `0.4.0`, Redis `ok`, and database
  `ok`. `/api/v1/debug/redis` and the retired SaleOrder read route return
  `404`; anonymous conversations access returns `403`; production OpenAPI omits
  the debug, SaleOrder create/read, and legacy quality-report routes.
- Real external-message tests, escalation apply, maintenance cron
  installation/apply, live latency proof, rollback exercise, and destructive
  cleanup were not performed because they remain separately approval-gated.
- Cleanup stage `tj-rt42` removed all 20 stale task worktrees, all 29 local
  integrated or patch-equivalent task branches, and about 377 MB of rebuildable
  Python caches after preserving exact evidence. Only `main` remains locally;
  remote branches, `.venv`, completion history, and all protected user files
  were preserved and verified.
- On 2026-07-23 the user explicitly authorized visible spawned subagents for
  this epic. Delegation remains adaptive: the orchestrator chooses the working
  shape from current evidence. The plan's candidate streams are guidance, not a
  prescribed schedule.
- Canonical runtime remains `https://noor.starec.ai`.
- Graphify is not configured; `graphify-out/GRAPH_REPORT.md` is absent.
- On 2026-07-23 the user explicitly authorized all previously gated production
  operations, live synthetic message/latency proof, and destructive cleanup.
  Stage `tj-5o9r` completed the production operations under exact snapshot and
  restore boundaries.
- The approved `tj-15m` live matrix stopped after one FAQ canary. Both Zoho CRM
  and Inventory refresh calls return `invalid_code` with no access token; no
  assistant message was produced, the batch was safely quarantined, no pending
  escalation remains, and health is green. `tj-15m.7` requires interactive
  Zoho owner consent and new protected refresh tokens before the matrix can
  resume.

## Audit Baseline
- Local canonical gates were green at audit time: Ruff, format, Mypy, and full
  pytest (`1431 passed, 19 skipped`).
- Production was generally available, but the audit found a public raw-Redis
  debug route, one Zoho OAuth-shaped incoming-batch loss, 33 pending escalation
  rows, a non-running maintenance cron, incomplete health, weak failure
  visibility, historical 17–42 second latency, and three public `501` routes.

## Next recommended
Next stage id: not opened.
Recommended action: obtain interactive Zoho owner consent, renew both CRM and
Inventory refresh tokens under `tj-15m.7`, then resume the exact live latency
matrix from scenario two.

## Starter prompt for next orchestrator
Use $orchestrator-stage to resume `tj-15m` only after `tj-15m.7` has both new
Zoho refresh tokens installed through the protected configuration path. Treat
`tj-av22`, `tj-5o9r`, and `tj-rt42` as accepted history.

## Approval gates
- The user explicitly approved escalation reconciliation, maintenance cron and
  first apply, one Telegram alert, controlled rollback/restore, live synthetic
  WhatsApp traffic, and safe destructive cleanup on 2026-07-23.
- Preserve existing unrelated user files and do not change credentials/scopes.

## Explicit defers
- `tj-15m`: blocked after one authorized canary; resume after `tj-15m.7`.
- `tj-15m.7`: blocked on interactive Zoho owner consent and new CRM/Inventory
  refresh tokens.
- `tj-5o9r`: accepted and closed.
- `tj-rt42`: accepted and closed.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
