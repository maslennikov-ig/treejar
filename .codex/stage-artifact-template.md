---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: <task-id>
stage_id: <stage-id>
repo: <repo-or-n/a>
branch: <branch>
base_branch: <base-branch>
base_commit: <base-commit-or-unknown>
worktree: <absolute-path-or-unknown>
status: <returned|accepted|merged|blocked>
delivery_method: <merge|cherry-pick|manual integration|not accepted|n/a>
accepted_by_orchestrator: <yes|no>
cleanup_status: <pending|cleaned|blocked|not_applicable>
cleanup_notes: <short cleanup result or blocker>
risk_level: <low|medium|high>
verification:
  - <command>: <passed|failed|blocked>
changed_files:
  - <path>
explicit_defers:
  - <none|bead-id-and-reason>
---

# Summary

Short outcome summary.

# Verification

List the commands that were actually run and the result.

# Delivery / Cleanup

Record how the orchestrator accepted or rejected the stream, then record the safe-only cleanup result. Use `accepted-content, not-git-merged; manual cleanup required` when work was accepted through cherry-pick or manual integration but the child branch is not Git-merged.

# Risks / Follow-ups / Explicit Defers

List residual risks, blockers, explicit next steps, and any justified defer.
Do not leave silent technical debt behind this artifact.
