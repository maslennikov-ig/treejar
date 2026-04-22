---
task_id: tj-ruue.6
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-manager-reply-auto-faq-flow
base_branch: codex/live-triage-20260417
base_commit: 9a72f0c
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-manager-reply-auto-faq-flow
status: returned
verification:
  - Context7 PydanticAI docs query: passed
  - Orchestrator review report docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-manager-reply-auto-faq-flow-orchestrator.md: passed
  - uv run --extra dev python -m pytest -s tests/test_auto_faq.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat.py tests/test_llm_safety.py tests/test_faq_translation.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_response_adapter.py tests/test_auto_faq.py tests/test_webhook_manager.py tests/test_llm_safety.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_auto_faq.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat.py tests/test_llm_safety.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_faq_translation.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.6.md: passed
  - git diff --check: passed
  - full pytest: not run; frontend/admin node_modules/esbuild missing and task scope says not to touch frontend
changed_files:
  - .codex/stages/tj-ruue/artifacts/tj-ruue.6.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-manager-reply-auto-faq-flow-orchestrator.md
  - src/api/telegram_webhook.py
  - src/llm/response_adapter.py
  - src/llm/safety.py
  - src/services/auto_faq.py
  - src/services/auto_faq_types.py
  - tests/test_auto_faq.py
  - tests/test_llm_safety.py
  - tests/test_response_adapter.py
  - tests/test_webhook_manager.py
---

# Summary

Implemented the combined manager reply and Auto-FAQ candidate flow.

Normal manager replies still use exactly one `response_adapter` call and do not
generate KB candidates. Explicit `faq_global` manager actions now use one
structured combined LLM call that returns `customer_message` plus an optional
English `kb_candidate`.

Auto-FAQ persistence is now confirmation-first. Candidate review runs
deterministic checks for unsafe regex matches, context-specific promises,
duplicate similarity, and confidence threshold. Passing candidates return
`needs_confirmation` and are not saved; saving is only available through the
explicit confirmed path.

The combined Auto-FAQ path uses the shared `src/llm/safety.py` routing with a
fast non-core default model, provider-side `max_tokens`, usage limits, retry,
timeout, and OpenRouter telemetry settings.

# Verification

- Context7 PydanticAI docs query: passed.
- Orchestrator code review report:
  `docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-manager-reply-auto-faq-flow-orchestrator.md`.
- `uv run --extra dev python -m pytest -s tests/test_auto_faq.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat.py tests/test_llm_safety.py tests/test_faq_translation.py -q` -> passed, `56 passed`.
- `uv run --extra dev python -m pytest -s tests/test_response_adapter.py tests/test_auto_faq.py tests/test_webhook_manager.py tests/test_llm_safety.py -q` -> passed, `46 passed`.
- `uv run --extra dev python -m pytest -s tests/test_auto_faq.py tests/test_response_adapter.py tests/test_webhook_manager.py tests/test_services_chat.py tests/test_llm_safety.py -q` -> passed, `51 passed`.
- `uv run --extra dev python -m pytest -s tests/test_faq_translation.py -q` -> passed, `5 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, `Success: no issues found in 122 source files`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.6.md` -> passed, `artifact validation OK`.
- `git diff --check` -> passed.

# Risks / Follow-ups / Explicit Defers

- No commit, push, deploy, staging mutation, production mutation, or frontend
  code change was done.
- Full pytest was not run because this fresh worktree does not have
  `frontend/admin/node_modules/esbuild`; installing it would write into the
  frontend tree, which is outside this task scope.
- This patch intentionally does not add frontend/admin UI for confirming KB
  candidates. The backend/service save path now requires explicit confirmation,
  and the Telegram manager notification tells admins the candidate was prepared
  but not saved.
