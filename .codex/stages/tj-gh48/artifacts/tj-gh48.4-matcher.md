---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh48.4
stage_id: tj-gh48
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: dialogue routing correctness, ambiguity, and escalation blockers are high-risk behavior changes
repo: treejar
branch: codex/tj-gh48-matcher
base_branch: codex/tj-gh48-expected-answer-frames-impl
base_commit: 17d21f966bd123bd74f0007162270b9f2c0fab03
worktree: /home/me/code/treejar/.worktrees/tj-gh48-impl/.worktrees/tj-gh48-matcher
write_zone:
  - src/dialogue/expected_answers.py
  - tests/test_dialogue_expected_answers.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.4-matcher.md
success_criteria:
  - RED matcher tests fail for missing matcher API before implementation
  - ExpectedAnswerMatch and match_expected_answer(state, text, now=None) exist
  - product preference answer fills workspace_preference=open and routes product_preference_answer
  - bounded delivery interruption is marked interruption without frame fulfillment
  - hard blockers override expected-answer frames
  - terse ordinal across two active frames routes expected_answer_clarify with ambiguous_frame_ids
  - expired frames are ignored and fall back safely
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
parallel_group: B
depends_on_streams:
  - A
parallel_decision: local
status: returned
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: stream returned for orchestrator review
risk_level: medium
docs_impact: api-contract
docs_reviewed: no-change-needed
docs_review_notes: existing tj-gh48 specs already define expected-answer matcher API and behavior covered here
verification:
  - "OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_expected_answers.py -v --tb=short": passed
  - "uv run --extra dev ruff check src/dialogue/expected_answers.py tests/test_dialogue_expected_answers.py": passed
  - "uv run --extra dev ruff format --check src/dialogue/expected_answers.py tests/test_dialogue_expected_answers.py": passed
  - "python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-gh48/artifacts/tj-gh48.4-matcher.md": passed
changed_files:
  - src/dialogue/expected_answers.py
  - tests/test_dialogue_expected_answers.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.4-matcher.md
explicit_defers:
  - none
---

# Summary

Implemented deterministic expected-answer matching for active frames, including product-preference slot filling, bounded service interruption detection, hard-blocker precedence, terse ordinal ambiguity handling, and expiry filtering.

# Scope / Routing

The stream stayed inside the assigned write zone. No runner, engine, state, reducer, fixture, or sibling artifact files were edited. No dependency documentation lookup was needed because the implementation is repo-local Python/Pydantic logic based on the selected tj-gh48 docs.

# Verification

RED was run before implementation:

- `OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_expected_answers.py -v --tb=short` failed during collection with `ModuleNotFoundError: No module named 'src.dialogue.expected_answers'`, proving the tests targeted the missing matcher API.

GREEN and formatting checks were run after implementation:

- `OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_expected_answers.py -v --tb=short` passed, `5 passed`.
- `uv run --extra dev ruff check src/dialogue/expected_answers.py tests/test_dialogue_expected_answers.py` passed.
- `uv run --extra dev ruff format --check src/dialogue/expected_answers.py tests/test_dialogue_expected_answers.py` passed.
- `python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-gh48/artifacts/tj-gh48.4-matcher.md` passed.

# Delivery / Cleanup

Stream is ready for orchestrator review on branch `codex/tj-gh48-matcher`. Cleanup is pending orchestrator acceptance.

# Risks / Follow-ups / Explicit Defers

No explicit defers. Integration with runner/engine/state mutation belongs to sibling/sequential streams and was intentionally not implemented here.
