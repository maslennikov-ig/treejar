---
task_id: tj-e2e26.1-3
stage_id: tj-e2e26
repo: treejar
branch: codex/tj-e2e26-order-decision-replies
base_branch: codex/live-triage-20260417
base_commit: b54ebb7
worktree: /home/me/code/treejar/.worktrees/codex-tj-e2e26-order-decision-replies
status: returned
verification:
  - uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_order_review_flow.py tests/test_webhook_manager.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-e2e26/artifacts/tj-e2e26.1-3.md: passed
  - git diff --check: passed
changed_files:
  - src/llm/engine.py
  - src/api/telegram_webhook.py
  - tests/test_llm_engine.py
  - tests/test_order_review_flow.py
  - tests/test_webhook_manager.py
  - .codex/stages/tj-e2e26/artifacts/tj-e2e26.1-3.md
---

# Summary

Implemented batch fixes for `tj-e2e26.1` and `tj-e2e26.3`.

- `check_order_status()` now reads active `conversation.metadata_["zoho_sale_order_id"]` before falling back to no-order, so metadata-only sale orders fetch Inventory status without a CRM deal ID.
- Rejected order decisions now persist explicit inactive metadata (`quotation_decision.status=rejected`, `active=false`, `zoho_sale_order_active=false`, `order_active=false`) so order-status/admin consumers can ignore stale sale-order metadata.
- Confirm/reject Telegram order decisions now persist decision metadata with status, quote number, sale order id/number when present, `decided_at`, and `source=telegram_order_decision`.
- Successful Telegram private manager replies now persist the adapted customer-facing text as an assistant `Message` with `model="manager_reply"` and Wazzup message id when returned. Failed Wazzup sends do not create a message or resolve escalation.

# Verification

- `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_order_review_flow.py tests/test_webhook_manager.py -q` -> passed, `72 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-e2e26/artifacts/tj-e2e26.1-3.md` -> passed.
- `git diff --check` -> passed.

# Risks / Follow-ups / Explicit Defers

- No production, staging, deploy, OpenRouter key, frontend, scheduled AI Quality Controls, broad production suite, `verify_wazzup.py`, or unsolicited media tests were touched or run.
- A pre-fix pytest attempt without `-s` hit the known local pytest capture tmpfile `FileNotFoundError` before collection; the required `-s` targeted command passed after implementation.
- Runtime E2E validation and Beads closeout remain for the orchestrator/reviewer.
