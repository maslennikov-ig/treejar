---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh20.1
stage_id: tj-gh20
repo: treejar
branch: codex/tj-gh20-dialogue-state-kernel
base_branch: origin/main
base_commit: f22545b7260e
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh20-dialogue-state-kernel
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Worker used the stage worktree under a strict docs/fixtures write zone; no separate child worktree cleanup was required.
risk_level: medium
verification:
  - python -m json.tool tests/fixtures/dialogue/dialogue_state_kernel_replay.json: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_dialogue_replay_fixtures.py -v --tb=short: passed
changed_files:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/dialogue-state-kernel-evals.md
  - tests/fixtures/dialogue/dialogue_state_kernel_replay.json
  - .codex/stages/tj-gh20/summary.md
explicit_defers:
  - tj-gh20.7: production shadow E2E and decision report require explicit delivery approval.
---

# Summary

Accepted Stream A documentation and replay fixtures, then updated them after
runtime review to reflect the safe v1 behavior: exact SKU+quantity turns are
recognized by the kernel but delegated to legacy until the kernel owns the full
quotation side-effect path.

# Verification

- JSON fixture validation passed.
- Replay fixture tests now validate schema and execute selected #11/#39/#40
  cases through the kernel runner.

# Delivery / Cleanup

The worker changes were accepted by direct review in the stage worktree. No
child branch merge or cleanup action was needed.

# Risks / Follow-ups / Explicit Defers

- Production shadow mode and a decision report remain in `tj-gh20.7`.
- GitHub #11 remains blocked on Lilia's answers.
