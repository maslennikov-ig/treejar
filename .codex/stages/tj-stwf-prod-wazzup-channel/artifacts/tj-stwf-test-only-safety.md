---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-stwf-prod-wazzup-channel/stage-manifest.json
stream_owner: test_only_egress_fix
orchestration_level: slice_acceptance
scope_kind: product_slice
bounded_acceptance: local-test-only-egress-and-status-repair-with-production-held
task_id: tj-stwf-test-only-safety
epic_id: tj-stwf
stage_id: tj-stwf-prod-wazzup-channel
agent_type: backend_developer
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production messaging and cross-channel authorization risk
repo: treejar
branch: codex/test-channel-safety
base_branch: main
base_commit: b3655501eb3ac71d2bb45086c7761a966784f403
worktree: /home/me/code/treejar/.worktrees/test-channel-safety
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: blocked
cleanup_notes: retained for safe restoration; live acceptance and delivery remain open
risk_level: high
verification_tier: delta
risk_tags:
  - authorization
  - concurrency
  - retry
  - data
affected_surfaces:
  - backend
  - database
  - user-flow
invariants:
  - tenancy
  - state-transition
  - rollback
docs_impact: behavior
docs_reviewed: updated
verification:
  - root affected correction set - 130 passed in 1.95s
  - root Ruff src and tests - passed
  - root format src and tests - 386 files passed
  - root Mypy src - 178 files passed
  - root git diff --check - passed
  - independent security re-review - no blocking findings after P1 correction
changed_files:
  - .env.example
  - src/core/config.py
  - src/integrations/messaging/wazzup.py
  - src/services/chat.py
  - src/services/outbound_audit.py
  - src/services/outbound_safety.py
  - tests/test_messaging_wazzup.py
  - tests/test_outbound_audit.py
  - tests/test_proposal_followup.py
  - tests/test_services_chat.py
  - tests/test_services_chat_batch.py
  - tests/test_services_followup_details.py
  - tests/test_webhook_manager.py
  - tests/test_wazzup_outbound_safety.py
explicit_defers:
  - tj-stwf - owner QR reconnection, controlled safe startup and fresh-message reply proof
---

# Summary

Local preparation is verified, but not deployed or accepted as live restoration.
Parent Bead `tj-stwf` remains open. Only test sender ending0665 is authorized.
Production app/worker remain stopped with restart policy `no`.

All audited WhatsApp sends require an explicit allowed sender, enabled bot and
matching conversation channel/recipient. Missing settings deny sending. The
transport rechecks before HTTP retries, media upload and caption sends. The
permission cannot be reused by another provider or inherited asyncio task.

Given an old foreign or unattributed conversation for a phone, when that phone
writes to the approved test channel, then a separate conversation is used.
The old ID, history and order remain unchanged and forbidden to later sends.
Status timestamps are normalized to aware UTC, including legacy naive values.

# Verification

Worker RED: 35 initial safety failures; 2 actual inbound-processing cases
reproduced old-conversation rebinding. Focused corrections made both green.
The initial root-selected 244-test set had 219 passed and 25 legacy-fixture
failures. Corrections use module-local collaborators in old routing unit tests;
the dedicated safety tests do not bypass authorization.

Root correction command:

```sh
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres /home/me/code/treejar/.venv/bin/python -m pytest tests/test_services_chat.py tests/test_services_chat_batch.py tests/test_services_followup_details.py tests/test_proposal_followup.py tests/test_webhook_manager.py tests/test_wazzup_outbound_safety.py -q --tb=short
```

Result: **130 passed in 1.95s**, no skips. Seven real local PostgreSQL cases use
random rollback-only schemas, including actual inbound and feedback handlers.
All HTTP is local; model and Zoho calls are doubles. No paid model, provider
mutation or real-user test send occurred.

Negative cases cover disabled/missing authorization, wrong sender/recipient,
foreign/missing provenance, direct transport bypass, inherited task context,
disabling between upload and send, and disabling before a retry. Positive cases
cover text/media/template, feedback, an isolated fresh conversation and real
PostgreSQL delivered/read status progression.

Independent security review found one P1: phone-only lookup could rebind an old
conversation. Channel-scoped lookup and real PostgreSQL regressions corrected
it; read-only re-review found no remaining blocking issues. The manager case
tests the audited send function, not a complete Telegram webhook roundtrip.

Root Ruff, formatting, Mypy and diff whitespace checks passed on the final
source. This is focused local evidence, not full release acceptance or stage
closure. The stage remains `replan_required`; frozen criteria are unchanged.

# Risks / Follow-ups

- At 17:00:25 UTC, read-only User API v3 lookup still returned test0665 as
  `qridle`. Its owner must reconnect the same phone via QR. Official reference:
  https://wazzup24.ru/help/api-ru/rabota-s-kanalami/ .
- Read-only DB count found zero audit rows after containment at16:45:12 UTC.
  Stopping processes cannot recall previously submitted provider requests.
- Old stopped containers retain the forbidden sender environment. Never start
  them or merge to auto-deploying main. Controlled recovery needs new safe
  containers and a reviewed startup plan. No rollout occurred here.
- The new allow setting remains absent from prod. New code would deny sending;
  the stopped old release does not implement this guard.
- This protects WhatsApp egress, not all LLM/CRM/Telegram side effects. Startup
  and retained jobs need explicit bounds before recovery.
- No old-message replay, queue deletion, DB data mutation, neighboring-product
  change, new sender approval or deferred webhook-auth hardening was included.
- docs-reviewed: updated - README, handoff and current incident evidence.
  graph-reviewed: no-change-needed - no graph in the isolated worktree; no
  external extraction or graph refresh was run.
