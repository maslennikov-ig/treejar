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
  - stable non-user synthetic fixtures remain limited to unit tests and mocks
  - live delivery scripts require an explicit validated destination and fail closed without one
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
verification_tier: release
risk_tags:
  - security
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: historical evidence uses a protected marker; live-script usage now documents the required explicit destination environment variable
verification:
  - TDD RED for missing scripts.live_test_destination contract: passed by failing with ModuleNotFoundError
  - TDD RED for a generic reset usage placeholder: passed by failing against the synthetic runtime example
  - focused GREEN for the generic reset usage placeholder: passed, 1 test
  - uv run pytest tests/test_live_test_destination.py: passed, 9 tests
  - affected pytest slice including live-destination contract: passed, 430 tests
  - integration live suite collection without destination: passed, 10 tests collected and no live execution
  - repository-wide exact current-tree tracked scan: passed with zero matches
  - repository-wide separator-insensitive normalized current-tree scan: passed with zero matches
  - uv run pytest on ten directly affected test modules: passed, 421 tests
  - uv run ruff check on affected source, scripts, and tests: passed
  - uv run ruff format --check on affected source, scripts, and tests: passed
  - uv run mypy src/: passed, 162 source files
  - full uv run ruff check src/ tests/: passed
  - full uv run ruff format --check src/ tests/: passed, 304 files
  - full uv run pytest tests/: passed, 1633 tests and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
  - git diff --check: passed
changed_files:
  - 61 historical .codex/stages artifact and summary files
  - 6 historical docs/client, docs/prompts, docs/specs, and docs/testing files
  - scripts/run_integration_tests.py
  - scripts/send_test_pdf.py
  - scripts/live_test_destination.py
  - src/api/telegram_webhook.py
  - tests/integration/conftest.py
  - tests/test_live_test_destination.py
  - 10 directly affected tests/test_*.py modules
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.2-historical-phone-redaction.md
explicit_defers:
  - Git history still contains the historical identity; rewrite requires explicit destructive-action authority and coordinated repository handling
  - The schema-required tj-ee5f stage manifest is absent on this main-based branch; root must register this returned artifact in the existing acceptance manifest after cherry-pick
---

# Summary

Redacted the historical test identity from the tracked current tree. Historical
documentation and stage evidence now use `[PROTECTED_TEST_PHONE]`; unit tests
and mocks use a stable non-user synthetic value while preserving leading-plus,
bare-digit, URL-encoding, suffix, and normalization behavior. Live-delivery
scripts have no destination default: they require an explicit validated
`NOOR_LIVE_TEST_WHATSAPP_PHONE` value before any external work.

The masked baseline contained 266 continuous occurrences across 81 tracked
files. A separator-insensitive scan found three additional formatted fixtures.
Both exact and normalized current-tree scans now return zero matches.

# Scope / Routing

This stream owns only current-tree redaction. It does not own the active
acceptance contracts, live authorization, provider execution, deployment,
production state, or Git history. The task used the repository contract and a
mechanical no-new-test lane for the redaction, followed by TDD for the reviewed
live-destination safety correction.

The v3 schema requires the canonical tj-ee5f manifest path in frontmatter.
That manifest is not present on this main-based branch and was intentionally
not fabricated; the root orchestrator must register this returned artifact in
the existing acceptance manifest after integration.

# Verification

- `uv run pytest tests/test_api_conversations.py tests/test_conversation_reset.py tests/test_escalation_fallback.py tests/test_escalation_state.py tests/test_llm_engine.py tests/test_llm_engine_customer_facts.py tests/test_llm_quotation.py tests/test_messaging_wazzup.py tests/test_scripts_bot_test.py tests/test_telegram_reset.py -q --tb=short`: `421 passed`.
- `uv run pytest tests/test_live_test_destination.py -q --tb=short`: `9 passed`;
  proves there is no live default, explicit environment binding works,
  placeholders are rejected, and both live scripts fail before external work.
- Affected slice: `430 passed`; integration-live collection found 10 tests
  without executing them.
- Focused Ruff check and format check over the affected source, scripts, and
  tests: passed.
- `uv run mypy src/`: passed for 162 source files.
- Full release gate: Ruff passed, format passed for 304 files, Mypy passed,
  and Pytest passed with `1633 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh`: passed.
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

The artifact remains `returned` and unaccepted. Its schema-required manifest
path is intentionally unresolved on this branch until root integration.
