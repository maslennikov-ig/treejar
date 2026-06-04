---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh49.1
stage_id: tj-gh49
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: Local sequential fix; no independent write streams.
repo: treejar
branch: codex/tj-gh49-name-gate-duplicate-fix
base_branch: origin/main
base_commit: ac78d6a3b1f17d8ecd03a38201ddd2ab54b44933
worktree: /home/me/code/treejar/.worktrees/tj-gh49-name-gate
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
success_criteria:
  - Exact #48 flow no longer repeats the customer-name question after `Lili`.
  - Stored original request is resumed or safely continued.
  - Existing name-gate and SKU/product regression tests remain green.
selected_docs:
  - none - deterministic repo bug; no version-sensitive library/API behavior.
selected_skills:
  - process-issues
  - orchestrator-stage
  - systematic-debugging
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none - simple two-file sequential bugfix.
catalog_candidates:
  - none - installed repo skills were sufficient.
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No child worktree or delegated branch was created for this local stream.
risk_level: low
docs_impact: behavior
docs_reviewed: no-change-needed
docs_review_notes: Narrow runtime guard; stage summary and handoff updated.
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_bare_name_resume_repairs_duplicate_name_prompt -v --tb=short": passed before tj-gh49.3 refactor
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -v --tb=short": passed
  - "uv run ruff check src/llm/engine.py tests/test_llm_engine.py": passed
  - "uv run ruff format --check src/llm/engine.py tests/test_llm_engine.py": passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed after npm ci --prefix frontend/admin
  - "scripts/orchestration/run_process_verification.sh": passed
  - "scripts/orchestration/run_stage_closeout.py --stage tj-gh49": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - tj-gh21 remains blocked on approved Wazzup WABA EN/AR templates.
---

# Summary

Implemented the first local fix for GitHub #48. This artifact is superseded by
`tj-gh49.3`, which replaced the narrow repeated-name repair with a shared
closed-question guard.

# Verification

The new regression failed before the fix and now passes. The whole
`tests/test_llm_engine.py` suite passes with 234 tests. Full local pytest passes
with `1225 passed, 19 skipped` after restoring ignored frontend dependencies
with `npm ci --prefix frontend/admin`.

# Risks / Follow-ups / Explicit Defers

Delivery is still pending. GitHub #48 should not be closed until production
evidence is captured after deploy.
