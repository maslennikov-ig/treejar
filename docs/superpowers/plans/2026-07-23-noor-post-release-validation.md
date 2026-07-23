# Noor Post-Release Validation Plan

Date: 2026-07-23
Owner: root orchestrator
Runtime: `https://noor.starec.ai`

## Goal

Complete the three previously approval-gated follow-ups with fresh, bounded
evidence: production operational validation (`tj-5o9r`), live synthetic
latency/message proof (`tj-15m`), and safe repository cleanup (`tj-rt42`).

## Execution Order

### 1. Production operational validation (`tj-5o9r`)

1. Record active release, health, compose state, storage totals, crontab
   checksum, available deployment backups, and privacy-safe configuration
   presence.
2. Archive a fresh escalation audit with mode `0600`, validate its digest,
   apply only exact safe IDs, run a fresh audit, and repeat the original apply
   to prove idempotency.
3. Archive the current crontab, install the managed conservative maintenance
   entry, run one conservative apply, and verify marker count, heartbeat,
   aggregate storage, and health.
4. Run one real Telegram verification send while filtering destination IDs and
   secrets from captured evidence.
5. Create a current-release archive, restore the recorded predecessor through
   the deployment script, verify health and its release SHA, then restore the
   current-release archive and verify the original exact SHA and health.
6. Stop immediately if health degrades, an exact manifest no longer matches,
   the wrong alert destination would be used, or the original release cannot
   be restored.

### 2. Live latency and message proof (`tj-15m`)

1. Reconfirm healthy exact release and the repository-approved synthetic
   WhatsApp recipient/channel without printing secrets.
2. Use unique `tj-15m-<scenario>-<timestamp>` suffixes for FAQ, product,
   comparison, order, Arabic, and escalation scenarios.
3. Record customer-visible outcome, no-duplicate/no-pending readback, and
   per-scenario duration; calculate p50, p95, and maximum.
4. Stop on unsafe content, unsupported commercial claims, duplicate sends,
   unresolved escalation, or health failure.

### 3. Repository cleanup (`tj-rt42`)

1. Re-run the cleanup audit and inventory every worktree, branch, completion
   tail, and cache candidate.
2. Preserve unrelated user files and archive evidence for any dirty or
   non-equivalent candidate.
3. Delete only clean worktrees/branches with no unique unintegrated changes and
   disposable generated caches; leave any ambiguous item tracked as a bounded
   defer.

## Verification and Closeout

- After every production mutation, verify canonical health and the relevant
  exact readback.
- After each stage, update its manifest/summary, Beads, and current-state
  handoff; run process verification and the canonical stage closeout.
- Run a final combined delta review across production evidence, synthetic
  traffic cleanup, repository state, docs, and Graphify status.
- Push only tracked project evidence; never commit credentials, raw customer
  content, destination IDs, or unrelated user files.
