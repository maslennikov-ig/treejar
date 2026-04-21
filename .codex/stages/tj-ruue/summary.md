# Stage Summary

Stage ID: `tj-ruue`
Status: `open`
Updated: 2026-04-21
Baseline: `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb`
Orchestrator worktree: `/home/me/code/treejar/.worktrees/codex-live-triage-20260417`
Orchestrator branch: `codex/live-triage-20260417`
Integration commit: `0404bfc` (`feat(llm): add OpenRouter cost safety layer`)

## Scope

Implement OpenRouter cost controls and AI Quality Controls from the approved plan:

- provider-side LLM safety and bounded output settings;
- durable DB+Redis attempt/cache state;
- admin-controlled QA automation defaults;
- summary-mode review context;
- model routing away from GLM-5 for non-core jobs;
- OpenRouter cache telemetry;
- combined manager reply and Auto-FAQ candidate flow;
- admin dashboard controls and rollout documentation.

## Beads

- Epic: `tj-ruue`
- Safety layer: `tj-ruue.1`
- DB+Redis attempt state: `tj-ruue.2`
- Admin backend config: `tj-ruue.3`
- Summary transcript builder: `tj-ruue.4`
- Model routing/cache telemetry: `tj-ruue.5`
- Manager reply/Auto-FAQ flow: `tj-ruue.6`
- Frontend dashboard: `tj-ruue.7`
- Plan/rollout docs: `tj-ruue.8`

## Current State

- Beads epic and child tasks have been created.
- Dependencies have been added between the planned tasks.
- Plan/rollout doc has been added at `docs/plans/2026-04-21-openrouter-cost-control-ai-quality-controls.md`.
- Context7 docs check was performed for PydanticAI settings/usage limits and OpenRouter usage/cache telemetry.
- This baseline does not contain `scripts/orchestration/report_child_completion.py`; child completion will be tracked by artifact files plus local orchestrator review until the repo contract is reconciled.
- `tj-ruue.1` safety layer was accepted from manual worker branch `codex/tj-ruue-safety-layer-v2` in `/home/me/code/treejar/.worktrees/codex-tj-ruue-safety-layer-v2`. The accepted worker commit is `72cde7c`; runtime/test files were integrated into `codex/live-triage-20260417` and committed as `0404bfc`. Independent orchestrator review passed targeted safety/call-site tests, artifact validation, ruff check, ruff format check, mypy, and `git diff --check`.

## Orchestration Plan

First wave:

- `tj-ruue.1`: accepted and integrated into `codex/live-triage-20260417`.
- `tj-ruue.8`: accepted locally.

Second wave:

- `tj-ruue.2`: DB+Redis attempt/cache state.
- `tj-ruue.4`: summary-mode transcript builder.

Third wave:

- `tj-ruue.3`: admin backend controls.
- `tj-ruue.5`: model routing and cache telemetry.

Final wave:

- `tj-ruue.6`: combined manager reply and Auto-FAQ candidate flow.
- `tj-ruue.7`: frontend dashboard.

## Verification Policy

Each child artifact must include:

- branch and worktree;
- base branch and base commit;
- changed files;
- commands run and results;
- risks, follow-ups, and explicit defers.

Stage closeout requires:

- artifact validation;
- `check_stage_ready.py`;
- repo-local code-change verification from `.codex/orchestrator.toml`;
- process verification entrypoint.

## Explicit Defers

- No production deploy or production mutation is included in this stage unless separately requested.
- Full-transcript QA remains off by default in the target design; enabling it requires explicit admin override after implementation.
