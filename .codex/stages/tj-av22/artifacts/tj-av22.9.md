---
schema_version: orchestration-artifact/v3
artifact_type: review-report
stage_manifest: .codex/stages/tj-av22/stage-manifest.json
stream_owner: final-reviewer
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: n/a
bounded_acceptance: independent review of durable inbound replay correction and five durable-documentation corrections
non_goals:
  - product-code or durable-documentation changes
  - Beads mutation
  - production or external-service proof
evidence:
  - none
task_id: tj-av22.9
epic_id: tj-av22
stage_id: tj-av22
session_id: tj-av22-final-review
milestone: noor-stabilization-final-review
milestone_status: replan-required
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk concurrency retry idempotency and durable-documentation review
repo: treejar
branch: codex/tj-av22-final-review
base_branch: codex/tj-av22-stabilization
base_commit: 87a9b29888f52e719838d8276e5ba3a4bdbe2c6d
worktree: /home/me/code/treejar/.worktrees/tj-av22-final-review
write_zone:
  - .codex/stages/tj-av22/artifacts/tj-av22.9.md
success_criteria:
  - inbound durability lease replay and manager-message boundaries have evidence-backed dispositions
  - five prior documentation findings have current dispositions
  - local and approval-gated production proof remain distinct
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-av22/artifacts/tj-av22.7.md
  - .codex/stages/tj-av22/artifacts/tj-av22.8.md
  - .codex/stages/tj-av22/prompts/tj-av22.9-final-review.md
selected_skills:
  - code-review
  - verification-before-completion
selected_agents:
  - independent-stabilization-and-documentation-reviewer
catalog_candidates:
  - none
parallel_group: final-stabilization-review
depends_on_streams:
  - inbound-correction
  - durable-documentation-correction
parallel_decision: sequential
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: isolated review worktree retained for root inspection
risk_level: high
verification_tier: integration
risk_tags:
  - concurrency
  - retry
  - state-transition
  - idempotency
  - rollback
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - state-transition
  - idempotency
  - rollback
  - test-matrix
docs_impact: behavior
docs_reviewed: needs-work
docs_review_notes: the five tj-av22.8 findings are corrected, but the inbound replay runbook overstates the execution-guard boundary
graph_reviewed: no-change-needed
graph_review_notes: Graphify is not configured and graphify-out/GRAPH_REPORT.md is absent
verification:
  - focused inbound and manager matrix - 50 passed: passed
  - later-batch read-only probe - recovered and new messages processed as separate batches: passed
  - voice replay read-only probe - two transcription calls and zero started-guard writes: failed
  - process verification: passed
  - ruff check src tests: passed
  - ruff format check src tests: passed
  - mypy src - 162 source files: passed
  - initial full pytest without frontend node_modules - 1499 passed 7 failed 19 skipped due missing esbuild: environment-incomplete
  - npm ci frontend admin - 90 packages 0 vulnerabilities: passed
  - full pytest after npm ci - 1506 passed 19 skipped: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.9.md
explicit_defers:
  - tj-av22.6 - execution guard must cover voice transcription before release
  - tj-av22.3 - all deployment live traffic credential and production readback proof remains approval-gated
---

# Summary

**NEEDS WORK / DO NOT RELEASE.** Durable Redis leasing fixes accepted-message
loss, and all five `tj-av22.8` documentation findings are corrected. One P1
replay gap remains: voice transcription invokes the OpenRouter LLM before the
immutable batch receives its execution guard.

# P1 Finding

## Voice transcription can replay before the execution guard

- **Evidence:** audio download and `transcribe_audio_with_metadata` run at
  `src/services/chat.py:997-1059`. The first execution-guard write is later,
  after database work, at `src/services/chat.py:1389`; the other guarded paths
  begin at `src/services/chat.py:1325` and `src/services/chat.py:1360`.
- **Probe:** two attempts against the same durable voice batch, with a database
  failure after transcription, produced `transcription_calls_before_guard=2`,
  `execution_started_writes=0`, and `processing_deleted=False`.
- **Impact:** a retry after a late pre-guard failure can repeat a paid LLM
  provider call. This does not satisfy the prior P1 requirement to guard before
  LLM/provider work and contradicts `docs/operations-runbook.md:188-193`.
- **Correction:** establish and test the replay boundary before voice
  transcription (and describe the exact boundary in the runbook), while
  preserving safe retry for failures that occur before any external call.

No other new P0, P1, or P2 finding was identified in the assigned correction
scope.

# Scope / Routing

This read-only review covered commits `71efe57` and `99283af`, the prior
`tj-av22.7`/`tj-av22.8` findings, current implementation/tests, and durable
operator documentation. The only repository write is this artifact.

# Required Dispositions

- **Durable accepted batch:** resolved. `LMOVE` builds the processing list at
  `src/services/chat.py:265-282`; retry/cancellation retains it, and a recovered
  list is read before the source queue.
- **Lease lifetime and ownership:** resolved locally.
  `INBOUND_BATCH_LOCK_TTL_SECONDS=660` at `src/services/chat.py:80` exceeds the
  configured 600-second worker timeout at `src/worker.py:143`; owner-token Lua
  release is used at `src/services/chat.py:285-315`.
- **Completed/uncertain replay:** resolved for work after the guard, but
  incomplete for voice transcription. Completed batches are acknowledged
  without `_process_batch_inner` at `src/services/chat.py:779-792`; recovered
  `started` batches are quarantined without re-entering it.
- **Messages arriving during recovery:** resolved. A read-only probe observed
  `[[old], [new]]` as two separate `_process_batch_inner` calls; recovery did
  not merge the source-queue message into the immutable processing batch.
- **Manager messages:** resolved. They are persisted and return before fallback
  or customer-response paths at `src/services/chat.py:1316-1322`; the focused
  manager tests passed and `process_message` was not called.
- **Runbook:** needs one correction. Its durable-list and uncertain-quarantine
  descriptions are accurate, but the claim that the guard precedes every LLM
  or provider action is false for voice transcription.

# Five Documentation Findings

All five findings from `tj-av22.8` are resolved:

1. Artifact-based, approval-gated deploy/rollback and restart semantics are
   aligned at `docs/dev-guide.md:353-377` and `docs/admin-guide.md:230-233`.
2. Redis/PostgreSQL health, version, dependency fields, sanitized HTTP `503`,
   and removed debug route are accurate at `docs/admin-guide.md:176-188`.
3. Zoho recovery uses the service-specific CRM and Inventory refresh-token
   names and keeps regeneration/scope changes approval-gated at
   `docs/admin-guide.md:222-227`.
4. Slow-response guidance starts with worker latency evidence and preserves the
   separate live-matrix approval gate at `docs/admin-guide.md:222-227`.
5. README no longer hard-codes an API endpoint count at `README.md:59-62`.

# Verification

The focused matrix passed (`50 passed`). Process verification, Ruff check,
Ruff format, and Mypy passed. The first full suite lacked frontend
`node_modules` and reported seven missing-`esbuild` failures; after the CI
equivalent `npm ci --prefix frontend/admin`, the fresh full suite passed with
`1506 passed, 19 skipped`.

# Delivery / Cleanup

The artifact is returned on `codex/tj-av22-final-review` for root triage. No
implementation or durable-documentation correction was made, and the isolated
worktree remains available for inspection.

# Risks / Follow-ups

Keep stage acceptance and `tj-av22.6` open until the voice transcription guard
boundary and runbook wording are corrected and independently re-reviewed.

No production, credential, live Wazzup/Telegram/Zoho/OpenRouter, deployment, or
external write was performed. Those proofs remain explicit approval gates.
