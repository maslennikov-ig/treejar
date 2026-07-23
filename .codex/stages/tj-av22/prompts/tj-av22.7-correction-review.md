Target: Codex reviewer in
`/home/me/code/treejar/.worktrees/tj-av22-correction-review`.

Goal: independently decide whether the seven findings in
`.codex/stages/tj-av22/artifacts/tj-av22.5.md` are resolved on the current
integration snapshot, and surface any new release-blocking regression in the
same changed surfaces.

Success criteria:
- each prior finding has a resolved or open verdict tied to current file/line
  evidence and a focused test;
- privacy, retry/idempotency, owner-safe locks, reconciliation, heartbeat, TTL,
  and alert cooldown behavior are covered;
- local evidence is kept separate from approval-gated production proof;
- one valid review artifact gives a clear release verdict.

Context: read `AGENTS.md`, `.codex/orchestrator.toml`, the prior review artifact,
Beads `tj-av22.5`, `tj-av22.6`, and `tj-av22.7`, then inspect the integrated
diff from `89f9a560071302d16f53704870e7a508e9d05f28`.

Constraints: this is a read-only code review. Choose the review order and
focused commands from risk. Do not edit code, config, tests, docs, Beads, or
runtime state. The only allowed write is the new artifact below. Do not contact
production or external services. Use the installed `code-review` and
`verification-before-completion` guidance.

Asset Routing:
- selected skills: code-review, verification-before-completion
- selected agents/personas: independent stabilization reviewer
- catalog candidates: none; installed review skills cover the task

Documentation: repository-owned contracts are sufficient; no dependency docs
are expected. Record any durable documentation mismatch as a finding.

Output: write only
`.codex/stages/tj-av22/artifacts/tj-av22.7.md`, with artifact frontmatter,
coverage, prior-finding disposition, new findings by severity, verification,
release verdict, and significant finding capture. Commit the artifact and
report completion with `scripts/orchestration/report_child_completion.py`.

Stop: return the evidence rather than modifying implementation. Label any proof
that requires production, credentials, or live traffic as approval-gated.
