---
task_id: tj-final27.7
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-7-qa-reporting
base_branch: main
base_commit: 10e128fab6958186dcfed079fa2e360129e5d43f
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-7-qa-reporting
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_reports.py::test_report_data_defaults tests/test_reports.py::test_format_report_text_contains_final_acceptance_fields tests/test_reports.py::test_generate_report_populates_final_acceptance_fields -q: passed after expected RED
  - uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_reports.py tests/test_reports_manager.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_db_integration.py::test_generate_report_returns_correct_structure tests/test_db_integration.py::test_generate_report_handles_empty_data tests/test_db_integration.py::test_generate_report_quality_uses_active_conversation_window -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.7.md: passed
changed_files:
  - src/services/reports.py
  - tests/test_reports.py
  - docs/testing/final-qa-reporting-runbook.md
  - .codex/stages/tj-final27/artifacts/tj-final27.7.md
---

# Summary

Closed the weekly reporting acceptance gap by adding refusal, post-delivery feedback, and LLM cost-control fields to `ReportData`, `generate_report()`, and Telegram report text. Existing bot QA and manager QA fields remain intact. Added focused TDD coverage for the new report fields and a small safe-runbook for owner/operator QA/report checks.

AI Quality Controls code already satisfied the safe defaults in the inspected implementation: scopes default to `disabled`, transcript mode defaults to `summary`, full transcript requires explicit warning override, and QA usage/cost/cache telemetry is persisted through `llm_attempts`.

Docs used: Context7 SQLAlchemy 2.0 async docs for awaited `AsyncSession.execute/scalars`; Context7 pytest docs for focused selection/monkeypatch patterns. FastAPI and React docs were not needed because no FastAPI or React files were changed.

# Verification

RED was confirmed first: the focused `tests/test_reports.py` selection failed because `ReportData` lacked the final-acceptance fields and formatted text lacked the new sections.

GREEN verification run:

- `uv run --extra dev python -m pytest -s tests/test_reports.py::test_report_data_defaults tests/test_reports.py::test_format_report_text_contains_final_acceptance_fields tests/test_reports.py::test_generate_report_populates_final_acceptance_fields -q` passed.
- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_reports.py tests/test_reports_manager.py -q` passed: 51 passed.
- `uv run --extra dev python -m pytest -s tests/test_db_integration.py::test_generate_report_returns_correct_structure tests/test_db_integration.py::test_generate_report_handles_empty_data tests/test_db_integration.py::test_generate_report_quality_uses_active_conversation_window -q` passed: 3 passed.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- `uv run mypy src/` passed.
- `git diff --check` passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.7.md` passed.

# Risks / Follow-ups / Explicit Defers

- No production, deploy, Wazzup, broad production suite, scheduled AI Quality Controls enablement, or live QA sample was run.
- `docs/admin-guide.md`, `OperatorCenter.tsx`, `operators.ts`, and `types/operators.ts` were not edited per worker write-zone restrictions. The backend API/text report includes the new fields; the existing React report panel may not render every new field until an owner-approved UI/docs merge touches those files.
- Refusal reporting uses the current local data model proxy: cancelled deals plus closed conversations without a Zoho deal. A richer refusal taxonomy remains a client/business decision if required.
