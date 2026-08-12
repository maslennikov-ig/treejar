---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-0h5d-deepseek-repair-judge/stage-manifest.json
stream_owner: tj-0h5d-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: production-reply-path
public_facade: review_flagged_reply
non_goals:
  - new-measured-round
  - deploy
  - generation-model-change
evidence:
  - shipped-config-replayed-on-both-flagged-replies
  - prompt-ablation-measured-on-both-vendors
task_id: tj-0h5d
epic_id: tj-0h5d
stage_id: tj-0h5d-deepseek-repair-judge
session_id: tj-0h5d-deepseek-repair-judge
milestone: the-judge-now-reaches-the-customer
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned change on the shared repair path with live paid calls
repo: treejar
branch: main
base_branch: main
base_commit: 7b2b659
worktree: /home/me/code/treejar
write_zone:
  - src/llm/repair_judge.py
  - src/llm/safety.py
  - tests/test_llm_repair_judge.py
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - .codex
success_criteria:
  - model-chosen-by-replay-not-reputation
  - prompt-states-the-enforced-rule
  - shipped-config-measured-end-to-end
selected_docs:
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
selected_skills:
  - orchestrator-stage
  - superpowers-systematic-debugging
selected_agents:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-lj09
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
  - the-judge-is-not-the-model-that-wrote-the-reply
  - the-prompt-states-the-rule-the-code-enforces
  - two-attempts-fit-inside-the-old-single-attempt-budget
  - deterministic-reply-chain-unchanged
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: report and handoff record the model, the prompt change, and that the judge returns the free repair verbatim
verification:
  - shipped config live on dialog 819 - 3 of 4 delivered, one 20s timeout covered by the existing retry
  - shipped config live on dialog 789 - 4 of 4 delivered
  - eight shipped-config calls cost $0.000596 at 5.6 to 10.2 seconds
  - all seven delivered replies were byte-identical to the free deterministic repair
  - ablation - prompt without the candidate paragraph delivered 2 of 4 on 819
  - cross-vendor - the shipped prompt delivered 4 of 4 on GLM 5.2 as well, so the paragraph and not the vendor carries the effect
  - focused green - 92 repair-judge, safety and acceptance-harness tests passed
  - uv run ruff check src/ tests/ scripts/ - passed
  - uv run ruff format --check src/ tests/ scripts/ - passed
  - uv run mypy src/ - passed over 174 source files
  - uv run pytest tests/ -v --tb=short - 3621 passed and 19 skipped
  - protected 60-output replay - aggregate 1fc87c04 unchanged
  - scripts/orchestration/run_process_verification.sh - passed
changed_files:
  - .codex/handoff.md
  - .codex/goals/tj-0h5d/scope-criterion-snapshot.json
  - .codex/orchestrator.toml
  - .codex/stages/tj-0h5d-deepseek-repair-judge/stage-manifest.json
  - .codex/stages/tj-0h5d-deepseek-repair-judge/summary.md
  - .codex/stages/tj-0h5d-deepseek-repair-judge/artifacts/tj-0h5d.md
  - docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md
  - src/llm/repair_judge.py
  - src/llm/safety.py
  - tests/test_llm_repair_judge.py
explicit_defers:
  - none
---

# Summary

The repair judge runs on `deepseek/deepseek-v4-flash` and the prompt now states
the rule the code has always enforced. Delivery to the customer goes from one
reply in four to seven in eight, at about a fortieth of the price.

# What the measurement actually showed

The vendor was not the problem. `review_flagged_reply` discards any correction
that still trips the guard, and the prompt never said so; it also framed
`cannot_fix` as the careful answer when it is the one that sends nothing. GLM
reworded the flagged promise and lost the reply, DeepSeek took the exit. One in
four, either way. With the rule stated it is four in four, either way.

# Verification

The shipped configuration was replayed against both flagged replies the
repository holds: 7 of 8 delivered, the single loss a 20s timeout that the
existing retry covers. Latency 5.6 to 10.2 seconds, eight calls for $0.000596.

# What is not being claimed

All seven delivered replies were byte-identical to the deterministic repair the
guard produces for free. On these two cases the paid judge adds nothing; it has
only stopped throwing the free answer away. And the paragraph that produces the
delivery rate is the same one that turns the judge into a copier: under the old
prompt GLM independently caught a delivery city the reply had invented, and
that catch is gone. Delivery was bought with independence, knowingly.

Two flagged replies, one violation class each, is the whole evidence base. The
four grounding violations that have never fired are where a judge would earn
its call, and nothing here measures that.

# Safety

Every replayed call ran with `notify_on_failure_override=False`, because a
failure on this path pages a manager by Telegram. No corpus text was printed,
written to the scratchpad, or committed.

# Delivery / Cleanup

One local commit on `main`. Paid calls: 16, $0.001960, under owner authority
given in session. No push, deploy, live mutation, or real-user message.

# Risks / Follow-ups / Explicit Defers

No defer. The generation model is untouched; only the second-vendor repair path
moved.
