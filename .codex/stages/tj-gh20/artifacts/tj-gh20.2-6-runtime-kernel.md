---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh20.2-6
stage_id: tj-gh20
repo: treejar
branch: codex/tj-gh20-dialogue-state-kernel
base_branch: origin/main
base_commit: f22545b7260e
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh20-dialogue-state-kernel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Runtime work was integrated in the stage worktree; no child branch cleanup was required.
risk_level: high
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py tests/test_dialogue_catalog_refs.py tests/test_dialogue_state.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py::test_dialogue_kernel_shadow_records_verified_policy_handoff_route tests/test_llm_engine.py::test_dialogue_kernel_enforce_quote_details_stores_legacy_metadata tests/test_llm_engine.py::test_process_message_dialogue_kernel_shadow_records_trace_and_uses_legacy tests/test_llm_engine.py::test_process_message_dialogue_kernel_enforce_name_gate_before_llm -v --tb=short: passed, 31 passed
  - uv run ruff check src/dialogue src/core/config.py src/llm/engine.py tests/test_dialogue_state.py tests/test_dialogue_catalog_refs.py tests/test_dialogue_runner.py tests/test_dialogue_config.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py: passed
  - uv run ruff format --check src/dialogue src/core/config.py src/llm/engine.py tests/test_dialogue_state.py tests/test_dialogue_catalog_refs.py tests/test_dialogue_runner.py tests/test_dialogue_config.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py: passed
  - uv run mypy src/dialogue src/core/config.py: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - git diff --check: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1098 passed, 19 skipped
changed_files:
  - pyproject.toml
  - uv.lock
  - src/core/config.py
  - src/dialogue/__init__.py
  - src/dialogue/state.py
  - src/dialogue/reducer.py
  - src/dialogue/catalog_refs.py
  - src/dialogue/runner.py
  - src/llm/engine.py
  - tests/test_dialogue_config.py
  - tests/test_dialogue_state.py
  - tests/test_dialogue_catalog_refs.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_replay_fixtures.py
  - tests/test_llm_engine.py
explicit_defers:
  - tj-gh20.7: deploy only in shadow mode after explicit approval.
---

# Summary

Accepted the local runtime implementation for `tj-gh20.2` through `tj-gh20.6`.

The implementation adds a LangGraph-backed runner, Pydantic state and trace
models, pure reducer helpers, deterministic SKU/model parsing, and a guarded
bridge from `process_message`. Default `legacy` mode short-circuits before graph
execution. `shadow` records bounded traces only. `enforce` is allowlist-driven
and deliberately falls back to legacy for exact SKU+quantity selection until a
later stage can own stock, pricing, and quotation side effects end to end.

# Verification

- RED tests were added and observed failing for the accepted review findings:
  legacy graph invocation, missing customer-name hydration, unsafe quantity
  selection interception, missing legacy post-quotation metadata hydration, and
  missing verified-policy legacy-route tracing.
- The targeted runtime suite passed with `31 passed`.
- Targeted static checks passed.

# Delivery / Cleanup

Runtime work is accepted in the stage branch but has not been merged, pushed, or
deployed. No production runtime config was changed.

# Risks / Follow-ups / Explicit Defers

- Process verification and stage closeout are tracked at stage level after
  artifact refresh.
- `tj-gh20.7` remains the delivery/shadow E2E task and is not included in local
  implementation completion.
