Target: Codex reviewer working from the isolated `tj-av22.9` review worktree.

Goal: give the root orchestrator an independent, evidence-backed verdict on the
latest inbound reliability correction and the durable documentation updates.
Use your judgment to choose the most useful review order and focused checks.

Useful context:
- `AGENTS.md`, `.codex/orchestrator.toml`, and `.codex/handoff.md`
- Beads `tj-av22.6`, `tj-av22.7`, `tj-av22.8`, and `tj-av22.9`
- prior review artifacts `tj-av22.7.md` and `tj-av22.8.md`
- implementation commit `71efe57`
- documentation commit `99283af`

The review should make it easy to decide whether:
- an accepted batch survives cancellation or worker loss in a durable,
  immutable processing list;
- the owner lease cannot expire during the configured worker job;
- completed work is acknowledged without replay, while an uncertain late
  outcome is quarantined without invoking LLM/provider side effects again;
- messages arriving during recovery remain a later batch;
- manager messages never trigger an automated customer response;
- the runbook describes the proven recovery boundary without overstating
  exactly-once delivery;
- the five documentation findings from `tj-av22.8` are resolved accurately.

Constraints: treat this as a read-only product-code and durable-doc review. The
only intended repository write is
`.codex/stages/tj-av22/artifacts/tj-av22.9.md`. Do not change implementation,
tests, durable guides, Beads, production, credentials, or external services.
Keep local evidence distinct from approval-gated production proof.

Asset Routing:
- selected skills: code-review, verification-before-completion
- selected agents/personas: independent stabilization and documentation reviewer
- catalog candidates: none; installed review guidance covers this task

Documentation: repository-owned contracts are sufficient. No version-sensitive
dependency research is expected. If a dependency detail becomes material, use
authoritative documentation through Context7 when available and cite it in the
artifact.

Output: a validated review artifact with current file/line evidence, focused
verification, disposition of the open inbound P1 and five documentation
findings, any new findings by severity, and a clear local release verdict.
Commit the artifact and report completion through
`scripts/orchestration/report_child_completion.py`.

Stop: return risks and evidence instead of correcting them. Anything requiring
production access, live traffic, credentials, or external writes remains an
explicit approval-gated proof.
