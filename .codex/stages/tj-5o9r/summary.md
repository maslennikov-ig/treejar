# Stage tj-5o9r Summary

Updated: 2026-07-23
Status: accepted and closed
Branch: `main`
Beads: `tj-5o9r`

## Cohesive Boundary

This stage validates four already-implemented production operation paths
against one canonical Noor runtime: exact-ID escalation reconciliation,
conservative Docker maintenance, privacy-safe Telegram alert delivery, and
artifact rollback/restore. The current release and the pre-operation snapshots
are the shared rollback boundary.

## Exact Authorized Scope

- User approval: 2026-07-23, explicit authorization for all previously gated
  actions.
- Escalations: archive a fresh read-only manifest, apply only its exact safe
  IDs, then audit and repeat the same apply for idempotency.
- Maintenance: archive the current crontab, install the conservative managed
  entry, run one conservative apply, then verify heartbeat, storage, cron, and
  health.
- Alert: send exactly one fixed privacy-safe verification message to the
  existing configured Telegram destination; do not expose the destination or
  credentials in evidence.
- Deployment: archive the current release, activate the recorded predecessor
  backup, verify health/release, restore the archived current release, and
  verify the exact original release and health.

## Rollback

- Escalation apply is transactionally all-or-nothing. A committed exact-ID
  resolution has no automatic inverse and therefore stops on any manifest
  mismatch.
- Cron rollback restores the archived crontab. Docker prune is conservative,
  never touches volumes or running resources, and is not reversible.
- Telegram delivery has no state rollback; the single message is explicitly
  synthetic and privacy-safe.
- Deployment rollback/restore uses `.hotfix-backups` through
  `scripts/vps-deploy.sh`; the stage is incomplete until the original release
  SHA is restored and healthy.

## Parallel Decomposition Matrix

| Stream | Shared state | Decision | Reason |
| --- | --- | --- | --- |
| Production operations (`tj-5o9r`) | Canonical VPS/runtime | sequential, root-owned | Exact snapshots and one rollback owner are required |
| Live latency/messages (`tj-15m`) | Wazzup, DB, Telegram | next stage | Must start only after production returns to a stable release |
| Repository cleanup (`tj-rt42`) | Git common dir/worktrees | final stage | Evidence must be committed before destructive cleanup |

## Routing

- Skills: `orchestrator-stage`, `task-router`, `senior-devops`,
  `writing-plans`, `verification-before-completion`,
  `orchestration-closeout`.
- Documentation: repository runbooks and deployed scripts are authoritative;
  no version-sensitive dependency behavior is being changed.
- Delegation: no subagent launched because all candidate streams mutate shared
  production or shared Git state; parallel execution would weaken snapshot and
  rollback ownership.
- Graphify: not configured; no graph refresh is planned for operational
  execution evidence.

## Evidence

- Baseline: release
  `2213a06800a156f6d511af26072ea17f16178ef2`, workflow
  `30028216974`, 5 running compose services, HTTP `200`, version `0.4.0`,
  Redis `ok`, database `ok`, no managed maintenance cron, and configured
  Telegram credentials/destination.
- Escalation reconciliation:
  - protected manifest SHA-256
    `42feb34fa82da9dad84e548e8d39ec559b21d728f436e592beb8b60f6644a7f7`;
  - `33` initial pending, `9` exact safe actions, `24` human-review records;
  - `9` changed transactionally, post-audit `24` pending and `0` safe actions;
  - repeated exact apply changed `0` and read back all `9` as already applied;
  - health remained green.
- Maintenance:
  - pre-install crontab SHA-256
    `659448f7547b03ba1763e81371516ba12e6b505992ccbfbdeb9d3338e9de8144`;
  - exactly one begin marker, one entry, and one end marker installed;
  - conservative first apply succeeded, released about 60 MB, wrote a success
    heartbeat, and preserved health.
- Telegram:
  - the first verification invocation sent no message and exposed a local
    property/call defect before the network call;
  - focused regression failed on the old code, the one-line correction passed
    with the runtime-monitoring slice (`14 passed`), and CI run `30031569448`
    passed lint, Mypy, and the full test job;
  - exactly one privacy-safe verification message was then delivered:
    `6 passed`, `0 failed`; destination and credentials remain only in the
    protected VPS log.
- Rollback/restore:
  - predecessor archive SHA-256
    `44440d05d2b994ebece3d7421bcade7136ecb2ef2db5f3929eb33f90581114e0`
    validated as release `6df39c72...`;
  - predecessor activated healthy; current-release backup SHA-256
    `944f2bebc4d920b7cb9372bdfd92eb45ce328fac62938b28624df2089f0ce02d`
    validated as `2213a068...`;
  - the initial restore shell failed before deploy because its log path was
    inside the replaced `ops/` tree; immediate restore from the intact current
    archive succeeded with 5 running services and exact original SHA;
  - the predecessor deploy implementation recreated the maintenance bind path
    as root, so the first heartbeat recovery cleanup completed but could not
    write its final status. Ownership was repaired exactly for
    `logs/maintenance`; a verified conservative rerun wrote `success` and
    health remained green.
- Corrections from the drill:
  - `scripts/vps-deploy.sh` now preserves production `ops/` audit state;
  - the deployment test failed before that correction and the affected
    deploy/maintenance/Telegram/monitoring slice passed afterward (`23 passed`);
  - runbooks now require one immutable `/tmp` copy of the current deploy
    operator for both rollback directions and post-restore verification of
    release, services, health, cron, and heartbeat;
  - correction commit: `aa0411d`.
- Final delivery:
  - GitHub Actions run `30032190269` passed lint, Mypy, the full test job, and
    deployment;
  - production activated exact release
    `aa0411db16fc4c128e154052729fdc2a24b7f2c6`;
  - post-deploy readback found 5 running services, HTTP `200`, Redis/database
    `ok`, cron markers `1:1:1`, maintenance heartbeat `success`, preserved
    protected operational evidence, and correct runtime directory ownership.
- Canonical stage closeout:
  - integration group: `132 passed`;
  - concurrency group: `96 passed`;
  - PostgreSQL group: `13 passed`;
  - artifact validation, stage sizing/readiness, process verification,
    blocking-finding reconciliation, documentation/project-index/debt checks,
    and non-dry-run integration closeout passed;
  - the closeout inbox now filters shared historical events by exact stage
    before validating identity; the regression and full process suite pass
    (`10 passed`).

## Closeout

- `docs-reviewed: updated` — operations and administrator runbooks now record
  the exercised rollback/restore invariants and operational-state ownership.
- `project-index: reviewed-no-change` — no stable entrypoint or ownership
  location changed; the existing deploy, escalation, maintenance, and alert
  entries remain correct.
- `graph-reviewed: no-change-needed` — Graphify is not configured and the
  changes are operational scripts/tests/docs rather than an architecture graph
  boundary.
