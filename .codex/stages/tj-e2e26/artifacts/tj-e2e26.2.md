---
task_id: tj-e2e26.2
stage_id: tj-e2e26
repo: treejar
branch: codex/tj-e2e26-conversations-auth-filter
base_branch: codex/live-triage-20260417
base_commit: b54ebb7
worktree: /home/me/code/treejar/.worktrees/codex-tj-e2e26-conversations-auth-filter
status: returned
verification:
  - Context7 FastAPI docs-first check: passed
  - uv run --extra dev python -m pytest -s tests/test_api_conversations.py tests/test_scripts_bot_test.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_api_escalation.py tests/test_scripts_verify_api.py -q: passed
  - uv run ruff check src/ tests/ scripts/: failed
  - uv run ruff format --check src/ tests/ scripts/: failed
  - uv run ruff check src/ tests/ scripts/bot_test.py scripts/verify_api.py: passed
  - uv run ruff format --check src/ tests/ scripts/bot_test.py scripts/verify_api.py: passed
  - uv run mypy src/: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-e2e26/artifacts/tj-e2e26.2.md
  - scripts/bot_test.py
  - scripts/verify_api.py
  - src/api/v1/conversations.py
  - src/api/v1/router.py
  - tests/test_api_conversations.py
  - tests/test_api_escalation.py
  - tests/test_scripts_bot_test.py
  - tests/test_scripts_verify_api.py
---

# Summary

Implemented the `tj-e2e26.2` conversation API hardening in the dedicated worktree.

- `/api/v1/conversations` is now mounted with the existing `require_api_key` internal API boundary.
- Conversation list phone filtering is exact by default via `Conversation.phone == phone`.
- Explicit fuzzy matching remains available with `phone_match=fuzzy`.
- `scripts/bot_test.py` now reads `--api-key`, `BOT_TEST_API_KEY`, or `API_KEY`, does not print the secret, and sends `X-API-Key` only for protected conversation polling.
- `scripts/verify_api.py` now checks conversation auth denial when no key is supplied, or authorized conversation list access when `--api-key`, `VERIFY_API_KEY`, or `API_KEY` is configured.
- Tests cover anonymous denial for list/detail/update/escalate, authorized success, exact phone filtering, explicit fuzzy filtering, and smoke-tooling auth headers.

Context7/FastAPI docs note: queried `/fastapi/fastapi` before changing router auth wiring. The docs state that `dependencies=[Depends(...)]` on `APIRouter` or `include_router()` applies to all path operations in that router, executes before operation dependencies, and does not pass dependency return values to the endpoint handler when declared in the dependency list. This matches the API-key side-effect validation used here.

# Verification

- `uv run --extra dev python -m pytest -s tests/test_api_conversations.py tests/test_scripts_bot_test.py -q` -> passed, `20 passed`.
- `uv run --extra dev python -m pytest -s tests/test_api_escalation.py tests/test_scripts_verify_api.py -q` -> passed, `5 passed`.
- `uv run ruff check src/ tests/ scripts/` -> failed on pre-existing `scripts/orchestration/cleanup_stage_workspace.py` and `scripts/orchestration/run_stage_closeout.py` issues outside this task's write zone: E402/import ordering and SIM109.
- `uv run ruff format --check src/ tests/ scripts/` -> failed on pre-existing formatting drift in `scripts/orchestration/check_stage_ready.py`, `cleanup_stage_workspace.py`, `run_stage_closeout.py`, and `validate_artifact.py`, all outside this task's write zone.
- `uv run ruff check src/ tests/ scripts/bot_test.py scripts/verify_api.py` -> passed.
- `uv run ruff format --check src/ tests/ scripts/bot_test.py scripts/verify_api.py` -> passed, `231 files already formatted`.
- `uv run mypy src/` -> passed, `Success: no issues found in 122 source files`.
- `git diff --check` -> passed.

# Risks / Follow-ups / Explicit Defers

- Repo-wide `scripts/` ruff gates are blocked by unrelated orchestration-script lint/format drift outside the allowed write zone; left untouched for orchestrator review.
- `scripts/bot_test.py` now fails before sending a webhook when no API key is configured, to avoid creating live smoke traffic that cannot be correlated through the protected conversations API.
- No deploy, production/staging mutation, broad production suite, Wazzup verification, scheduled AI Quality Controls, or media tests were run.
