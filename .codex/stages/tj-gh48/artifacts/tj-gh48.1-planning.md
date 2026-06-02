---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh48.1
stage_id: tj-gh48
agent_type: n/a-local
subagent_model: n/a
reasoning_effort: n/a
model_reasoning_rationale: local planning/spec package; no delegated write stream
repo: treejar
branch: codex/tj-gh48-expected-answer-frames
base_branch: origin/main
base_commit: 428deed
worktree: /home/me/code/treejar
write_zone:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - docs/superpowers/plans/2026-06-02-expected-answer-frames.md
  - .codex/stages/tj-gh48/summary.md
  - .codex/handoff.md
success_criteria:
  - Expected-answer frame spec added
  - Eval matrix updated for #47 delayed answers, ambiguity, expiry, blockers, and long-dialog stress
  - Beads epic and dependent tasks created
  - New-agent prompt prepared
selected_docs:
  - LangGraph memory and persistence docs
  - Rasa Forms slot filling and unhappy paths
  - Microsoft Bot Framework dialog state/waterfall dialogs
  - OpenAI Structured Outputs
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /home/me/.agents/skills/task-router/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/writing-plans/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
selected_agents:
  - none - this stream is local planning
catalog_candidates:
  - none - installed skills are sufficient
parallel_group: local-planning
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No delegated worktree was created for the planning package.
risk_level: medium
docs_impact: structural
docs_reviewed: updated
docs_review_notes: Updated kernel spec, eval plan, implementation plan, stage summary, and handoff for expected-answer frames.
verification:
  - python3 -m json.tool tests/fixtures/dialogue/dialogue_state_kernel_replay.json >/dev/null: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh48/artifacts/tj-gh48.1-planning.md: passed
  - bd dep cycles: passed, no dependency cycles detected
  - scripts/orchestration/run_process_verification.sh: passed
  - git diff --check: passed
changed_files:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - docs/superpowers/plans/2026-06-02-expected-answer-frames.md
  - .codex/stages/tj-gh48/summary.md
  - .codex/stages/tj-gh48/artifacts/tj-gh48.1-planning.md
  - .codex/handoff.md
explicit_defers:
  - Implementation is deferred to Beads tj-gh48.2 through tj-gh48.7.
---

# Summary

Prepared the planning package for the fundamental dialogue-memory fix. The
existing Dialogue State Kernel spec now describes durable expected-answer frames
instead of relying on only the last assistant question.

# Scope / Routing

No file-changing subagent was used. This pass is intentionally local because it
creates the source-of-truth spec, Beads graph, and handoff prompt for a new
orchestrator.

# Verification

Planning verification passed:

- JSON fixture validation passed.
- Artifact validation passed.
- Beads dependency cycle check passed.
- Process verification passed.
- `git diff --check` passed.

# Delivery / Cleanup

No merge, deploy, production E2E, or runtime config change is part of this
planning stream.

# Risks / Follow-ups / Explicit Defers

Implementation remains open under `tj-gh48.2` through `tj-gh48.7`.
