---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.6-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4.4-acceptance-harness
public_facade: process_message
bounded_acceptance: counted-manager-handoff-on-repair-fallback
non_goals:
  - acceptance-harness-journal
  - frozen-twenty-measured-round
evidence:
  - focused-fallback-tests
task_id: tj-n7p4.6
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: unsafe-or-unavailable-repair-becomes-manager-handoff
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential change on the same final response and escalation boundary
repo: treejar
branch: main
base_branch: main
base_commit: f12cc5c
worktree: /home/me/code/treejar
write_zone:
  - src/llm/repair_judge.py
  - src/llm/message_processor.py
  - tests/test_llm_repair_judge.py
  - .codex
success_criteria:
  - provider-unavailability-hands-off
  - cannot-fix-hands-off
  - rejected-correction-hands-off
  - fallback-counted-separately
  - customer-told-in-served-language
  - no-deterministic-deletion-restored
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
  - docs/plans/2026-08-11-orchestrator-prompt.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-n7p4.3
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - authorization
  - security
affected_surfaces:
  - backend
invariants:
  - no-deterministic-customer-text-removal
  - escalation-persists-before-customer-notice
  - one-final-customer-boundary
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record fallback outcomes accounting persistence and localized customer notice
verification:
  - focused TDD red: five fallback tests failed before implementation
  - focused green: 17 repair-judge tests passed
  - affected response-path regression: 849 tests passed
  - provider unavailable cannot-fix and rejected correction each replace the unsafe draft and deterministic candidate with a manager notice
  - existing active manager handoff is reused without duplicate notification
  - English and Arabic customer notices passed the full response policy without a removal flag
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 373 files
  - uv run mypy src/: passed over 174 source files
  - uv run pytest tests/ -v --tb=short: 3590 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.6.md
  - src/llm/message_processor.py
  - src/llm/repair_judge.py
  - tests/test_llm_repair_judge.py
explicit_defers:
  - tj-n7p4.4-owns-production-parity-and-call-journaling-in-the-acceptance-harness
---

# Summary

Every unresolved repair now becomes a real manager handoff rather than the old
sentence deletion. The same boundary covers a provider exception, `cannot_fix`,
and an empty or still-flagged correction. It counts the fallback separately.

# Scope / Routing

The root implemented this sequentially because the repair call, response
finalizer, escalation persistence and final customer text share one transaction
boundary. The handoff reason contains only outcome, model and guard names; it
does not copy customer or provider error text. No subagent or paid call was
needed.

# Verification

Five behavior tests failed before implementation. After implementation, all 17
repair tests and 849 affected response-path tests passed. They prove the unsafe
draft and deterministic candidate are absent, the escalation occurs before the
final reply is recorded, English and Arabic notices are safe, an active handoff
is reused, and provider failures are counted distinctly. Ruff, format, Mypy,
all repository tests and process verification passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. No child
branch or worktree exists. No push, deploy, live mutation, model configuration
change, paid call or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`.4` must route the acceptance harness through this exact judged repair and
fallback boundary and journal only actual triggered calls. That is explicit
sequencing, not silent debt.
