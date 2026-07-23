---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: zoho-inbound-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: malformed-oauth-lock-retry-quarantine-and-replay-matrix
non_goals:
  - production-replay
  - production-deployment
  - live-zoho-wazzup-or-telegram-calls
  - documentation-outside-worker-write-zone
evidence:
  - none
task_id: tj-p9ui
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-zoho-inbound
milestone: noor-zoho-inbound-reliability
milestone_status: completed
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: cross-module OAuth parsing, distributed locking, queue retry, and idempotency risk
repo: treejar
branch: codex/tj-av22-zoho
base_branch: codex/tj-av22-stabilization
base_commit: 6ab4f7bd498b49dd9b40008564f2133b3c0ca4a0
worktree: /home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-zoho
write_zone:
  - src/integrations/zoho_oauth.py
  - src/integrations/crm/zoho_crm.py
  - src/integrations/inventory/zoho_inventory.py
  - src/services/chat.py
  - src/worker.py
  - focused-zoho-chat-batch-and-worker-tests
  - .codex/stages/tj-av22/artifacts/tj-p9ui.md
success_criteria:
  - malformed OAuth success responses fail deterministically without secrets
  - token TTL and refresh locking remain safe on all covered paths
  - transient accepted batches retry with bounded backoff
  - terminal batches are quarantined with sanitized failure metadata
  - replay reuses inbound and outbound idempotency identities
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - docs/superpowers/specs/2026-07-23-noor-stabilization-design.md
  - docs/superpowers/plans/2026-07-23-noor-stabilization.md
  - https://www.zoho.com/crm/developer/docs/api/v8/refresh.html
  - https://www.zoho.com/crm/developer/docs/api/v8/token-validity.html
selected_skills:
  - systematic-debugging
  - test-driven-development
  - verification-before-completion
  - format-commit-message
selected_agents:
  - built-in-worker
catalog_candidates:
  - none
parallel_group: zoho-inbound
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: isolated worktree retained for root-orchestrator review and integration
risk_level: high
verification_tier: integration
risk_tags:
  - concurrency
  - retry
  - state-transition
  - idempotency
affected_surfaces:
  - backend
invariants:
  - state-transition
  - idempotency
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: no-change-needed
docs_review_notes: worker write zone excludes durable docs; tj-av22.3 must reconcile the stale OAuth-lock wording and document inbound quarantine keys
verification:
  - uv run pytest focused Zoho CRM Inventory chat-batch and worker suite: passed
  - uv run pytest expanded chat webhook and worker affected suite: passed
  - uv run ruff check changed Zoho chat worker and focused test files: passed
  - uv run ruff format --check changed Zoho chat worker and focused test files: passed
  - uv run mypy src/integrations src/services/chat.py src/worker.py: passed
changed_files:
  - src/integrations/zoho_oauth.py
  - src/integrations/crm/zoho_crm.py
  - src/integrations/inventory/zoho_inventory.py
  - src/services/chat.py
  - src/worker.py
  - tests/test_zoho_crm.py
  - tests/test_zoho_client.py
  - tests/test_services_chat_batch.py
  - tests/test_worker.py
  - .codex/stages/tj-av22/artifacts/tj-p9ui.md
explicit_defers:
  - tj-av22.3 - production replay and deployment remain approval-gated
  - tj-av22.3 - reconcile docs/dev-guide.md OAuth-lock wording and document the inbound failure and quarantine Redis keys during integration closeout
---

# Summary

Zoho CRM and Inventory now share a typed, sanitized OAuth parser. It rejects
missing or blank access tokens, OAuth error JSON, invalid/non-object JSON,
unsupported token types, invalid expiry values, and unsafe HTTP/transport
responses without including response bodies or credentials in errors. Cache
TTL is clamped below Zoho's documented one-hour validity, and the distributed
lock and polling windows now outlive the refresh request timeout.

Accepted inbound batches retain their raw queue payload until the typed Zoho
outcome is known. Retryable OAuth failures restore the batch in original order
and raise an ARQ `Retry` with bounded exponential backoff. Attempt three and
terminal credential failures write the raw batch to a stable quarantine key,
append sanitized metadata to a bounded failure history, and fail the ARQ job.
Replayed inbound messages continue to use the existing unique Wazzup message
identifier, while bot replies now use a stable source-message idempotency key.

# Scope / Routing

The stream stayed inside the declared Zoho clients, shared OAuth module,
chat/worker boundary, focused tests, and this artifact. Official Zoho CRM V8
refresh and token-validity documentation established the one-hour token
contract and the need to reuse valid tokens. Repository and installed ARQ
source established `Retry`, `job_try`, and per-function `max_tries` behavior.
No live Zoho, Wazzup, Telegram, staging, or production access occurred.

# Verification

- The exact focused command passed: `61 passed`.
- The expanded affected chat/webhook/worker command passed: `85 passed`.
- Ruff check and format check passed on every changed Python file.
- Mypy passed on all integration modules plus `src/services/chat.py` and
  `src/worker.py`.
- Red tests first reproduced `KeyError`, raw JSON decode errors, unsafe TTL,
  undersized lock windows, lost retry state, missing quarantine behavior, and
  unstable reply identity before the corresponding changes.

# Delivery / Cleanup

Implementation commit `4824dc7` is on `codex/tj-av22-zoho`. The root
orchestrator reviewed the implementation, merged the returned stream as
`068ab1a`, and reran the exact 61-test focused suite plus Ruff, format, and
Mypy successfully. The isolated worktree remains available until approved
cleanup.

# Risks / Follow-ups / Explicit Defers

- No production replay or credential refresh was attempted. `tj-av22.3` owns
  approval-gated deployment, the exact affected-conversation review, and any
  production replay.
- `docs/dev-guide.md` still describes a generic 30-second OAuth lock, while the
  implementation uses separate CRM/Inventory keys with a 20-second lock and
  poll window around a 15-second refresh timeout. The operations runbook also
  does not yet document `wazzup:inbound:failures` or
  `wazzup:inbound:quarantine:<batch_id>`. Those files are outside this worker's
  write zone; `tj-av22.3` must update or explicitly carry this bounded defer.
