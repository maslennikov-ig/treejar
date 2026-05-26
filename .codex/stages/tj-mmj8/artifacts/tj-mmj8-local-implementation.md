---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-mmj8
stage_id: tj-mmj8
repo: treejar
branch: codex/fr3309-brief-details
base_branch: origin/main
base_commit: 5e2917d05866d8ba3f538ec3a33dd3ccfbd2e188
worktree: /home/me/code/treejar/.worktrees/codex-fr3309-brief-details
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: local worktree retained because deploy, merge, and live E2E are not authorized for this stage yet
risk_level: high
verification:
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest Fr3309 targeted tests: failed before implementation, then passed (6 passed)
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py -v --tb=short: passed (216 passed)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: failed before frontend/admin npm ci because esbuild was missing
  - npm ci in frontend/admin: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1149 passed, 16 skipped)
  - scripts/orchestration/run_process_verification.sh --stage tj-mmj8: passed
  - scripts/orchestration/run_stage_closeout.py --stage tj-mmj8: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-mmj8/summary.md
  - .codex/stages/tj-mmj8/artifacts/tj-mmj8-local-implementation.md
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - tj-mmj8 tracked deploy, production smoke, and live E2E replay are pending explicit owner authorization
---

# Summary

Implemented the Fr3309 quote-brief fix in the dedicated worktree. The bot now
parses ordered unlabeled customer briefs while quote context is active, stores
high-confidence details directly, asks confirmation for low-confidence briefs,
continues after affirmative confirmation, and prevents ambiguous `individual`
follow-ups from overwriting explicit company data such as `LLD`.

# Verification

The Fr3309 tests were written red first and now pass. The full local gate passed
after installing the admin frontend dependencies in this isolated worktree.

# Delivery / Cleanup

The stream is accepted into this local branch but not merged or deployed. The
worktree remains for delivery because production mutation and live WhatsApp E2E
were not authorized for this stage.

# Risks / Follow-ups

Production is not fixed until this branch is merged, deployed, smoke-tested, and
the approved Fr3309 live replay is completed. That defer is tracked on
`tj-mmj8`.
