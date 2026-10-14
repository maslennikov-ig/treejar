---
schema_version: orchestration-artifact/v1
task_id: tj-7ize
stage_id: tj-7ize
repo: treejar
branch: codex/tj-7ize-ci-20261014
base_branch: main
base_commit: 4b032c718888f6393b5bbc9a50e2b7f7f78e7041
worktree: /home/me/code/treejar/.worktrees/tj-7ize-ci-20261014
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Assigned scoped worker; no model override or paid calls.
status: returned
delivery_method: not accepted
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: Retain branch/worktree for root review and delivery.
risk_level: low
verification:
  - uv run --no-sync pytest tests/test_ci_workflow_contract.py -q --tb=short --import-mode=importlib: passed, 42 tests
  - uv run --no-sync ruff check tests/test_ci_workflow_contract.py: passed
  - uv run --no-sync ruff format --check tests/test_ci_workflow_contract.py: passed
  - git diff --check: passed
changed_files:
  - .github/workflows/ci.yml
  - tests/test_ci_workflow_contract.py
  - docs/reports/2026-10-14-runtime-doc-ci-fix.md
explicit_defers:
  - none
---

# Summary

Both main push and pull-request path filters use ordered `paths`: include all,
exclude `.codex/**`, `.beads/**`, `docs/**` and Markdown, then re-include exactly
`docs/faq.md` and `docs/04-sales-dialogue-guidelines.md`. The existing deployment
classifier already recognizes both runtime documents and is unchanged.

Current [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore)
requires `paths` for combined inclusion/exclusion and evaluates the patterns in
order. Commit `4b032c7` introduced unsupported re-inclusion via `paths-ignore`.

# Verification

- Before the workflow fix: 7 failed / 35 passed; failures covered the invalid
  filter and runtime-document-only changes for both events.
- After the fix: 42 passed in 0.59s. The 36 trigger cases cover each runtime doc,
  FAQ plus report, report-only Markdown/HTML, ordinary docs, FAQ backups, root
  and nested Markdown, orchestration, tracker, source, tests, workflow, source
  plus report in both file orders, and an empty change set for both events.
- Commands above used `UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv`
  with `--no-sync`. Pytest also used `PYTHONPATH=.`, `APP_ENV=test`, fake keys,
  empty Telegram/Zoho credentials, and local port 9 for DB/Redis/LLM endpoints.
  Interpreter: Python 3.12.13. No live provider calls or mutations were made.
- Scoped line-by-line code review and file history review: no actionable
  findings. Source, classifier, jobs, permissions and deploy conditions retain
  their existing content. Only trigger rules, regression coverage and this
  receipt changed.

# Risks / Follow-ups

No in-scope issues remain. Hosted GitHub Actions has not been exercised by this
worker. Root owns final acceptance, tracker updates, delivery and cleanup; this
worktree has not pushed, merged, deployed or closed the task.
