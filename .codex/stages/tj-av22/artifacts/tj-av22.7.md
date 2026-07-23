---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: correction-reviewer
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: independent disposition of the seven tj-av22.5 findings on 3cf59b5
non_goals:
  - product-code changes
  - test or documentation changes
  - Beads mutation
  - production or external-service contact
evidence:
  - none
task_id: tj-av22.7
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-correction-review
milestone: noor-stabilization-correction-review
milestone_status: replan-required
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk security reliability concurrency and privacy correction review
repo: treejar
branch: codex/tj-av22-correction-review
base_branch: codex/tj-av22-stabilization
base_commit: 3cf59b540f206102341ba16f4d11401a27d18b85
worktree: /home/me/code/treejar/.worktrees/tj-av22-correction-review
write_zone:
  - .codex/stages/tj-av22/artifacts/tj-av22.7.md
success_criteria:
  - every prior finding has a current evidence-backed disposition and focused test
  - changed reliability privacy operations and cooldown surfaces are reviewed
  - local proof is separated from approval-gated production proof
  - no implementation runtime or external state is changed
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-av22/artifacts/tj-av22.5.md
  - .codex/stages/tj-av22/prompts/tj-av22.7-correction-review.md
selected_skills:
  - code-review
  - verification-before-completion
  - format-commit-message
selected_agents:
  - independent-stabilization-reviewer
catalog_candidates:
  - none
parallel_group: final-stabilization-review
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: isolated review worktree retained for root inspection
risk_level: high
verification_tier: integration
risk_tags:
  - security
  - concurrency
  - retry
  - state-transition
  - idempotency
  - rollback
  - data
affected_surfaces:
  - backend
  - database
  - data
  - api
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: n/a
docs_review_notes: review-only stream; the overstated inbound recovery claim is captured below for root correction
verification:
  - focused correction matrix - 27 passed: passed
  - affected-surface pytest matrix - 116 passed: passed
  - voice and signal privacy matrix - 2 passed: passed
  - worker cancellation read-only probe - zero requeue and zero quarantine writes: passed
  - repeated quarantine TTL read-only probe - 604800 second TTL renewed: passed
  - ruff check src tests and escalation guard: passed
  - ruff format check src tests and escalation guard: passed
  - mypy no-incremental src - 162 source files: passed
  - git diff check from ee7a250: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.7.md
explicit_defers:
  - tj-av22.6 - crash-safe inbound lease and replay idempotency remain release-blocking
  - tj-av22.3 - deployment production readback real OAuth replay cron heartbeat Telegram and synthetic E2E proof remain approval-gated
---

# Summary

Six of the seven findings from `tj-av22.5` are resolved on
`codex/tj-av22-stabilization@3cf59b5`. The inbound preservation finding remains
open: ordinary caught exceptions are now requeued or quarantined, but the worker
still removes the only Redis copy before acquiring a durable processing lease.
A worker cancellation or process loss can therefore still discard an accepted
payload, and replay after a late failure can repeat LLM or tool side effects.

No separate new P0/P1 finding was identified in the other corrected surfaces.
The local release verdict is **NEEDS WORK** until the open P1 is corrected and
re-reviewed. Approval-gated production proof remains a separate release
requirement and was not attempted.

# Coverage

The review compared the integrated snapshot from
`main@89f9a560071302d16f53704870e7a508e9d05f28`, inspected correction history
after the prior review base `ee7a250`, and read the current implementations and
tests for inbound batching, OAuth refresh locks, escalation reconciliation,
privacy-safe logging, maintenance heartbeat topology, quarantine retention, and
Telegram cooldown delivery. Beads `tj-av22.5`, `tj-av22.6`, and `tj-av22.7`
were read in `--readonly` mode.

# Prior-Finding Disposition

## 1. OPEN P1 — inbound recovery is not crash-safe or replay-safe

- **Current evidence:** `src/services/chat.py:621-627` drains the live list with
  destructive `LPOP` calls and holds the payload only in process memory.
  Recovery begins only inside `except Exception` at
  `src/services/chat.py:636-700`. `asyncio.CancelledError` and hard worker loss
  bypass that recovery boundary. A fresh read-only cancellation probe observed
  `requeue_calls=0` and `quarantine_calls=0`.
- **Replay evidence:** a caught late exception is requeued at
  `src/services/chat.py:659-675`, including failures after inbound persistence
  commits at `src/services/chat.py:1079-1141` or assistant persistence at
  `src/services/chat.py:1266-1280`. On replay, existing inbound IDs are skipped,
  but there is no completed-batch guard before `process_message` is invoked
  again at `src/services/chat.py:1193-1225`. The focused test at
  `tests/test_services_chat_batch.py:286-300` proves only a stable outbound
  `crm_message_id`; it does not prevent repeated LLM, CRM, inventory, or
  assistant-row side effects.
- **Positive coverage:** focused tests confirm bounded requeue for ordinary
  OAuth and generic exceptions, TTL quarantine for terminal/exhausted errors,
  and queue restoration when the quarantine write raises. Those cases passed,
  but they do not cover worker loss between `LPOP` and outcome persistence.
- **Impact:** an accepted customer message can still disappear during worker
  cancellation/restart, while a late catchable failure can repeat non-idempotent
  work. This leaves acceptance criterion AC-2 and Beads `tj-av22.6` incomplete.
- **Required correction:** atomically move messages into a durable processing
  list or immutable batch envelope before processing, acknowledge only after a
  committed terminal outcome, reclaim abandoned leases, and persist/check a
  completed-batch idempotency marker before invoking LLM or provider tools.
  Add cancellation/crash-recovery and late-failure replay regressions.

## 2. RESOLVED — stale OAuth owner cannot release a replacement lock

CRM and Inventory now acquire unique owner tokens at
`src/integrations/crm/zoho_crm.py:86-99` and
`src/integrations/inventory/zoho_inventory.py:255-269`. Both release through the
atomic compare-and-delete helper at `src/integrations/zoho_oauth.py:158-171`.
Lock exhaustion is a typed retryable `ZohoOAuthError` at
`src/integrations/crm/zoho_crm.py:101-109` and
`src/integrations/inventory/zoho_inventory.py:271-279`.
`test_expired_lock_owner_cannot_release_new_owner_lock`, both timeout tests, and
the timeout-versus-TTL test passed.

## 3. RESOLVED — reconciliation apply re-runs the canonical classifier

After exact IDs are locked and state preconditions pass,
`scripts/escalation_guard.py:317-331` classifies the current database pair using
the manifest threshold and current time and rejects every action not currently
safe to resolve. The fabricated active/pending human-owned action regression at
`tests/test_scripts_escalation_guard.py:259-300` and the idempotent apply test
passed. Fabricated record/action presentation can no longer bypass the actual
state-transition policy.

## 4. RESOLVED — inbound operational logs no longer expose customer payloads

The webhook logs counts and message types rather than raw bodies at
`src/api/v1/webhook.py:92-101` and `src/api/v1/webhook.py:158-185`. Worker logs
use keyed batch references and metadata; the voice path logs neither media URLs
nor transcription text at `src/services/chat.py:843-918`. Webhook payload,
generic-failure, and voice transcription capture tests passed and explicitly
exclude chat ID, customer text, author name, media URL, and transcription.

## 5. RESOLVED — the worker can observe the host maintenance heartbeat

The worker receives `./logs/maintenance` read-only at
`docker-compose.yml:24-30`. Deployment preserves `logs` and creates the mounted
directory at `scripts/vps-deploy.sh:40-55` and
`scripts/vps-deploy.sh:155-167`. The Compose topology test and deployment
preservation test passed. Actual host cron installation and post-deploy
heartbeat readback remain approval-gated production proof.

## 6. RESOLVED — quarantine payloads have bounded retention

`src/services/chat.py:208-234` stores one idempotent JSON document with
`SET NX EX` and renews the configured TTL for an existing key.
`src/core/config.py:103-110` bounds the setting to at least 60 seconds and
defaults to seven days. Terminal/exhausted and quarantine-failure tests passed;
a focused repeated-write probe confirmed renewal to `604800` seconds.

## 7. RESOLVED — failed Telegram delivery does not consume cooldown

The notification wrapper returns confirmed delivery state at
`src/services/notifications.py:618-635`. Monitoring validates configuration
before claiming, uses a unique claim token, and atomically releases a failed
claim at `src/services/runtime_monitoring.py:210-243` and
`src/services/runtime_monitoring.py:450-470`. Deduplication, confirmed delivery,
missing configuration, no-op, exception, and failed-delivery release tests all
passed.

# New Findings by Severity

No independent new P0, P1, or P2 finding was found outside the still-open
inbound preservation and idempotency boundary above.

The runbook statement at `docs/operations-runbook.md:181-185` that a consumed
message does not silently disappear is stronger than the implementation. This
is part of the open P1 rather than a separate documentation-only finding:
durable recovery should be implemented first, then the runbook should describe
the proven lease/reclaim behavior exactly.

# Verification

- Focused correction matrix: `27 passed`.
- Affected-surface suite across nine test files: `116 passed`.
- Additional voice and runtime-signal privacy matrix: `2 passed`.
- Read-only cancellation probe: payload popped; zero requeue writes; zero
  quarantine writes.
- Read-only repeated-quarantine probe: existing key expiry renewed to the
  configured `604800` seconds.
- Ruff check: passed.
- Ruff format check: passed (`301 files already formatted`).
- Mypy: passed (`162 source files`).
- `git diff --check ee7a250..HEAD`: passed.

These are local proofs only. No deployment, production Redis/database read,
OAuth credential use, live webhook traffic, cron installation, Telegram send,
WhatsApp send, or external API call was made.

# Release Verdict

**NEEDS WORK / DO NOT RELEASE.** The six resolved findings can remain accepted,
but the root orchestrator should keep `tj-av22.6` and stage acceptance open
until durable inbound leasing plus replay idempotency are implemented and an
independent focused re-review passes.

After that correction, release still requires the separately approval-gated
`tj-av22.3` evidence: deployed SHA/version readback, production debug-route
absence, Redis and database health, real bounded OAuth replay, escalation
dry-run/manager disposition, cron and heartbeat readback, optional Telegram
delivery, WhatsApp/synthetic E2E, and rollback evidence.

# Significant Finding Capture

The significant open P1 is already within Beads `tj-av22.6`; the strict
read-only/write-zone contract prohibited changing task state or creating a new
Bead. The root orchestrator should update that task with the crash-safe lease
and replay-idempotency acceptance proof before correction work resumes.

# Risks / Follow-ups

- Implement and test durable inbound lease/ack/reclaim semantics.
- Add a completed-batch guard covering LLM and provider-tool side effects, not
  only outbound `crm_message_id` stability.
- Correct the runbook recovery claim together with the implementation.
- Preserve all production and external-service checks as explicit approval
  gates.

# Delivery / Cleanup

This review artifact is returned on `codex/tj-av22-correction-review` for root
triage. It does not accept or merge the integration snapshot. The dedicated
worktree remains available for orchestrator inspection and safe cleanup.
