---
task_id: tj-19ol.3.13
stage_id: tj-19ol.3
repo: treejar
branch: codex/tj-19ol-3-13-order-handoff-guard
base_branch: main
base_commit: cb52133bedf68b0320b4a62966aee23498c25fa9
worktree: unknown
status: accepted_and_integrated
verification:
  - git diff --check: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - TMPDIR=/home/me/code/treejar/.tmp timeout 900s uv run pytest tests/ -v --tb=short: passed (463 passed, 19 skipped)
changed_files:
  - src/llm/engine.py
  - src/llm/order_handoff.py
  - tests/test_dialog_scenarios.py
  - tests/test_llm_engine.py
  - tests/test_llm_order_handoff.py
---

# Summary

Accepted child `tj-19ol.3.13` added a narrow first-turn concrete-order detector and bounded handoff-only retry path so hosted runtime requests such as `"I need 200 chairs delivered to Dubai Marina by next week"` escalate reliably instead of falling back to a normal qualifying reply.

# Verification

The delegated stream passed `git diff --check`, Ruff lint/format checks, `mypy`, and the full pytest suite recorded in the original report (`463 passed, 19 skipped`).

# Risks / Follow-ups

The detector is intentionally narrow and does not try to solve every geography or product-phrasing variant. Acoustic/no-exact-match quality and `/opt/noor` rebuild drift remain separate follow-ups outside this child task.
