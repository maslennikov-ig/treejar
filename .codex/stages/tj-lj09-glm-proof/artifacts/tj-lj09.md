---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-lj09-glm-proof/stage-manifest.json
stream_owner: tj-lj09-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: production-reply-path
public_facade: review_flagged_reply
non_goals:
  - new-measured-round
  - deploy
  - second-vendor-change
evidence:
  - replayed-request-digest-matches-the-round
  - twelve-live-calls-across-five-configurations
task_id: tj-lj09
epic_id: tj-lj09
stage_id: tj-lj09-glm-proof
session_id: tj-lj09-glm-proof
milestone: the-record-now-names-the-cause-it-measured
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned change on the shared path-policy boundary with live paid calls
repo: treejar
branch: main
base_branch: main
base_commit: 28a150d
worktree: /home/me/code/treejar
write_zone:
  - src/llm/safety.py
  - tests/test_llm_repair_judge.py
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - .codex
success_criteria:
  - failure-class-measured-not-assumed
  - budget-set-from-measurement
  - retired-hypothesis-removed-from-code-and-report
selected_docs:
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
selected_skills:
  - orchestrator-stage
  - superpowers-systematic-debugging
selected_agents:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-0s42
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch exists
risk_level: high
verification_tier: release
risk_tags:
  - authorization
affected_surfaces:
  - backend
invariants:
  - the-replayed-request-is-the-one-that-failed
  - a-failure-is-classified-before-it-is-blamed
  - the-budget-holds-the-measured-worst-case
  - two-attempts-fit-inside-the-old-single-attempt-budget
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: the round report now carries the measured cause; the handoff records the budget and the inert reasoning switch
verification:
  - request digest a39e8bd07e400c26 rebuilt from the round's stored state and identical to the recorded one
  - 800 tokens - 0 of 2 succeeded, both UnexpectedModelBehavior classified judge_output_invalid
  - 1200 with vendor reasoning left on - 1 of 2 succeeded
  - 1200 with reasoning disabled - 2 of 2 succeeded, completion 906 and 958
  - 2000 with reasoning disabled - 4 of 4 succeeded, completion 720 to 1494, latency 9.35s to 15.33s
  - reasoning effort low and reasoning max_tokens 256 - 2 of 2 each, completion 1423 to 1440, no reduction
  - focused green - 62 repair-judge and safety tests passed
  - uv run ruff check src/ tests/ scripts/ - passed
  - uv run ruff format --check src/ tests/ scripts/ - passed
  - uv run mypy src/ - passed
  - uv run pytest tests/ -v --tb=short - 3619 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh - passed
changed_files:
  - .codex/handoff.md
  - .codex/goals/tj-lj09/scope-criterion-snapshot.json
  - .codex/orchestrator.toml
  - .codex/stages/tj-0s42-repair-retry/summary.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-lj09-glm-proof/stage-manifest.json
  - .codex/stages/tj-lj09-glm-proof/summary.md
  - .codex/stages/tj-lj09-glm-proof/artifacts/tj-lj09.md
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - src/llm/safety.py
  - tests/test_llm_repair_judge.py
explicit_defers:
  - none
---

# Summary

The repair call that failed on 2026-08-11 was replayed against the live vendor
from the round's own stored request, matching the recorded digest byte for
byte. The provider was never down. Every failure is our output schema
rejecting a truncated answer, because a complete answer from this model costs
720-1494 completion tokens and the path allowed 800. The budget is now 2000,
confirmed over four consecutive successes.

# The hypothesis that was wrong

`tj-0s42` guessed that disabling reasoning would fix this and said plainly it
was unproved. It was: asking `z-ai/glm-5.2` not to think changes nothing.
`enabled: false`, `effort: low` and `reasoning.max_tokens: 256` all leave
completion around 1430 tokens. Roughly 300 of those are the JSON the schema
wants; the remainder is reasoning the vendor bills for and never returns.

What that means for the codebase is narrow and worth stating: a reasoning
switch is a request, not a guarantee, so a path that sets one must still budget
as though it were ignored. The switch stays declared, the comment and the test
now say it did not fix this, and the budget carries the weight.

# Verification

The rebuilt request matched the round's stored digest `a39e8bd07e400c26…`
exactly, so the replay is the call that failed rather than a likeness of it.
Twelve live calls: 800 tokens 0/2, 1200 with reasoning left on 1/2, 1200 with
reasoning off 2/2, 2000 with reasoning off 4/4, and two probes each at
`effort: low` and `reasoning.max_tokens: 256` that succeeded without reducing
completion. Worst observed latency 15.33s against a 20s per-call timeout. Full
suite and gates as listed in the frontmatter.

# Safety

`notify_on_failure_override=False` on every replayed call: a failing attempt on
this path pages a manager by Telegram, and a diagnostic must not do that. No
corpus text was printed, written to the scratchpad, or committed; the stored
artefacts carry token counts, digests and exception classes only.

# Delivery / Cleanup

One local commit on `main`. Paid calls: 12, $0.058492, under owner authority
given in session. No push, deploy, live mutation, or real-user message.

# Risks / Follow-ups / Explicit Defers

No defer. The budget is measured on one request; a longer question could cost
more, and the retry plus the `judge_output_invalid` class are what will surface
that rather than another silent handoff.

Raised for the owner, not decided here: a repair call costs about $0.005 while
generating the reply it repairs cost $0.000084. Repair is sixty times the price
of writing, which makes the firing rate of this path a product question.
