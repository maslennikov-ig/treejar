---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-q1a2-one-reply-owner/stage-manifest.json
stream_owner: tj-q1a2-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: customer-reply-runtime
public_facade: process-message-and-response-policy
bounded_acceptance: d1-through-d6-protected-replay
non_goals:
  - production-delivery
evidence:
  - none
task_id: tj-q1a2
epic_id: tj-q1a2
stage_id: tj-q1a2-one-reply-owner
session_id: tj-q1a2
milestone: one-owner-for-customer-reply-content
milestone_status: accepted
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Root-owned sequential dependency chain with one shared state contract and protected evidence boundary.
repo: treejar
branch: main
base_branch: main
base_commit: 56227dc
worktree: /home/me/code/treejar
write_zone:
  - reply-policy-runtime-tests-and-corpus-bridge
success_criteria:
  - D1-D6 pass their Beads acceptance and the frozen replay is explained without re-baselining.
  - Dialogs 819 and 789 pass the bounded unanchored live-repair acceptance.
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/specs/2026-08-12-one-owner-for-what-the-reply-says.md
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - test-driven-development
  - verification-before-completion
  - test-pass
  - orchestration-closeout
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: local-sequential
depends_on_streams:
  - none
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Clean detached base-proof worktree at 56227dc was removed through git worktree remove.
risk_level: high
verification_tier: release
risk_tags:
  - privacy
  - state-transition
affected_surfaces:
  - backend
invariants:
  - state-transition
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage summary, artifact and handoff record the durable reply-policy state and privacy-safe evidence.
verification:
  - focused D1-D5 set: passed (960)
  - full tests/test_llm_engine.py: passed (823)
  - focused D6 and response-policy set: passed (102)
  - protected tj-t6ug baseline replay: passed as unchanged baseline aggregate 1fc87c04a645fa97
  - current protected replay: passed with aggregate c842132fde97fa2f and 56 explained changes
  - bounded D6 live replay: passed with 8 calls, 0 failures, 0 stubs and notifications disabled
  - uv run ruff check src/ tests/ scripts/: passed
  - uv run ruff format --check src/ tests/ scripts/: passed (451 files)
  - uv run mypy src/: passed (174 files)
  - scripts/orchestration/run_process_verification.sh: passed
  - uv run pytest tests/ -v --tb=short: passed (3640 passed, 19 skipped)
changed_files:
  - .codex/goals/tj-q1a2/scope-criterion-snapshot.json
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-q1a2-one-reply-owner/stage-manifest.json
  - .codex/stages/tj-q1a2-one-reply-owner/summary.md
  - .codex/stages/tj-q1a2-one-reply-owner/artifacts/tj-q1a2.md
  - scripts/corpus_bridge/replay_policy_chain.py
  - scripts/corpus_bridge/replay_repair_judge.py
  - src/llm/catalog_planning.py
  - src/llm/engine.py
  - src/llm/message_processor.py
  - src/llm/opening_guard.py
  - src/llm/repair_judge.py
  - src/llm/response_policy.py
  - src/llm/response_runtime.py
  - src/llm/sales_turn_guard.py
  - src/llm/verified_answers.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - tests/test_llm_engine.py
  - tests/test_llm_repair_judge.py
  - tests/test_llm_response_guard_declarations.py
  - tests/test_llm_response_policy_guards.py
  - tests/test_opening_guard.py
  - tests/test_sales_turn_guard.py
explicit_defers:
  - tj-2m5m.4 remains separate out-of-scope discovery work.
---

# Summary

D1-D6 now give state one owner for customer-facing reply content. Identity
deduplication is sentence-bounded, current-message names and the sent name ask
are explicit state, and prompt plus guards share one permitted-ask set. The
repair judge is unanchored and deterministic grounding repair is the safe
fallback, with escalation only for an opening-plus-question stub.

# Scope / Routing

This was a root-owned sequential stream because D2-D6 consume state contracts
introduced by their predecessors and all six share one protected replay. No
subagent was used. No corpus text entered the working tree.

# Verification

The frozen baseline remained `1fc87c04a645fa97`; current aggregate is
`c842132fde97fa2f`. The 56 changes are individually accounted for below. Codes:
`I` removes one duplicate company-identity sentence; `N` suppresses a name ask
from a current-message name; `Q` drops surplus asks under
`only_asks_were_dropped`.

- `tj-vz7o-luna-glm-20260810`: 28 I+N; 116 I+Q; 293 I+Q; 366 Q; 420 Q; 421
  I+Q; 436 I+Q; 442 Q; 692 I+Q; 789 I; 807 I+Q; 819 Q; 867 I+Q; 875 N; 1000 Q;
  1022 I+Q; 1067 Q; 1217 I+Q; 1291 I+Q.
- `tj-vz7o-luna-glm-20260810-rerun`: 28 I+N; 116 I+Q; 293 I+Q; 366 Q; 420 Q;
  421 I+Q; 436 I+Q; 442 Q; 692 I+Q; 789 I; 807 Q; 819 Q; 867 I+Q; 875 N;
  1000 I+Q; 1022 Q; 1067 Q; 1217 I+Q; 1291 Q.
- `tj-rt7w-luna-glm-20260811`: 28 I+N; 116 I+Q; 293 I+Q; 366 Q; 421 I+Q;
  436 Q; 442 I+Q; 692 Q; 789 I+Q; 807 I+Q; 819 Q; 867 I+Q; 875 I+N; 1000 Q;
  1022 I+Q; 1067 Q; 1217 I+Q; 1291 I+Q.

For every `Q` change the unchanged `REDUCING` proof reported
`only_asks_were_dropped=true`. Dialogs 28, 436, 789, 875 and 1291 were also
read individually against the protected text; their user-visible before/after
is reported outside Git.

D6 used eight of the approved twenty calls, four per dialog. All calls had
notifications disabled. Dialog 819 produced substantive fallback four times
without handoff; dialog 789 produced the exact defined no-answer shape and
handed off four times. There were no failures or unusable stubs, and no judge
correction was byte-identical to its deterministic candidate.

# Delivery / Cleanup

Root acceptance passed in the main worktree. The clean detached base-proof
worktree was removed through Git after its frozen replay was accepted. No
remote, deployment, runtime or model-config action is permitted.

# Risks / Follow-ups / Explicit Defers

No in-scope product debt is deferred. `tj-2m5m.4` remains a separate Beads
discovery item. The live proof covers exactly the two stored repair-path dialogs;
no claim is made beyond that bounded evidence.
