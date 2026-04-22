# Stage Summary

Stage ID: `tj-ruue`
Status: `open`
Updated: 2026-04-22
Baseline: `origin/main@9ef78006a6a6055fa4786f1a856b422cb916dabb`
Orchestrator worktree: `/home/me/code/treejar/.worktrees/codex-live-triage-20260417`
Orchestrator branch: `codex/live-triage-20260417`
Integration commit: `0404bfc` (`feat(llm): add OpenRouter cost safety layer`)
Latest integration commit: `a48c8f7` (`feat(llm): add model routing cache telemetry`)

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
- `tj-ruue.2` DB+Redis LLM attempt/cache state was accepted from `codex/tj-ruue-llm-attempt-state` and integrated as `b6dd171`. Orchestrator follow-up review created/fixed `tj-ruue.2.4` through `tj-ruue.2.7`: terminal-success delivery replay, persistence failure classification, transcript-aware attempt keys, and Redis lock cleanup on begin failure. Verification passed focused QA/manager/attempt/migration tests, ruff, format, mypy, artifact validator, `git diff --check`, and full pytest after local `npm ci` in `frontend/admin` (`689 passed, 19 skipped`).
- `tj-ruue.3` Admin AI Quality Controls backend was accepted from `codex/tj-ruue-ai-quality-controls-backend` and integrated as `949d335`. Orchestrator review found/fixed `tj-ruue.3.1`: `daily_sample` and `max_calls_per_day` were represented but initially only per-run bounded. The accepted code adds SystemConfig-backed admin GET/PUT/PATCH config, conservative disabled defaults, GLM/full-transcript override validation, QA model propagation, Redis UTC-day daily sample reservation, Redis daily call quotas, and safe invalid-config fallback. Verification passed focused admin/QA/evaluator tests, ruff, format, mypy, artifact validator, `git diff --check`, and full pytest after local `npm ci` in `frontend/admin` (`703 passed, 19 skipped`).
- `tj-ruue.4` Summary-mode transcript builder was accepted from `codex/tj-ruue-summary-transcript-builder` and integrated as `705804b`. The accepted code adds bounded QA review contexts, summary/default transcript mode, disabled-mode local no-action results, full-mode explicit routing, transcript-mode propagation into jobs/evaluators, and prompt/version-aware attempt hashes. Orchestrator review found/fixed `tj-ruue.4.1`: terminal LLM attempts now only replay when input/settings hashes match, so admin policy/model changes can re-evaluate stale `no_action`/`success` rows. Verification passed targeted QA/manager/attempt/context tests (`113 passed`), ruff, format, mypy, artifact validator, `git diff --check`, and full pytest (`720 passed, 19 skipped`).
- `tj-ruue.5` Model routing and OpenRouter cache telemetry was accepted from `codex/tj-ruue-model-routing-cache-telemetry` and integrated as `a48c8f7`. The accepted code centralizes model routing in `src/llm/safety.py`, keeps GLM/main defaults only for core chat/follow-up, routes non-core QA/helper paths to the fast model by default, adds conservative OpenRouter request telemetry/cache settings, and persists normalized usage/cache fields into `llm_attempts` for QA success and LLM-backed no-action outcomes. Orchestrator review found/fixed `tj-ruue.5.1`: importing AI Quality config no longer requires `OPENROUTER_API_KEY` because `src.llm` package exports are lazy. Verification passed targeted LLM/QA/chat import tests (`156 passed`), ruff, format, mypy, artifact validator, `git diff --check`, and full pytest (`727 passed, 19 skipped`).

## Orchestration Plan

First wave:

- `tj-ruue.1`: accepted and integrated into `codex/live-triage-20260417`.
- `tj-ruue.8`: accepted locally.

Second wave:

- `tj-ruue.2`: accepted and integrated into `codex/live-triage-20260417`.
- `tj-ruue.4`: accepted and integrated into `codex/live-triage-20260417`.

Third wave:

- `tj-ruue.3`: accepted and integrated into `codex/live-triage-20260417`.
- `tj-ruue.5`: accepted and integrated into `codex/live-triage-20260417`.

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
