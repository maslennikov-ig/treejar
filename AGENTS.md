# Agent Instructions

`AGENTS.md` is the primary portable contract for this repository. Read it first, then read `.codex/orchestrator.toml`, then `.codex/handoff.md`.

## Repository Shape

- Single-repo Python runtime for the Treejar AI sales assistant
- Main delivery branch: `main`
- Canonical live runtime target: `https://noor.starec.ai`

## Canonical Verification

Use the repo-local verification commands from `.codex/orchestrator.toml`.
Use `scripts/orchestration/run_process_verification.sh` as the process-verification entrypoint before claiming the orchestration layer is in a good state.
Use `scripts/orchestration/run_stage_closeout.py --stage <stage_id>` when a stage is actually closing; it is the canonical two-phase closeout entrypoint.

Typical code-change gates in this repo include:
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `uv run pytest tests/ -v --tb=short`

## Autonomy Policy

- Act without asking on reversible local work: reading files, editing tracked repo files, updating repo-local orchestration docs, running local verification, and updating Beads when task truth is clear.
- Ask before destructive, hard-to-reverse, or high-impact externally visible actions that are not already explicitly required by the repo contract.
- Always ask before deploys, prod/staging mutations, permission scope expansion, force-push/history rewrite, or when requirements remain materially ambiguous.

## Safety Boundaries

- Keep one task per branch or dedicated worktree.
- Prefer dedicated worktrees for delegated or parallel streams.
- Keep canonical runtime triage, deploy drift, and product fixes in separate delivery streams.
- If Beads needs recovery after clone or upgrade, use `bd bootstrap --yes`, `bd import`, `bd hooks install`, and `bd export -o .beads/issues.jsonl` as needed before push.
- Do not leave silent technical debt. Fix in-scope issues before close; any justified defer must be explicit, bounded, tracked in Beads, and listed in `.codex/handoff.md` under `Explicit defers`.

## Operational State

- `.codex/orchestrator.toml` is the machine-readable repo-local contract.
- `.codex/handoff.md` is current-state only.
- `.codex/stages/<stage_id>/summary.md` stores tracked stage summaries.
- `.codex/stages/<stage_id>/artifacts/<task_id>.md` stores tracked delegated artifacts.
- `.codex/agent-reports/` is the legacy local-only pre-v2 archive.
- `scripts/orchestration/validate_artifact.py` validates tracked artifacts.
- `scripts/orchestration/check_stage_ready.py <stage_id>` is the minimal hard stop before stage close.
- `scripts/orchestration/run_stage_closeout.py --stage <stage_id>` runs stage-close verification before delivery.
- `scripts/orchestration/cleanup_stage_workspace.py --stage <stage_id>` removes safe local worktrees and branches for completed stage deliveries.
- Beads remains the source of truth for queue, status, and dependencies.
