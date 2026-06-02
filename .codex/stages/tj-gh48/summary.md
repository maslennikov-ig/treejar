# Stage tj-gh48: Expected Answer Frames

Updated: 2026-06-02
Status: implementation complete locally; stage closeout verification passed
Branch: `codex/tj-gh48-expected-answer-frames-impl`
Base: fresh `origin/main` at `428deed`
Beads: `tj-gh48`, `tj-gh48.1` through `tj-gh48.7`

docs-reviewed: updated - refreshed tj-gh48 handoff, summary, artifacts, kernel
spec, eval plan, and project-index navigation/rationale for implemented
expected-answer frames.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
project-index: updated - `.codex/project-index.md` now names the
expected-answer frame matcher under `src/dialogue/`; no new route surface,
integration, verification command, or ownership boundary required a broader
index update.

## Goal

Replace narrow last-question-only routing with durable expected-answer frames in
the existing Dialogue State Kernel. The implementation teaches Noor to remember
bounded expected answers across interruptions while preserving hard escalation
paths, legacy fallback, and production shadow safety.

## Implementation Completed

Runtime files:

- `src/dialogue/state.py`: `ExpectedSlot` and `ExpectedAnswerFrame` schema,
  frame loading, and invalid-frame recovery.
- `src/dialogue/reducer.py`: push, fulfill, interrupt, expire, and bounded
  active/history reducers.
- `src/dialogue/expected_answers.py`: deterministic matcher with blockers,
  interruption detection, ambiguity handling, expiry filtering, ordinal
  source-ref matching, and required-slot fulfillment semantics.
- `src/dialogue/runner.py`: `expire_frames -> match_expected_answer -> decide`
  graph, expected-answer route/proposal trace metadata, safe payload helper,
  and fulfillment guard.
- `src/llm/engine.py`: expected-answer frame capture for product preference,
  SKU quantity, quote details, post-quote approval, and name gate prompts;
  product-preference expected-answer bridge gated to usable kernel decisions.

Tests and fixtures:

- `tests/test_dialogue_state.py`
- `tests/test_dialogue_expected_answers.py`
- `tests/test_dialogue_runner.py`
- `tests/test_dialogue_replay_fixtures.py`
- `tests/test_llm_engine.py`
- `tests/fixtures/dialogue/dialogue_state_kernel_replay.json`

Documentation:

- `docs/specs/dialogue-state-kernel.md`
- `docs/specs/dialogue-state-kernel-evals.md`
- `docs/superpowers/plans/2026-06-02-expected-answer-frames.md`
- `.codex/stages/tj-gh48/artifacts/*.md`
- `.codex/handoff.md`

## Routing Result

- Documentation: no new version-sensitive external lookup was needed during
  implementation; prior planning docs remain sufficient.
- Knowledge Graph: not configured/not relevant.
- Selected skills: `orchestrator-stage`, `task-router`,
  `superpowers:test-driven-development`,
  `superpowers:receiving-code-review`,
  `superpowers:verification-before-completion`, and `orchestration-closeout`.
- Selected agents/personas: visible `worker` subagents for matcher and runner,
  then read-only `correctness_reviewer`, `improvement_reviewer`, and
  `docs_reviewer`.
- Catalog candidates: none.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-gh48.2` | State schema and reducers | local | `src/dialogue/state.py`, `src/dialogue/reducer.py`, state tests | `tj-gh48.1` | state tests, targeted suite | complete |
| B | `tj-gh48.4` | Matcher/interruption policy | Huygens worker | `src/dialogue/expected_answers.py`, matcher tests | A interface | matcher tests, artifact validation | merged |
| C | `tj-gh48.3` | Runner graph/capture support | Rawls worker | `src/dialogue/runner.py`, runner tests | A interface | runner tests, artifact validation | merged |
| D | `tj-gh48.5` | `process_message` integration | local | `src/llm/engine.py`, engine tests | B+C | targeted engine tests | complete |
| E | `tj-gh48.6` | Replay/stress suite | local | fixtures and replay tests | B+D | replay tests, JSON validation | complete |
| F | `tj-gh48.7` | Review and closeout | local + reviewers | artifacts, docs, Beads | D+E | reviewer pass, full gates, closeout | local review complete; production E2E deferred |

## Review Findings

Accepted and fixed:

- Shadow and unallowlisted enforce frame matches must not change
  customer-visible legacy behavior. Fixed by gating frame extraction on
  `result.should_use_kernel` and `decision.side_effects_allowed`.
- Plural hard-blocker terms such as `discounts`, `returns`, `refunds`,
  `warranties`, and `guarantees` must override expected-answer frames. Fixed in
  matcher blocker terms.
- Single active-frame ordinal answers such as `the second option` must resolve
  through frame `source_refs`. Fixed with ordinal source-ref matching.
- Required slots must not be marked fulfilled after partial matches. Fixed with
  `fulfilled` and `missing_required_slots` payload fields and runner guard.
- Engine should not duplicate nested expected-answer metadata parsing. Fixed via
  `expected_answer_match_payload`.
- Frame capture was narrower than the Beads acceptance criteria. Fixed with
  deterministic capture for product preference, SKU quantity, quote details,
  post-quote approval, and name gate prompts.
- Stage docs and artifacts were stale after implementation. Updated.
- Trace-disabled expected-answer state changes were not persisted to durable
  `conversation.metadata_`. Fixed by persisting `after_state` independently of
  optional trace collection, with RED/GREEN coverage for fulfilled and expired
  frames when `trace_enabled=false`.
- The project-index closeout note falsely said no project index existed. Fixed
  the index and rationale so `.codex/project-index.md` covers expected-answer
  frame matching under `src/dialogue/`.
- Fresh review found that a shadow kernel exception would crash before the
  legacy path. Fixed with shadow-only fail-open logging and RED/GREEN coverage.
- Expired `quote_details` frames could leave stale `active_flow` and hijack a new
  product request under allowlisted enforce. Fixed by requiring a live
  quote-details context, selected items, or current assistant quote-detail prompt.
- Product-preference slot matching could fulfill negated/conflicting answers and
  the generic word `person` could falsely block capacity phrases such as
  `6 person team`. Fixed with ambiguity propagation, nearby-negation checks, and
  narrower human-request blocker phrases.
- Real product-preference frames could store `workspace_preference` as `luma` or
  `novo` instead of canonical `private` or `open`. Fixed by keeping product
  family names as aliases only.
- Allowlisted enforce product-preference answers previously returned a static
  kernel acknowledgement. Fixed so the normal agent/product path continues with
  frame-derived directives.

Rejected:

- Direct matcher import in the runner was not adopted. The lazy adapter remains
  as a compatibility/test seam; the unsafe call shape and payload handling were
  fixed and covered.
- Capturing only `product_preference` frames or marking other frame kinds
  `observed_only` was not adopted for this stage; bounded shadow telemetry for
  future frame kinds is intentional and remains guarded from customer-visible
  effects.
- Moving unallowlisted/shadow frame lifecycle updates into trace-only proposed
  state was not adopted; durable lifecycle telemetry is part of the shadow
  evaluation contract, with customer-visible behavior still gated.
- Adding a LangGraph checkpointer was not adopted; v1 persistence remains in
  `Conversation.metadata_` by design.

## Verification Evidence

Passed before review fixes:

- `OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_state.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py -v --tb=short`
  -> `264 passed`.
- `uv run --extra dev ruff check src/ tests/` -> passed.
- `uv run --extra dev ruff format --check src/ tests/` -> passed.
- `uv run --extra dev mypy src/` -> passed after type payload fix.
- Full suite initially failed only because `frontend/admin/node_modules/esbuild`
  was absent.

Environment repair:

- `npm ci` in `frontend/admin` restored frontend test dependencies; npm warned
  that local Node `v24.16.0` is outside the package engine range
  `>=22.12.0 <23`.

Passed after dependency repair:

- `OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_admin_dashboard_frontend.py -v --tb=short`
  -> `11 passed`.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/ -v --tb=short`
  -> `1207 passed, 19 skipped`.

Passed after review fixes:

- RED matcher/runner/engine review regressions failed as expected before fixes.
- RED trace-disabled persistence regressions failed as expected before fix:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py::test_dialogue_kernel_persists_expired_frame_state_without_trace tests/test_dialogue_runner.py::test_dialogue_kernel_persists_fulfilled_frame_state_without_trace -v --tb=short`
  -> failed with persisted frame status `active` instead of `expired` or
  `fulfilled`.
- GREEN trace-disabled persistence regressions:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py::test_dialogue_kernel_persists_expired_frame_state_without_trace tests/test_dialogue_runner.py::test_dialogue_kernel_persists_fulfilled_frame_state_without_trace -v --tb=short`
  -> `2 passed`.
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py -v --tb=short`
  -> `17 passed`.
- `OPENROUTER_API_KEY=dummy uv run --extra dev python -m pytest tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_llm_engine.py -v --tb=short -k "expected_answer or product_preference or dialogue_kernel"`
  -> `36 passed, 216 deselected`.
- `uv run --extra dev ruff check src/dialogue/expected_answers.py src/dialogue/runner.py src/llm/engine.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_llm_engine.py`
  -> passed.
- `uv run --extra dev ruff format --check src/dialogue/expected_answers.py src/dialogue/runner.py src/llm/engine.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_llm_engine.py`
  -> passed.
- `uv run --extra dev mypy src/dialogue src/llm/engine.py`
  -> passed.
- Fresh review-and-fix pass:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_dialogue_kernel_shadow_fail_open_uses_legacy -v --tb=short`
  failed before fix with `RuntimeError: kernel failure`, then passed.
- Fresh review-and-fix pass:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_runner.py::test_dialogue_kernel_expired_quote_details_frame_does_not_hijack_product_request -v --tb=short`
  failed before fix with `should_use_kernel=True`, then passed.
- Fresh review-and-fix pass:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_expected_answers.py::test_product_preference_frame_rejects_negated_or_conflicting_answer tests/test_dialogue_expected_answers.py::test_person_capacity_terms_do_not_block_expected_answer_frame -v --tb=short`
  failed before fix, then `tests/test_dialogue_expected_answers.py` passed with
  `9 passed`.
- Fresh review-and-fix pass:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_product_preference_frame_builder_keeps_workspace_preference_canonical -v --tb=short`
  failed before fix with `luma` instead of `private`, then passed.
- Fresh review-and-fix pass:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_product_preference_answer_after_interruption_uses_frame_when_enforced -v --tb=short`
  failed before fix with `dialogue-kernel|product_selection`, then passed through
  the normal `mock-model` path.
- Fresh targeted suite:
  `OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_state.py tests/test_dialogue_expected_answers.py tests/test_dialogue_runner.py tests/test_dialogue_replay_fixtures.py tests/test_llm_engine.py -v --tb=short`
  -> `280 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed after formatting
  `tests/test_llm_engine.py`.
- `uv run mypy src/` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  -> `1223 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` -> passed.

Canonical stage closeout:

- `OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh48`
  -> passed; full pytest inside closeout reported `1223 passed, 19 skipped`.

## Current Constraints

- Do not remove the legacy runtime.
- Keep production `dialogue_kernel_mode=shadow` unless explicit approval enables
  a narrow enforce rollout.
- Do not close #11; it remains blocked on policy answers.
- No deploy, production mutation, live WhatsApp test, production config change,
  remote merge, PR creation, or remote branch push without explicit current-task
  approval.

## Explicit Defers

- `tj-gh48.7`: production deploy, production smoke, production shadow E2E, live
  WhatsApp E2E, and any enforce rollout are deferred because this task did not
  authorize those external actions.
- GitHub #11 remains open and blocked on policy answers.
