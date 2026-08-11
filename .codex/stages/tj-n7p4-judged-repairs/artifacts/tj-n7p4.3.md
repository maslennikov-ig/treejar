---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
stream_owner: tj-n7p4.3-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-n7p4.6-manager-handoff
public_facade: process_message
bounded_acceptance: three-answer-second-vendor-repair
non_goals:
  - manager-handoff-on-repair-failure
  - acceptance-harness-journal
  - frozen-twenty-measured-round
evidence:
  - protected-replay-under-git-common-dir
task_id: tj-n7p4.3
epic_id: tj-n7p4
stage_id: tj-n7p4-judged-repairs
session_id: tj-n7p4-judged-repairs
milestone: every-removal-flag-is-decided-by-a-second-vendor
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential change on the shared reply provider replay and cost boundary
repo: treejar
branch: main
base_branch: main
base_commit: d81a744
worktree: /home/me/code/treejar
write_zone:
  - src/llm/repair_judge.py
  - src/llm/message_processor.py
  - src/llm/response_policy.py
  - src/llm/response_runtime.py
  - src/llm/safety.py
  - tests
  - .codex
success_criteria:
  - approve-correct-cannot-fix-implemented-and-counted
  - correction-reclassified-before-send
  - empty-or-still-flagged-correction-rejected
  - one-judge-call-only-on-a-removal-flag
  - actual-final-reply-recorded-once
  - protected-correction-root-read
selected_docs:
  - docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md
  - docs/plans/2026-08-11-orchestrator-prompt.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-systematic-debugging
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-n7p4.2
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
  - one-final-customer-boundary
  - protected-corpus-stays-outside-git
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the provider contract replay reading test-contract update and cost
verification:
  - focused TDD red: repair-judge module and finalizer imports failed before implementation
  - focused green: 12 repair-judge tests passed
  - focused policy and processor regression: 137 tests passed
  - production-route regression after test isolation fix: 33 tests passed
  - protected preflight: 60 source digests matched; exactly one grounding flag on dialog 789
  - protected production-path replay: 60 checked; exactly one flagged and changed reply; final aggregate 802c0e956777866851a69378c70898e83cee8a42b56dedbf1ef738a73723ee14
  - repair judge: one z-ai/glm-5.2 call; correct; one accepted correction; zero approvals cannot-fix rejected corrections or handoffs; cost 0.001265216 USD
  - root reading: corrected reply removes the unsupported customer-furniture service and adds supported catalog help while preserving confirmed context and the next question
  - user-authorized stale-test update: two legacy deletion assertions now require original text plus a non-visible candidate; test isolation supplies a local repair judge
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 373 files
  - uv run mypy src/: passed over 174 source files
  - uv run pytest tests/ -v --tb=short: 3585 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/stage-manifest.json
  - .codex/stages/tj-n7p4-judged-repairs/summary.md
  - .codex/stages/tj-n7p4-judged-repairs/artifacts/tj-n7p4.3.md
  - src/llm/message_processor.py
  - src/llm/repair_judge.py
  - src/llm/response_policy.py
  - src/llm/response_runtime.py
  - src/llm/safety.py
  - tests/conftest.py
  - tests/test_llm_repair_judge.py
  - tests/test_llm_reply_rendering.py
  - tests/test_llm_response_guard_declarations.py
explicit_defers:
  - tj-n7p4.6-owns-manager-handoff-on-provider-failure-or-rejected-correction
---

# Summary

Removing guards no longer apply their deterministic candidate. They leave the
customer text intact and pass the reply, bounded evidence and flags to a fixed
second-vendor model. The judge may approve, correct or say it cannot fix the
reply; every answer, model and cost is counted. A correction is rendered again
and is rejected if it is empty or still flagged.

# Scope / Routing

The root implemented this sequentially because production response finalizing,
the repair provider, protected replay and call accounting share one boundary.
The finalizer is now the only place that records the actual reply. It masks PII
from both the reply and deterministic candidate before the provider call and
recomputes deferred media from the final text. Manager fallback remains the
immediately following `.6` child.

# Verification

The new tests were red first on the missing judge and finalizer, then all twelve
passed. The full route suite exposed an attempted external call because legacy
tests mocked only the primary model; an autouse local repair-judge stand-in now
keeps route tests isolated, and all 33 affected routes passed. The owner
authorized updating the two stale assertions that required deterministic
deletion; they now require original text plus a non-visible candidate.

The protected preflight matched all 60 source digests and found exactly one
flag. One authorized GLM call corrected that reply for $0.001265216. Exactly
dialog 789 changed, the correction reclassified cleanly, and the root read it
against both the original and prior deletion candidate. It replaces the
unsupported used-furniture promise with supported catalog help and preserves
the confirmed introduction and next question. No corpus text entered Git.

Ruff, format, Mypy, all 3,604 collected tests, and process verification passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. No child
branch or worktree exists. No push, deploy, live mutation, model configuration
change, scoring-model call or real-user message occurred.

# Risks / Follow-ups / Explicit Defers

`.6` owns the manager handoff for provider unavailability, cannot-fix and
rejected correction. This is explicit sequencing, not silent debt. The second
model is the semantic half of R2; deterministic reclassification remains its
formal lower bound, so `tj-rt7w.14` closes with this accepted reasoning.
