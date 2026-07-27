# Orchestrator Handoff
Updated: 2026-07-27
Current branch: `main`
Current stage id: `tj-15m`
Current stage status: in progress; Wazzup restored, full matrix pending

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
- On 2026-07-24 Viktor supplied fresh EU Zoho Self Client grants. CRM and
  Inventory refresh tokens were rotated through the protected production path;
  both direct and app-native read-only probes pass, and later deploys preserved
  the credentials.
- The resumed `tj-15m` matrix found and fixed three bounded defects: quantity
  loss in `N units of SKU`, explicit no-quotation requests entering quote
  routing, and an English first-turn name gate for Arabic input. Releases
  `e4959e0`, `3ebb69c`, and `cee1f7d` are deployed.
- GitHub Actions run `30098682854` passed lint, type-check, tests, and deploy.
  Local release gates pass with `1528 passed, 19 skipped`. Production health is
  green on exact release `cee1f7d4ba05eba5107d38bd5388c2b5b4622d55`.
- On 2026-07-27 the exact configured Wazzup WhatsApp channel reported `active`.
  One approved synthetic canary completed in `6.797s`: one user message, one
  assistant message, one text outbound audit with status `sent`, a provider
  message ID, no outbound error, and no escalation. Task `tj-15m.10` is
  accepted; this single sample is not a p50/p95/max distribution.

## Audit Baseline
- Local canonical gates were green at audit time: Ruff, format, Mypy, and full
  pytest (`1431 passed, 19 skipped`).
- Production was generally available, but the audit found a public raw-Redis
  debug route, one Zoho OAuth-shaped incoming-batch loss, 33 pending escalation
  rows, a non-running maintenance cron, incomplete health, weak failure
  visibility, historical 17–42 second latency, and three public `501` routes.

## Next recommended
Next stage id: `tj-15m` remains active.
Recommended action: run the post-fix Arabic scenario, the
escalation-and-cleanup scenario, and the complete delivery-aware matrix under
`tj-15m.7`; then compute customer-visible p50/p95/max and close the stage if all
correctness and cleanup gates pass.

## Starter prompt for next orchestrator
Use $orchestrator-stage to continue `tj-15m.7`. Treat the Zoho rotation,
releases through `cee1f7d`, Wazzup `active` readback, and the accepted
`6.797s` delivery canary as verified history. Run the remaining post-fix Arabic
and escalation/cleanup scenarios plus the complete delivery-aware latency
matrix, preserving the existing recipient, suffix, stop, and privacy
boundaries.

## Approval gates
- The user explicitly approved escalation reconciliation, maintenance cron and
  first apply, one Telegram alert, controlled rollback/restore, live synthetic
  WhatsApp traffic, and safe destructive cleanup on 2026-07-23.
- Preserve existing unrelated user files and do not change credentials/scopes.

## Explicit defers
- `tj-15m`: in progress; the complete delivery-aware matrix remains.
- `tj-15m.7`: in progress; credential rotation and Wazzup delivery canary pass,
  while Arabic, escalation/cleanup, and final latency distribution remain.
- `tj-15m.10`: accepted and closed after active-channel readback and one
  successful audited synthetic text send.
- `tj-5o9r`: accepted and closed.
- `tj-rt42`: accepted and closed.
- Referral launch `tj-final27.6`, WABA approval `tj-gh21`, catalog GH #54
  `tj-2pkk`, new soft/hard escalation policy `tj-g3f`, delivery-source policy
  `tj-9q0`, and Zoho UTM mapping `tj-hye` remain separate external gates.
