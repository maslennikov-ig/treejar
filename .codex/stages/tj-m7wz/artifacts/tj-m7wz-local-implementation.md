---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-m7wz
stage_id: tj-m7wz
repo: treejar
branch: codex/tj-gh42-quote-context-provenance
base_branch: origin/main
base_commit: 29d16ec8d13ef8c7fb367289a27bf49c72026bea
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh42-quote-context-provenance
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: stage worktree is intentionally retained for commit, delivery, deploy verification, and live E2E
risk_level: high
verification:
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py::test_tools_create_quotation_requires_explicit_company_or_individual_instead_of_crm_fallback -v --tb=short: failed before fix, then passed
  - PYTHONPATH=. OPENROUTER_API_KEY=dummy uv run --extra dev pytest tests/test_llm_engine.py -k "quantity or quote or quotation or individual" -v --tb=short: passed (82 passed, 122 deselected)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed after npm --prefix frontend/admin ci (1136 passed, 16 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - scripts/orchestration/run_stage_closeout.py --stage tj-m7wz: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-m7wz/summary.md
  - .codex/stages/tj-m7wz/artifacts/tj-m7wz-local-implementation.md
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - live E2E on +79262810921 remains pending until the fixed commit is delivered to the production runtime
---

# Summary

Implemented quotation-context and PDF-provenance fixes for GitHub #41-#46 in the dedicated `tj-m7wz` worktree. The bot now persists pending product references when asking for quantity, resolves bare quantity replies into the prior product context, recovers quote items from prose confirmations, treats `individual purchase` as customer type, and prevents stale CRM/test company/email data from satisfying or rendering customer-facing quotation PDF fields.

# Verification

The new regression tests were written before the corresponding implementation. Targeted quote regression tests, ruff, format check, mypy, full pytest, process verification, stage closeout, and two visible correctness reviews passed. The first full pytest run failed only because the isolated worktree lacked `frontend/admin` Node dependencies; after `npm --prefix frontend/admin ci`, the full suite passed.

# Risks / Follow-ups

The remaining validation is runtime delivery plus live E2E on the approved phone number `+79262810921`. No production mutation or GitHub issue closure has been performed in this local implementation artifact.
