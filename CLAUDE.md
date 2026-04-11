# CLAUDE.md

Primary repo contract lives in `AGENTS.md`.

For orchestration and current state, use:
1. `AGENTS.md`
2. `.codex/orchestrator.toml`
3. `.codex/handoff.md`

Repo-specific reminders:
- Treejar uses a main-only delivery flow.
- Canonical runtime target is `https://noor.starec.ai`.
- Prefer dedicated worktrees for delegated or parallel streams.
- If Beads maintenance is needed after clone or upgrade, use `bd bootstrap --yes`, `bd import`, `bd hooks install`, and `bd export -o .beads/issues.jsonl`.
