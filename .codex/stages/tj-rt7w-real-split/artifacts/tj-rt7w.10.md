---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rt7w-real-split/stage-manifest.json
stream_owner: tj-rt7w.10-root-implementation
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: src.llm.engine.process_message
public_facade: process_message stays a 40-line facade; process_message_impl keeps its signature
bounded_acceptance: behaviour-preserving; no function over 300 lines; no closure in the file
non_goals:
  - retiring deterministic routes
  - any behaviour or rubric change
  - the paired measured round, which is tj-rt7w.7
evidence:
  - none
task_id: tj-rt7w.10
epic_id: tj-rt7w
stage_id: tj-rt7w-real-split
session_id: cut-back-the-over-complication
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: cross-module state threading on the product's hottest path
repo: treejar
branch: main
base_branch: main
base_commit: 19556ba
worktree: /home/me/code/treejar
write_zone:
  - src/llm/message_processor.py
  - tests/test_llm_message_processor_structure.py
  - tests/test_llm_message_processor_patch_points.py
success_criteria:
  - no function in src/llm/message_processor.py over 300 lines
  - no closure anywhere in the file
  - guard and policy sources byte-identical
  - no existing test edited
  - stored raw outputs replay unchanged
  - full suite green
selected_docs:
  - none
selected_skills:
  - orchestration-bridge:orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: temporary base worktree for the replay comparison removed and pruned
risk_level: high
verification_tier: integration
risk_tags:
  - public-api
  - state-transition
affected_surfaces:
  - backend
invariants:
  - state-transition
docs_impact: refactor
docs_reviewed: updated
docs_review_notes: stage summary and handoff record the split, its bound, and the one regression it caused
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -q: passed (3557 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - protected raw-output replay at 19556ba vs tip: passed (31 outputs, identical digest)
changed_files:
  - src/llm/message_processor.py
  - tests/test_llm_message_processor_structure.py
  - tests/test_llm_message_processor_patch_points.py
explicit_defers:
  - tj-rt7w.7: the paired measured round, which needs current owner authority for paid calls
  - tj-rt7w.14: the R2 bound has no semantic half; a fix owes a measured round under R5
---

# Summary

`tj-rt7w.6` reported `process_message: 40 lines`. True, and it said nothing:
the forty lines delegate to a sequence that was 2,044 lines with fifteen
closures in a new file. This is the split it reported.

The state came first because everything else waited on it. `_Turn` holds the
fourteen locals that crossed every boundary and the six builders that closed
over them; `_TurnConfig` holds the seven config reads; `_QuoteFacts` holds the
twenty-two quote facts. Several of those values are reassigned while the turn
runs, so nothing could be bound early — which is exactly what kept the sequence
in one body. `opening_anchor_line` was a one-element list for that reason and
is a field now.

The sequence is eleven phase functions, each returning the reply or `None`.
Longest 259 lines; `process_message_impl` is 163.

# Scope / Routing

Root-owned on `main`. Named reason for local execution:
`delegation.inline_subagents_allowed = false` and no visible spawned subagents
in this runtime, so the stage skill's delegation result is local ownership.
Three commits, one per step: `c9d22f9`, `e600a55`, `190a462`.

# Verification

Ruff, format, Mypy and the full suite pass on the tip. Process verification
passes. The stored raw assistant outputs from the protected acceptance run
re-render through the full policy chain to an identical digest at `19556ba` and
at the tip — 31 outputs, not the twenty earlier stages cited. Guard, policy,
catalog-planning, response-runtime, order-quote-route and engine sources are
byte-identical: the whole stage changes one source file.

Both new assertions were confirmed red before green.

# Delivery / Cleanup

Accepted directly in the root worktree. The temporary detached worktree used
for the before/after replay is removed and pruned. No push, PR, merge, deploy,
production or staging mutation, model-configuration change, paid call, or
real-user message occurred.

# Risks / Follow-ups / Explicit Defers

Hoisting `from src.core.config import get_system_config` to module level broke
twelve tests: they patch `src.core.config.get_system_config`, and the
import-time binding froze the real function. They failed loudly only because
the mocked session returns coroutines — a stricter mock would have passed while
testing nothing. The import is back inside the two calls that use it, and
`tests/test_llm_message_processor_patch_points.py` now derives the general rule
from the suite, so the next one is caught by a test rather than by luck.

`tj-rt7w.7` is unblocked and open. It needs current owner authority for its
20 Luna + 20 GLM calls; none were made here.
