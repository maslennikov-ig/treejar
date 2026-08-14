---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-l6pw-outbound-guard-repair/stage-manifest.json
stream_owner: tj-l6pw-outbound-guard-repair-root
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: customer-facing reply path
public_facade: src/llm/outbound_reply_guard.finalize_customer_reply_text
bounded_acceptance: the outbound language boundary and the first-turn question it may remove
non_goals:
  - model prompt, rubric, applicability map or harness language threshold
  - the accepted stage tj-final27-client-handoff and its measured round
  - tj-jlx4
evidence:
  - none
task_id: tj-l6pw
epic_id: n/a
stage_id: tj-l6pw-outbound-guard-repair
session_id: tj-l6pw
milestone: cohesive-vertical-slice
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root executed locally; single cohesive guard change with no parallel benefit
repo: treejar
branch: main
base_branch: main
base_commit: c70e7e9eeb103661fade5fa021e77d83af651b9d
worktree: /home/me/code/treejar
write_zone:
  - src/llm/language_guard.py
  - src/llm/outbound_reply_guard.py
  - src/llm/opening_guard.py
  - tests/test_llm_outbound_reply_guard.py
success_criteria:
  - an Arabic reply naming Latin-script catalog rows, a price or a link reaches the customer unchanged
  - an English reply still may not carry Arabic script
  - a first turn that loses its only question to the guard receives one back in the selected language
  - the protected raw replay does not move
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
cleanup_status: not_applicable
cleanup_notes: work performed in the primary worktree; no stage branch or worktree created
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
docs_review_notes: handoff current truth, one-question wording corrected, new stage summary added
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -q --tb=short: passed
  - uv run pytest tests/test_llm_outbound_reply_guard.py -q: passed
  - uv run python -m scripts.corpus_bridge.replay_policy_chain --convention raw: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/llm/language_guard.py
  - src/llm/outbound_reply_guard.py
  - src/llm/opening_guard.py
  - tests/test_llm_outbound_reply_guard.py
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-l6pw-outbound-guard-repair/summary.md
  - .codex/stages/tj-l6pw-outbound-guard-repair/stage-manifest.json
  - .codex/goals/tj-l6pw/scope-criterion-snapshot.json
explicit_defers:
  - tj-s6ah, tj-gwg1, tj-2f1u, tj-c58g, tj-q88k: opening defect forms the accepted round named; none critical
  - tj-jlx4: excluded by the owner
---

# Summary

The audit of the accepted stage found that the new language boundary judged an
Arabic reply by its share of Arabic letters. Our catalog is named in Latin
script, so a true Arabic answer that named three products, quoted a price or
carried a link failed that test and the customer received a fixed sentence
instead of the answer. The boundary now decides per side: an Arabic reply keeps
the customer's language when it carries Arabic of its own, and an English reply
still may not carry Arabic script. When the removed second-language sentence was
the only place a first turn asked anything, one work-led question is restored in
the selected language and folded into the name ask.

# Scope / Routing

Write zone was the three guard modules and their focused test file, plus the
orchestration documents. No prompt, rubric, applicability map or harness
threshold was touched, and the accepted stage was not edited.

# Verification

Every command above ran in this worktree. Full pytest returned 3842 passed, 20
skipped, 0 failed against the deployed 3832/20/0, and the difference is exactly
this stage's focused cases. Replaying the shipped output path over the stored
round `tj-08ve-round-20260814c` cost nothing and returned 18 of 20 replies
byte-identical, with dialogs 293 and 1291 each gaining one work-led question.
The protected raw replay stayed at `1b425bd1…` against `1fc87c04…` with the same
seven expected differences.

# Delivery / Cleanup

Delivered to `main` under explicit owner authorization on 2026-08-14 as
`6921673` and `d30b2d9`, deployed by GitHub Actions run `31811997412`, with an
exact `/api/v1/health` SHA readback. No stage branch or worktree to clean.

# Risks / Follow-ups / Explicit Defers

The fallback still exists and still replaces a reply written wholly in the wrong
language; that is intended. An English reply to an Arabic customer that quotes a
price is now kept rather than replaced, because losing the price costs the
customer more than reading it in English. Five bounded opening defects are
tracked and deferred as listed above.
