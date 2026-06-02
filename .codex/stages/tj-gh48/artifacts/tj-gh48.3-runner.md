---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh48.3
stage_id: tj-gh48
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: runner graph sequencing affects shadow/enforce behavior and fallback safety
repo: treejar
branch: codex/tj-gh48-runner
base_branch: codex/tj-gh48-expected-answer-frames-impl
base_commit: 17d21f966bd123bd74f0007162270b9f2c0fab03
worktree: /home/me/code/treejar/.worktrees/tj-gh48-impl/.worktrees/tj-gh48-runner
write_zone:
  - src/dialogue/runner.py
  - tests/test_dialogue_runner.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.3-runner.md
success_criteria:
  - Add RED runner tests first and verify expected failure.
  - Add explicit expire_frames -> match_expected_answer -> decide graph nodes.
  - Age and expire active expected-answer frames before decide using reducer lifecycle APIs.
  - Handle high-confidence allowlisted product_selection/product_preference_answer expected-answer matches in enforce.
  - Fall back to legacy for unallowlisted expected-answer matches.
  - Record bounded expected-answer match/proposal metadata in shadow trace with no customer-visible side effects.
  - Keep existing runner tests green.
selected_docs:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - docs/superpowers/plans/2026-06-02-expected-answer-frames.md
selected_skills:
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - worker
catalog_candidates:
  - none
parallel_group: C
depends_on_streams:
  - B matcher module sibling stream at merge time
parallel_decision: parallel
status: merged
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Merged into codex/tj-gh48-expected-answer-frames-impl; child worktree removed after clean status.
risk_level: medium
docs_impact: none
docs_reviewed: no-change-needed
docs_review_notes: Existing specs already describe expected-answer frames and runner graph; this stream only implements the runner scaffolding.
verification:
  - "RED OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_runner.py::test_dialogue_kernel_graph_orders_expected_answer_steps tests/test_dialogue_runner.py::test_dialogue_kernel_expires_expected_answer_frames_before_match tests/test_dialogue_runner.py::test_dialogue_kernel_enforce_handles_allowlisted_expected_answer_match tests/test_dialogue_runner.py::test_dialogue_kernel_unallowlisted_expected_answer_match_falls_back_to_legacy tests/test_dialogue_runner.py::test_dialogue_kernel_shadow_records_bounded_expected_answer_trace -v --tb=short": failed_expected
  - "OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_runner.py -v --tb=short": passed
  - "uv run --extra dev ruff check src/dialogue/runner.py tests/test_dialogue_runner.py": passed
  - "uv run --extra dev ruff format --check src/dialogue/runner.py tests/test_dialogue_runner.py": passed
  - "uv run --extra dev mypy src/dialogue/runner.py tests/test_dialogue_runner.py": passed
changed_files:
  - src/dialogue/runner.py
  - tests/test_dialogue_runner.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.3-runner.md
explicit_defers:
  - none
---

# Summary

Added runner graph scaffolding for expected-answer frames. The graph now ages and expires frames, calls a lazy matcher adapter, then decides with a bounded expected-answer proposal path.

# Scope / Routing

The change stayed within the assigned runner stream write zone. It did not create `src/dialogue/expected_answers.py`, edit engine integration, or modify state/reducer APIs.

# Verification

RED was verified first: the five new focused runner tests failed because the graph only had `decide`, matcher was not called, allowlisted expected-answer handling did not occur, and shadow trace metadata was absent.

GREEN verification passed with the full runner test file, ruff check, ruff format check, and an extra targeted mypy run over the touched files.

# Delivery / Cleanup

Merged into `codex/tj-gh48-expected-answer-frames-impl` with merge commit
`8d3380c`. The child worktree was clean and was removed after integration.

# Risks / Follow-ups / Explicit Defers

No explicit defers remain for this stream. Integration confirmed the matcher
payload contract, then review fixes added `fulfilled` and
`missing_required_slots` to prevent premature frame fulfillment.
