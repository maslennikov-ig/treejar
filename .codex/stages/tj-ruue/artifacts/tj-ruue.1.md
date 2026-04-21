---
task_id: tj-ruue.1
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-safety-layer-v2
base_branch: origin/main
base_commit: 9ef78006a6a6055fa4786f1a856b422cb916dabb
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-safety-layer-v2
status: accepted
verification:
  - Context7 PydanticAI docs query: passed
  - Context7 OpenRouter docs query: passed
  - uv run python -m pytest -s targeted safety/callsite tests -v --tb=short: passed
  - uv run python -m pytest -s relevant LLM/quality/followup tests -v --tb=short: passed
  - uv run python -m pytest -s tests/ -v --tb=short: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.1.md: passed
  - git diff --check: passed
changed_files:
  - src/core/config.py
  - src/llm/conversation_summary.py
  - src/llm/engine.py
  - src/llm/response_adapter.py
  - src/llm/safety.py
  - src/quality/evaluator.py
  - src/quality/manager_evaluator.py
  - src/services/auto_faq.py
  - src/services/followup.py
  - tests/test_auto_faq.py
  - tests/test_llm_conversation_summary.py
  - tests/test_llm_engine.py
  - tests/test_llm_safety.py
  - tests/test_manager_evaluator.py
  - tests/test_quality_evaluator.py
  - tests/test_response_adapter.py
  - tests/test_services_followup_details.py
---

# Summary

Accepted the manual worker implementation for the LLM safety layer. The patch adds central per-path PydanticAI safety policy, injects provider-side `ModelSettings(max_tokens=...)` into all current PydanticAI call sites, keeps core sales/followup paths free of non-core budget blocking and usage limits, bounds non-core paths to one safe retry total, adds a primitive non-core budget blocker, and routes final failure/budget-block events through a narrow admin notification adapter.

Covered call sites:

- `src/quality/evaluator.py`
- `src/quality/manager_evaluator.py`
- `src/llm/engine.py`
- `src/services/followup.py`
- `src/llm/conversation_summary.py`
- `src/llm/response_adapter.py`
- `src/services/auto_faq.py`

# Verification

Worker verification:

- Context7 PydanticAI/OpenRouter docs checked and recorded.
- Targeted safety/call-site pytest: 21 passed.
- Relevant LLM/quality/followup pytest: 116 passed.
- Full suite with capture disabled: 664 passed, 19 skipped.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- Artifact validator: passed.

Orchestrator review verification:

- Re-read the artifact and diff in `/home/me/code/treejar/.worktrees/codex-tj-ruue-safety-layer-v2`.
- `uv run python -m pytest -s tests/test_llm_safety.py ... -v --tb=short`: 21 passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.1.md`: passed in worker worktree.
- `uv run ruff check src/ tests/`: passed in worker worktree.
- `uv run ruff format --check src/ tests/`: passed in worker worktree.
- `uv run mypy src/`: passed in worker worktree.
- `git diff --check`: passed in worker worktree.

# Risks / Follow-ups / Explicit Defers

- The accepted worker branch was committed as `72cde7c` (`feat(llm): add provider-side safety controls`). The runtime/test files were integrated into `codex/live-triage-20260417` and committed as `0404bfc` (`feat(llm): add OpenRouter cost safety layer`).
- Standard pytest capture fails locally before executing tests with `_pytest/capture.py FileNotFoundError`; worker verified the same tests with `-s`.
- Full pytest required `npm ci` in `frontend/admin` for missing `esbuild`; npm reported existing Node/audit warnings. No frontend code was changed.
- Durable DB/Redis attempt state, real daily budget accounting, OpenRouter cache telemetry persistence, and admin controls remain deferred to follow-up tasks.
