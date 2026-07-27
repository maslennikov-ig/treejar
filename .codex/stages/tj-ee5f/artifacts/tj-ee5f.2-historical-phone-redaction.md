---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj_ee5f_phone_redaction
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: tj-ee5f acceptance evidence and Russian client report
public_facade: current-tree privacy boundary for test identities
bounded_acceptance: redact the historical test identity from the tracked current tree without rewriting Git history
non_goals:
  - Git history rewrite, push, deploy, live calls, provider calls, or production mutation
evidence:
  - none
task_id: tj-ee5f.2
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f
milestone: historical test-identity current-tree redaction
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: bounded privacy-sensitive mechanical redaction in an isolated worktree
repo: treejar
branch: codex/tj-ee5f-historical-phone-redaction
base_branch: main
base_commit: b2f740821d9e28305d5e283be5e0d77171dd1b8e
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-historical-phone-redaction
write_zone:
  - tracked current-tree files containing the protected historical test identity
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.2-historical-phone-redaction.md
success_criteria:
  - historical docs and stage evidence use a protected marker
  - behavior-sensitive source, scripts, and tests use a stable non-user synthetic fixture
  - exact and separator-insensitive repository scans have zero current-tree matches
  - affected tests and proportionate static checks pass
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - README.md
  - Beads tj-ee5f.2
selected_skills:
  - orchestrator-stage
  - test-driven-development no-new-test lane
  - systematic-debugging
  - verification-before-completion
  - orchestration-closeout
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: historical-phone-redaction
depends_on_streams:
  - tj-ee5f-task-1
parallel_decision: sequential
status: returned
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: dedicated worktree and branch retained for root-orchestrator review and integration
risk_level: high
verification_tier: delta
risk_tags:
  - security
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - test-matrix
docs_impact: docs-only
docs_reviewed: updated
docs_review_notes: historical client docs, runbooks, and stage evidence now use a protected marker; no public behavior or durable architecture changed
verification:
  - repository-wide exact current-tree tracked scan: passed with zero matches
  - repository-wide separator-insensitive normalized current-tree scan: passed with zero matches
  - uv run pytest on ten directly affected test modules: passed, 421 tests
  - uv run ruff check on affected source, scripts, and tests: passed
  - uv run ruff format --check on affected source, scripts, and tests: passed
  - uv run mypy src/: passed, 162 source files
  - git diff --check: passed
changed_files:
  - 61 historical .codex/stages artifact and summary files
  - 6 historical docs/client, docs/prompts, docs/specs, and docs/testing files
  - scripts/run_integration_tests.py
  - scripts/send_test_pdf.py
  - src/api/telegram_webhook.py
  - tests/integration/conftest.py
  - 10 directly affected tests/test_*.py modules
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.2-historical-phone-redaction.md
explicit_defers:
  - Git history still contains the historical identity; rewrite requires explicit destructive-action authority and coordinated repository handling
---

# Summary

Redacted the historical test identity from the tracked current tree. Historical
documentation and stage evidence now use `[PROTECTED_TEST_PHONE]`; executable
fixtures use a stable non-user synthetic value while preserving leading-plus,
bare-digit, URL-encoding, suffix, and normalization behavior.

The masked baseline contained 266 continuous occurrences across 81 tracked
files. A separator-insensitive scan found three additional formatted fixtures.
Both exact and normalized current-tree scans now return zero matches.

# Scope / Routing

This stream owns only current-tree redaction. It does not own the active
acceptance contracts, live authorization, provider execution, deployment,
production state, or Git history. The task used the repository contract and a
mechanical no-new-test lane, with existing behavioral tests as the acceptance
proof.

# Verification

- `uv run pytest tests/test_api_conversations.py tests/test_conversation_reset.py tests/test_escalation_fallback.py tests/test_escalation_state.py tests/test_llm_engine.py tests/test_llm_engine_customer_facts.py tests/test_llm_quotation.py tests/test_messaging_wazzup.py tests/test_scripts_bot_test.py tests/test_telegram_reset.py -q --tb=short`: `421 passed`.
- Focused Ruff check and format check over the affected source, scripts, and
  tests: passed.
- `uv run mypy src/`: passed for 162 source files.
- Exact tracked scan and separator-insensitive normalized tracked scan: zero
  matches.
- `git diff --check`: passed.

# Delivery / Cleanup

Returned on the dedicated branch for root-orchestrator review. No push, merge,
deploy, live action, provider call, or cleanup was performed.

# Risks / Follow-ups / Explicit Defers

Git history remains unchanged and therefore still contains the historical
identity. That exposure is bounded and explicit: any history rewrite requires
separate destructive-action authority, repository-wide coordination, remote
handling, and consumer re-cloning guidance.
