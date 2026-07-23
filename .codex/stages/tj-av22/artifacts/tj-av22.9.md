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
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: independent high-risk concurrency retry idempotency and durable-documentation review
repo: treejar
branch: codex/tj-av22-final-review
base_branch: codex/tj-av22-stabilization
base_commit: 7d2251d8ac5bf82f8f99d2dcc714bb4b5f41c1ea
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
docs_reviewed: no-change-needed
docs_review_notes: the five tj-av22.8 corrections remain accurate and the runbook now matches the pre-provider execution guard
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
  - correction regression test - 1 passed: passed
  - correction focused inbound and manager matrix - 51 passed: passed
  - correction two-attempt voice replay probe - one transcription one started guard then uncertain quarantine: passed
  - correction process verification: passed
  - correction ruff check and format on changed files: passed
  - correction mypy src - 162 source files: passed
  - root canonical correction gate - 1507 passed 19 skipped: passed
changed_files:
  - .codex/stages/tj-av22/artifacts/tj-av22.9.md
explicit_defers:
  - tj-av22.3 - all deployment live traffic credential and production readback proof remains approval-gated
---

# Summary

**PASS / LOCALLY RELEASE-READY.** On integration snapshot `7d2251d`, the prior
voice-transcription P1 is closed. Durable Redis leasing, replay quarantine,
manager-message silence, and all five `tj-av22.8` documentation corrections
remain valid. Approval-gated production proof is still outstanding.

# Correction Round

Commit `fb52643` adds one idempotent `_ensure_side_effect_guard` at
`src/services/chat.py:904-909` and invokes it at `src/services/chat.py:1006-1007`
before audio download or transcription at `src/services/chat.py:1067-1069`.
The same helper guards voice fallback, escalation, and the main LLM path at
`src/services/chat.py:1334-1335`, `src/services/chat.py:1364-1371`, and
`src/services/chat.py:1393-1405`.

The existing regression at `tests/test_services_chat.py:237-322` passed. An
independent two-attempt probe produced: first outcome `Retry`, second outcome
`uncertain_replay`, `transcription_calls=1`, `execution_started_writes=1`,
`quarantine_writes=1`, and processing deletion only after quarantine. The
second attempt therefore did not re-enter transcription or other provider work.

No current P0, P1, or P2 finding remains in the assigned scope.

# Prior P1 Finding

The initial review on snapshot `87a9b29` demonstrated two voice transcription
calls with no `started` guard before a late database failure. That historical
finding drove `fb52643` and is now resolved by the correction evidence above.

# Scope / Routing

This read-only review covered commits `71efe57`, `99283af`, and `fb52643`, the
prior `tj-av22.7`/`tj-av22.8` findings, current implementation/tests, and
durable operator documentation. The only repository write is this artifact.

# Required Dispositions

- **Durable accepted batch:** resolved. `LMOVE` builds the processing list at
  `src/services/chat.py:265-282`; retry/cancellation retains it, and a recovered
  list is read before the source queue.
- **Lease lifetime and ownership:** resolved locally.
  `INBOUND_BATCH_LOCK_TTL_SECONDS=660` at `src/services/chat.py:80` exceeds the
  configured 600-second worker timeout at `src/worker.py:143`; owner-token Lua
  release is used at `src/services/chat.py:285-315`.
- **Completed/uncertain replay:** resolved, including voice transcription.
  Completed batches are acknowledged without `_process_batch_inner` at
  `src/services/chat.py:779-792`; recovered `started` batches are quarantined
  without re-entering it.
- **Messages arriving during recovery:** resolved. A read-only probe observed
  `[[old], [new]]` as two separate `_process_batch_inner` calls; recovery did
  not merge the source-queue message into the immutable processing batch.
- **Manager messages:** resolved. They are persisted and return before fallback
  or customer-response paths at `src/services/chat.py:1326-1332`; the focused
  manager tests passed and `process_message` was not called.
- **Runbook:** resolved. The pre-provider guard claim at
  `docs/operations-runbook.md:188-193` now matches the implementation.

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

For correction round two, the dedicated regression passed (`1 passed`), the
focused inbound/manager matrix passed (`51 passed`), and the independent
two-attempt probe confirmed one transcription followed by uncertain quarantine
without replay. Process verification, changed-file Ruff/format, and Mypy over
162 source files passed. The root canonical correction gate reported
`1507 passed, 19 skipped` on the same integration snapshot.

# Delivery / Cleanup

The artifact is returned on `codex/tj-av22-final-review` for root triage. No
implementation or durable-documentation correction was made, and the isolated
worktree remains available for inspection.

# Risks / Follow-ups

The locally reviewable inbound P1 is closed. Stage release still depends on the
explicit production proofs tracked by `tj-av22.3`.

No production, credential, live Wazzup/Telegram/Zoho/OpenRouter, deployment, or
external write was performed. Those proofs remain explicit approval gates.
