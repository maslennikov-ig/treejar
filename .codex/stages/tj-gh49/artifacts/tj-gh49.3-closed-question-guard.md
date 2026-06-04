---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh49.3
stage_id: tj-gh49
agent_type: n/a
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: Local sequential refactor; no independent write streams.
repo: treejar
branch: codex/tj-gh49-name-gate-duplicate-fix
base_branch: origin/main
base_commit: ac78d6a3b1f17d8ecd03a38201ddd2ab54b44933
worktree: /home/me/code/treejar/.worktrees/tj-gh49-name-gate
write_zone:
  - src/llm/closed_question_guard.py
  - src/llm/engine.py
  - tests/test_closed_question_guard.py
  - tests/test_llm_engine.py
success_criteria:
  - No narrow workstation/storage/assembly fallback remains.
  - Standalone repeated slot questions are repaired whenever the answer is already known.
  - Exact #48 and related known-name regressions pass.
selected_docs:
  - none - deterministic repo behavior; no version-sensitive dependency behavior.
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - none - sequential central LLM routing change; no current spawned-subagent authorization.
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
docs_reviewed: updated
docs_review_notes: Project index updated for src/llm/closed_question_guard.py.
verification:
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_closed_question_guard.py tests/test_llm_engine.py -v --tb=short": "242 passed"
  - "uv run ruff check src/llm/closed_question_guard.py src/llm/engine.py tests/test_closed_question_guard.py tests/test_llm_engine.py": passed
  - "uv run ruff format --check src/llm/closed_question_guard.py src/llm/engine.py tests/test_closed_question_guard.py tests/test_llm_engine.py": passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": "1233 passed, 19 skipped"
  - "scripts/orchestration/run_process_verification.sh": passed
  - "scripts/orchestration/run_stage_closeout.py --stage tj-gh49": passed
changed_files:
  - src/llm/closed_question_guard.py
  - src/llm/engine.py
  - tests/test_closed_question_guard.py
  - tests/test_llm_engine.py
  - .codex/project-index.md
explicit_defers:
  - tj-gh21 remains blocked on approved Wazzup WABA EN/AR templates.
---

# Summary

Replaced the first #48 fallback with a shared closed-question guard. The guard
does not parse products or duplicate sales logic. It checks whether a standalone
reply asks for state-backed slots that are already known: customer name,
company-or-individual status, and specific delivery address. It does not replace
long product/quote confirmations that merely mention those fields.

# Verification

The new tests first failed against the prior hotfix because it parsed
workstation/storage/assembly and did not protect known-name conversations
outside name-gate resume. After the refactor, the targeted closed-question and
engine suites pass, including regression coverage for summaries and selection
confirmations that must keep their substantive content.

# Risks / Follow-ups / Explicit Defers

External delivery remains tracked by `tj-gh49.2`: merge/deploy, production
smoke, synthetic/live #48 evidence, then GitHub comment/closure.
