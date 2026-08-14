---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-dak8-loosen-opening/stage-manifest.json
stream_owner: tj-dak8-loosen-opening-root
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: customer-facing first turn
public_facade: src/llm/opening_guard.apply_opening_guard
bounded_acceptance: who writes the first-turn opening, and how much fixed text rides with it
non_goals:
  - the client rubric, the applicability map and the harness language threshold
  - the accepted stages tj-final27-client-handoff and tj-l6pw-outbound-guard-repair
  - tj-jlx4
evidence:
  - none
task_id: tj-dak8
epic_id: n/a
stage_id: tj-dak8-loosen-opening
session_id: tj-dak8
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root executed locally; one cohesive guard and directive change with a blind reading only the root may perform
repo: treejar
branch: main
base_branch: main
base_commit: db55e1f0b498273547fafd5403804f70facf1b6e
worktree: /home/me/code/treejar
write_zone:
  - src/llm/opening_guard.py
  - src/llm/outbound_reply_guard.py
  - src/dialogue/claim_contract.py
  - src/llm/engine.py
  - docs/root-reading-convention.md
success_criteria:
  - a first turn that introduces us itself keeps its own words
  - a first turn that does not still receives the fixed sentence
  - a paired round shows 20/20 customer language and zero critical failures
  - the protected replay is re-pinned only under explicit owner authority
selected_docs:
  - none
selected_skills:
  - none
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
cleanup_notes: primary worktree; no stage branch or worktree was created, so nothing remained to remove
risk_level: medium
verification_tier: delta
risk_tags:
  - state-transition
affected_surfaces:
  - backend
invariants:
  - state-transition
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: handoff current truth, reading convention extended, stage summary added
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -q --tb=line: passed
  - uv run python -m scripts.corpus_bridge.replay_policy_chain --convention raw: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/llm/opening_guard.py
  - src/llm/outbound_reply_guard.py
  - src/dialogue/claim_contract.py
  - src/llm/engine.py
  - docs/root-reading-convention.md
  - tests/test_opening_guard.py
  - tests/test_dialogue_consultative_opening.py
  - tests/test_llm_engine.py
  - tests/test_llm_response_guard_declarations.py
  - .codex/handoff.md
  - .codex/orchestrator.toml
explicit_defers:
  - tj-wvuk (P3): the anchor lands after the discovery question; recorded, not fixed
  - tj-c58g: an internal SKU string reaching the customer on dialog 1067
  - rule 7 -0.15 is deliberately not chased; chasing it restores the ban this stage removed
---

# Summary

The fixed first-turn opening stopped being unconditional. When the model has
already greeted the customer, named itself and said what Treejar does, its own
sentences stand. When it has not, the fixed sentence arrives as before, which is
what makes the loosening safe: that sentence measured zero in 26 transcripts of
26 while it was only a request. The directive was rewritten to ask for the
introduction rather than to promise one, and the anchor's low-stock
qualification became a clause of the price instead of a second paragraph.

# Scope / Routing

Write zone was the opening guard, the outbound boundary it shares a fold with,
the consultative directive and its call site, plus the reading convention the
round is scored against. The client rubric, the applicability map and the
language threshold were not touched.

# Verification

All commands above ran in this worktree. Full pytest returned 3846 passed, 20
skipped, 0 failed. The measured round `tj-loosen1-round-20260814e` cost
`$0.004955` over 20 generation calls with no repair, scoring or second-reader
call, and returned 20/20 customer language with zero critical failures. The
protected replay was re-pinned to `caaa8e44…` under explicit owner authorization
because the change alters how every first turn renders; the 2026-08-11 baseline
is retained untouched.

# Delivery / Cleanup

Delivered to `main` under explicit owner authorization on 2026-08-14. No stage
branch or worktree to clean.

# Risks / Follow-ups / Explicit Defers

Rule 7 lost 0.15 because three replies of twenty now say what Treejar does
twice. That is the cost the owner accepted for removing the ban, and it is
fifteen words of ordinary sales copy rather than a defect a customer would act
on. The residual items are listed above; none is critical and none blocks the
client package.
