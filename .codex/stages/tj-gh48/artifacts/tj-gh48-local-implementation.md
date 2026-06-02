---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-gh48.local-implementation
stage_id: tj-gh48
agent_type: n/a-local
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local orchestrator integration covered shared state, engine bridge, replay fixtures, review fixes, and closeout docs
repo: treejar
branch: codex/tj-gh48-expected-answer-frames-impl
base_branch: origin/main
base_commit: 428deed
worktree: /home/me/code/treejar/.worktrees/tj-gh48-impl
write_zone:
  - src/dialogue/state.py
  - src/dialogue/reducer.py
  - src/dialogue/runner.py
  - src/dialogue/expected_answers.py
  - src/llm/engine.py
  - tests/
  - docs/specs/
  - .codex/stages/tj-gh48/
  - .codex/handoff.md
success_criteria:
  - Expected-answer frame state, lifecycle reducers, matcher, runner graph, and engine bridge implemented.
  - Product-preference expected answers survive bounded interruptions in enforce allowlist mode.
  - Shadow and unallowlisted enforce modes remain telemetry-only for frame matches.
  - Replay fixtures cover immediate, delayed, ambiguous, expired, hard-blocker, and long-dialog expected-answer cases.
  - Reviewer findings are accepted or rejected with concrete reasons.
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-gh48/summary.md
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - docs/superpowers/plans/2026-06-02-expected-answer-frames.md
selected_skills:
  - orchestrator-stage
  - superpowers:test-driven-development
  - superpowers:receiving-code-review
  - superpowers:verification-before-completion
  - orchestration-closeout
selected_agents:
  - correctness_reviewer
  - improvement_reviewer
  - docs_reviewer
catalog_candidates:
  - none
parallel_group: A-D-E-F
depends_on_streams:
  - B matcher
  - C runner
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Local orchestrator stream used the implementation worktree directly; delegated child worktrees were cleaned after merge.
risk_level: medium
docs_impact: structural
docs_reviewed: updated
docs_review_notes: Specs, eval plan, stage summary, handoff, artifact metadata, and project-index closeout rationale refreshed for implemented expected-answer frames.
verification:
  - "RED matcher/runner/engine review regressions": failed_expected
  - "RED trace-disabled expected-answer persistence regressions": failed_expected
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py::test_dialogue_kernel_persists_expired_frame_state_without_trace tests/test_dialogue_runner.py::test_dialogue_kernel_persists_fulfilled_frame_state_without_trace -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py -v --tb=short": passed
  - "OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_llm_engine.py -v --tb=short -k expected_answer or product_preference or dialogue_kernel": passed
  - "OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_state.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py -v --tb=short": passed
  - "uv run --extra dev ruff check src/ tests/": passed
  - "uv run --extra dev ruff format --check src/ tests/": passed
  - "uv run --extra dev mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib} OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/ -v --tb=short": passed
changed_files:
  - src/dialogue/state.py
  - src/dialogue/reducer.py
  - src/dialogue/expected_answers.py
  - src/dialogue/runner.py
  - src/llm/engine.py
  - tests/test_dialogue_state.py
  - tests/test_dialogue_expected_answers.py
  - tests/test_dialogue_runner.py
  - tests/test_dialogue_replay_fixtures.py
  - tests/test_llm_engine.py
  - tests/fixtures/dialogue/dialogue_state_kernel_replay.json
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - docs/superpowers/plans/2026-06-02-expected-answer-frames.md
explicit_defers:
  - tj-gh48.7 rollout follow-up: no deploy, production mutation, live WhatsApp E2E, or #11 close was performed without explicit approval.
---

# Summary

Implemented the expected-answer frame stage on
`codex/tj-gh48-expected-answer-frames-impl`. The branch adds durable frame state
and reducers, deterministic matching, runner graph support, engine capture for
customer-facing questions, frame-aware product-preference handling in enforce
allowlist mode, and replay/stress coverage.

# Scope / Routing

State/reducer work was local after the fresh `origin/main` worktree was created.
Matcher and runner streams were delegated to visible Codex subagents, reviewed,
and merged. Engine bridge, replay fixtures, review fixes, docs, and closeout
were completed locally because they crossed shared routing boundaries.

Accepted reviewer findings:

- Shadow/unallowlisted frame matches must not steer live legacy behavior; fixed
  by gating engine frame extraction on usable kernel decisions.
- Plural hard blockers must override frame matches; fixed in matcher terms.
- Single-frame ordinal answers must resolve through source refs; fixed with
  ordinal source-ref matching.
- Required-slot semantics must prevent premature fulfillment; fixed with
  `fulfilled` and `missing_required_slots` payload fields.
- Engine should not parse nested runner metadata directly; fixed with
  `expected_answer_match_payload`.
- Frame capture was narrower than task acceptance; fixed with deterministic
  capture for product preference, SKU quantity, quote details, post-quote
  approval, and name gate prompts.
- Trace-disabled expected-answer frame updates must still persist durable state;
  fixed by saving `after_state` regardless of optional trace collection.
- Stage project-index rationale must not claim the repo index is absent; fixed
  to reference the existing `.codex/project-index.md` coverage for `src/dialogue/`.

Rejected reviewer finding:

- Directly importing the matcher in the runner was not adopted. The lazy adapter
  remains as a compatibility/test seam; the runtime bug was in unsafe argument
  binding and payload handling, both now covered by tests.

# Verification

RED tests were added and observed failing for the review issues before the
fixes. Focused GREEN verification passed for matcher, runner, and engine
expected-answer paths. Full local gates passed after frontend admin dependencies
were restored with `npm ci` in `frontend/admin`.

Additional RED/GREEN coverage was added for `trace_enabled=false`: expired and
fulfilled expected-answer frames now persist to `conversation.metadata_` even
when no trace is appended.

# Delivery / Cleanup

No deploy, production mutation, live WhatsApp E2E, remote push, PR creation, or
merge to `main` was performed. Delegated child worktrees were clean and removed
after merge into the implementation branch.

# Risks / Follow-ups / Explicit Defers

Production remains `dialogue_kernel_mode=shadow`; no enforce rollout was
enabled. Live WhatsApp E2E and production shadow trace comparison remain
explicitly deferred until current-task approval. GitHub #11 remains open and
blocked on policy answers.
