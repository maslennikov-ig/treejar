Target: Codex worker in `/home/me/code/treejar/.worktrees/tj-av22-alert-cooldown`.

Goal: resolve Beads bug `tj-av22.1.1` so runtime-alert cooldown is retained only
after a confirmed Telegram delivery.

Success criteria:
- incomplete configuration and transport/no-op failures do not consume the
  cooldown claim;
- confirmed delivery retains deduplication;
- deterministic tests cover both outcomes without external calls;
- focused quality gates pass and the worker artifact is complete.

Context: read `AGENTS.md`, `.codex/orchestrator.toml`, the Bead, and the runtime
monitoring/notification code and tests. The independent stabilization review
identified this as a P2 reliability gap.

Constraints: work only on this outcome in the assigned worktree. Choose the
implementation that best fits the existing notification contract. Preserve
unrelated changes and do not contact Telegram or production. Use
`systematic-debugging`, `test-driven-development`, and
`verification-before-completion` as relevant.

Asset Routing:
- selected skills: systematic-debugging, test-driven-development,
  verification-before-completion
- selected agents/personas: none; this is the owned worker stream
- catalog candidates: none; installed skills cover the task

Documentation: no dependency research is expected. Review the operations
runbook and update it only if the observable operator contract changes.

Output: commit the implementation and tests, then write
`.codex/stages/tj-av22/artifacts/tj-av22.1.1.md` with findings, changed files,
verification, residual risk, commit SHA, and `docs-reviewed`. Report completion
through `scripts/orchestration/report_child_completion.py`.

Stop: return with evidence if the fix would require external traffic,
production changes, credentials, or edits outside this narrow outcome.
