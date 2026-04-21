# OpenRouter Cost Control and AI Quality Controls

Date: 2026-04-21
Stage: `tj-ruue`
Status: implementation plan approved for staged orchestration

## Problem Statement

OpenRouter spend in March-April 2026 was driven mostly by background quality jobs, not by normal client chat traffic. The current implementation lets expensive evaluators send full transcripts and large system/tool prompts to OpenRouter on frequent cron schedules. It also relies on post-response `UsageLimits`, which does not prevent provider-side runaway output billing.

The target state is a durable cost-control layer plus admin-owned AI Quality Controls:

- default AI QA automation is disabled;
- QA and manager review can run manually or on conservative schedules from admin settings;
- non-core QA paths do not use GLM-5 by default;
- large conversations are summarized before review unless an admin explicitly allows full transcripts;
- all LLM calls have provider-side output caps, request limits, one retry, durable attempt state, and budget checks;
- OpenRouter cache telemetry is recorded where supported;
- repeated candidates do not get reprocessed indefinitely.

## Evidence Summary

Input data: `/home/me/code/treejar/.tmp/openrouter_activity_2026-04-21.csv`.

Observed period: 2026-03-23 08:27:19 UTC to 2026-04-12 03:09:11 UTC.

Key totals:

- 3674 OpenRouter generation rows.
- Total cost: `$39.502915`.
- `z-ai/glm-5-20260211`: `$39.344706`, 2283 calls, 13.85M prompt tokens, 8.47M completion tokens.
- `xiaomi/mimo-v2-flash-20251210`: `$0.158034`, 1390 calls.
- Exact cron-like calls around `:00` / `:30`: `$24.550454`.
- Broader minute `:00` / `:30` calls: `$26.054379`.
- `prompt > 32k`: 230 rows, `$10.656645`.
- `completion > 100k`: one row, the runaway.

Runaway generation:

- generation: `gen-1775962801-YCgBAz8xSVUvl5LhDoP0`
- time: 2026-04-12 03:00:01 UTC
- model/provider: `z-ai/glm-5-20260211` / Parasail
- prompt tokens: 2851
- completion tokens: 3,920,375
- reasoning tokens: 1169
- cost: `$12.548051`

Large input examples:

- `gen-1775757600-9SPA0RMCkGiXRsdBbJZf`: 86,229 prompt tokens at 2026-04-09 18:00:00 UTC, GLM-5.
- `gen-1775565001-lZBgOIouGPYeqr9wi6mh`: 67,331 prompt tokens at 2026-04-07 12:30:01 UTC, Xiaomi fast model.
- `gen-1775563304-c0nwr0R1gkVUiYemC08A`: 66,075 prompt tokens at 2026-04-07 12:01:43 UTC, GLM-5.

Repeat evidence:

- Prompt size 44,109 repeated 82 times, costing about `$3.93`.
- Prompt size 44,110 repeated 51 times, costing about `$2.32`.

Root causes in code:

- `src/worker.py`: final review hourly, red flags every 30 minutes, manager review every 30 minutes.
- `src/quality/evaluator.py`: final/red-flag evaluators build prompts from full message history and pass only post-response `UsageLimits`.
- `src/quality/manager_evaluator.py`: manager evaluator loads all post-escalation user/manager messages and passes only post-response `UsageLimits`.
- `src/quality/job.py`: markers are written after successful work; no-flag and failed cases can be retried by future cron runs.
- `src/quality/manager_job.py`: failed/unreviewable escalations do not get durable terminal state.
- `src/llm/context.py`: normal client chat is already bounded, which is why core chat is not the same cost source.
- `src/llm/conversation_summary.py`, `src/llm/response_adapter.py`, `src/services/auto_faq.py`: secondary LLM paths also lack provider-side max output settings.

## Documentation Checks

Context7 was used on 2026-04-21 for current PydanticAI and OpenRouter behavior.

Confirmed PydanticAI constraints:

- `ModelSettings(max_tokens=...)` can be set at model, agent, or run level; run-level settings have highest precedence.
- `UsageLimits(response_tokens_limit, total_tokens_limit, request_limit)` still matters, but token-limit exceptions can happen after a provider response is already produced.
- For OpenRouter, PydanticAI documents `OpenRouterModel` and `OpenRouterModelSettings`, including `openrouter_usage={"include": True}`.

Confirmed OpenRouter constraints:

- OpenRouter usage can include `prompt_tokens_details.cached_tokens`.
- OpenRouter usage can include `prompt_tokens_details.cache_write_tokens`.
- OpenRouter usage can include completion details such as reasoning tokens and cost fields.
- Prompt caching reduces prompt cost where supported, but does not protect against runaway completion output; provider-side `max_tokens` is still mandatory.

## Design Principles

1. Safety first, without silently breaking core bot behavior.
   Provider-side output caps must be high enough per path to allow valid structured output, but no path should be able to generate millions of tokens.

2. QA automation is non-core.
   Owner-quality automation can be useful, but it must be admin-controlled and disabled by default. The bot's client-facing sales path remains the priority.

3. Durable state beats repeated cron work.
   Cron jobs must record attempts, failures, no-action decisions, budget blocks, and manual-review states so the same candidate does not get billed repeatedly.

4. Summaries are the default review context.
   Full transcript review is allowed only with explicit admin warning/override.

5. GLM-5 is reserved for valuable sales decisions.
   Non-core QA, red flags, summaries, translation, and KB candidate work should use fast/cache-friendly models unless an admin explicitly overrides with a warning.

6. Cache is an optimization, not a safety boundary.
   Use OpenRouter cache telemetry and app-level cache keys, but still enforce budgets, locks, retry policy, and max output settings.

## Target Architecture

### 1. Safety Layer

Every LLM path should go through a shared helper or policy object that provides:

- path name, scope, and purpose;
- model selection;
- provider-side `model_settings.max_tokens`;
- `UsageLimits` with `request_limit`, `response_tokens_limit`, and `total_tokens_limit`;
- one safe retry for retryable transport/provider/validation failures;
- timeout;
- budget check before the call;
- usage logging after the call;
- admin alert on final failure or budget block for relevant paths.

Initial max output defaults should be path-specific:

- client-facing sales chat: large enough for current behavior, but bounded;
- final QA evaluation: structured output cap only;
- red flags: small structured output cap;
- manager QA: structured output cap;
- summary: compact structured output cap;
- response adapter: short message cap;
- Auto-FAQ translation/candidate: short structured output cap;
- voice transcription: separate OpenAI SDK path, reviewed independently.

### 2. LLM Attempts and Cache State

Add durable DB state with statuses:

- `pending`
- `success`
- `no_action`
- `failed_retryable`
- `failed_final`
- `budget_blocked`
- `needs_manual_review`

Suggested columns:

- `id`
- `path`
- `scope`
- `entity_type`
- `entity_id`
- `entity_updated_at`
- `prompt_version`
- `input_hash`
- `settings_hash`
- `status`
- `model`
- `provider`
- `attempt_count`
- `last_error`
- `budget_cents`
- `cost_estimate`
- `prompt_tokens`
- `completion_tokens`
- `reasoning_tokens`
- `cached_tokens`
- `cache_write_tokens`
- `result_json`
- `created_at`
- `updated_at`
- `next_retry_at`

Redis responsibilities:

- short-lived lock per `(path, entity_id, entity_updated_at, prompt_version)`;
- backoff marker after retryable failure;
- optional daily budget counters for fast pre-checks.

DB remains the source of durable truth. Redis is coordination and speed.

### 3. AI Quality Controls Config

Store the admin config in `SystemConfig` JSON plus typed backend schema.

Scopes:

- bot QA;
- manager QA;
- red flags.

Modes:

- `disabled`;
- `manual`;
- `daily_sample`;
- `scheduled`.

Transcript modes:

- `disabled`;
- `summary`;
- `full_with_warning`.

Other settings:

- preset criteria toggles;
- model;
- daily budget;
- max calls per run;
- max calls per day;
- retry policy;
- alert behavior;
- OpenRouter cache telemetry flag.

Defaults:

- all QA automation disabled;
- transcript mode `summary`;
- conservative budgets;
- GLM-5 unavailable in QA defaults;
- full transcript requires explicit warning override;
- scheduled mode requires explicit opt-in.

### 4. Summary-Mode Transcript Builder

Build review context in two phases.

Rules-first extraction:

- first customer turn;
- latest customer/assistant turns;
- manager segment after escalation;
- promises and commitments;
- complaints, red flags, urgency, refunds, legal/safety terms;
- order/quotation context;
- unanswered questions;
- evidence snippets with message IDs/timestamps.

Fast LLM summary:

- only after deterministic extraction;
- fast/cache-friendly model;
- structured summary schema;
- cache key: `(entity_type, entity_id, entity_updated_at, prompt_version, criteria_version)`.

Evaluator behavior:

- default to summary;
- if summary lacks evidence, return `needs_manual_review` or `insufficient_evidence`, not full transcript by default;
- full transcript allowed only through admin override and budget checks.

### 5. Model Routing

Policy:

- GLM-5 stays available for client-facing sales and high-value decision paths.
- QA, red flags, summaries, response adapter, Auto-FAQ candidate work default to fast/cache-friendly models.
- Admin override to GLM-5 requires explicit warning and is logged.

Expected effect:

- eliminates GLM-5 as default for frequent non-core background jobs;
- reduces cost even before caching;
- preserves quality where it matters most: client-facing sales.

### 6. OpenRouter Prompt Caching and Telemetry

Enable cache usage where supported by the selected model/provider and request format.

Always log:

- prompt tokens;
- completion tokens;
- reasoning tokens;
- cached tokens;
- cache write tokens;
- provider;
- model;
- path;
- estimated/actual cost when available.

Cache caveat:

- cache hit/miss metrics are observability and cost optimization;
- runaway output prevention still depends on provider-side `max_tokens`.

### 7. Manager Reply and Auto-FAQ

Current problem:

- normal manager response adaptation and Auto-FAQ can become separate LLM work;
- Auto-FAQ should not be a broad automatic semantic agent.

Target flow:

- normal manager reply: one adapter call only;
- when manager explicitly presses "add to KB": one combined LLM call returns:
  - `customer_message`;
  - `kb_candidate`;
- deterministic post-checks:
  - regex guards;
  - duplicate similarity;
  - confidence threshold;
  - admin confirmation before saving.

## Beads Task Map

- `tj-ruue`: epic, OpenRouter cost controls and AI Quality Controls.
- `tj-ruue.1`: safety layer for all LLM paths.
- `tj-ruue.2`: DB+Redis LLM attempt cache state.
- `tj-ruue.3`: admin AI Quality Controls backend.
- `tj-ruue.4`: summary-mode transcript builder for QA.
- `tj-ruue.5`: model routing and OpenRouter cache telemetry.
- `tj-ruue.6`: combined manager reply and Auto-FAQ candidate flow.
- `tj-ruue.7`: frontend AI Quality Controls dashboard.
- `tj-ruue.8`: this plan doc and rollout docs.

Dependency order:

1. `tj-ruue.1` before `tj-ruue.2` and `tj-ruue.4`.
2. `tj-ruue.2` before `tj-ruue.3`.
3. `tj-ruue.8` before `tj-ruue.3`.
4. `tj-ruue.4` before `tj-ruue.5`.
5. `tj-ruue.5` before `tj-ruue.6`.
6. `tj-ruue.3` before `tj-ruue.7`.

## Implementation Plan

### Patch Set 1: Safety Layer

Goal: make every existing LLM path incapable of runaway output.

Scope:

- central LLM policy/settings helper;
- provider-side `ModelSettings(max_tokens=...)` at all PydanticAI run sites;
- one retry only;
- timeout;
- admin alert on final failure;
- basic usage logging shape.

Primary files:

- `src/llm/engine.py`
- `src/quality/evaluator.py`
- `src/quality/manager_evaluator.py`
- `src/llm/conversation_summary.py`
- `src/llm/response_adapter.py`
- `src/services/auto_faq.py`

Tests:

- every LLM path passes `model_settings.max_tokens`;
- one retry occurs once;
- retry failure becomes final failure;
- final failure sends admin notification;
- runaway-scale completion cannot be requested because provider-side cap is set.

### Patch Set 2: DB+Redis Attempt State

Goal: stop repeated cron billing for the same candidate.

Scope:

- DB model and migration;
- attempt repository/service;
- Redis lock/backoff helper;
- integration into QA jobs.

Tests:

- same entity/update/prompt_version uses cached state;
- concurrent job sees Redis lock and skips;
- failed retryable sets backoff;
- unreviewable/no-action writes terminal state;
- budget-blocked writes durable state.

### Patch Set 3: Admin Backend Config

Goal: make QA automation admin-owned and disabled by default.

Scope:

- typed config schema;
- defaults;
- admin read/update API;
- validation for GLM override and full transcript mode;
- manual trigger endpoints that respect mode/budget.

Tests:

- default config has all automation disabled;
- disabled mode performs zero LLM calls;
- manual trigger respects budget and max calls;
- scheduled mode requires explicit enabled settings;
- GLM/full transcript override returns warning metadata.

### Patch Set 4: Summary Transcript Builder

Goal: replace full transcript prompts with bounded review context.

Scope:

- deterministic excerpt builder;
- fast LLM structured summary;
- cache key by entity/update/prompt_version;
- evaluator fallback to `needs_manual_review` on insufficient evidence.

Tests:

- oversized transcript uses summary by default;
- full transcript only with explicit policy;
- summary cache prevents repeated LLM call;
- evaluator can return insufficient evidence instead of consuming full transcript.

### Patch Set 5: Model Routing and OpenRouter Cache Telemetry

Goal: remove GLM-5 from non-core defaults and measure cache behavior.

Scope:

- model policy per path;
- OpenRouter usage include where supported;
- logging of cache fields;
- cost metrics by path/provider/model.

Tests:

- QA defaults do not select GLM-5;
- GLM override requires explicit setting;
- usage logs include `cached_tokens` and `cache_write_tokens`;
- cache settings are included when enabled.

### Patch Set 6: Combined Manager Reply and Auto-FAQ

Goal: reduce duplicate LLM calls around manager replies and KB candidates.

Scope:

- normal manager reply stays one adapter call;
- "add to KB" path uses one combined structured call;
- deterministic post-checks;
- admin confirmation.

Tests:

- normal reply does not create KB candidate;
- add-to-KB returns both customer message and candidate;
- duplicate/unsafe/low-confidence candidate is rejected;
- only confirmed candidate is saved.

### Patch Set 7: Frontend Dashboard

Goal: expose AI Quality Controls safely to admins.

Scope:

- controls for scopes, modes, transcript mode, budgets, model, retry policy, criteria toggles;
- preset and advanced sections;
- warnings for full transcript and GLM override;
- status panels and manual triggers.

Tests:

- renders current settings;
- tooltips/help text explain cost/risk;
- disabled defaults render clearly;
- warnings appear for risky overrides.

## Immediate Operational Mitigation Without Code

Until this ships and credits are safe:

1. Disable or pause background QA cron jobs if there is an operational toggle or scheduler-level control.
2. Keep final review, red flags, and manager review in manual mode operationally.
3. Do not run broad backfills over historical conversations.
4. Avoid GLM-5 for non-client-facing manual experiments.
5. If manual review is required, sample a small number of candidates and inspect usage after each batch.

Safe to disable without breaking the core bot:

- final owner QA automation;
- red flag background scan;
- manager QA automation;
- Auto-FAQ candidate generation unless explicitly requested by manager.

Do not disable without separate review:

- client-facing sales chat;
- order/quotation paths;
- escalation alerts that notify managers;
- WhatsApp/Wazzup inbound/outbound delivery.

## Rollout Plan

1. Merge and deploy safety layer first.
2. Enable usage logging and verify every LLM path reports path/model/provider/token fields.
3. Deploy DB+Redis attempt state with QA jobs still disabled.
4. Enable manual-only admin QA controls.
5. Test manual QA on a small sample and inspect usage/cost/cache fields.
6. Enable daily sample only after budget and cache telemetry look sane.
7. Keep scheduled frequent mode disabled unless explicitly justified by fresh operational need.

## Rollback Plan

- Safety layer rollback: revert the patch only if it blocks core chat; otherwise lower caps or disable non-core paths first.
- Attempt/cache rollback: leave DB table in place, disable service integration, keep statuses for audit.
- Admin controls rollback: force config defaults to disabled and hide scheduled mode.
- Summary rollback: switch QA to manual disabled rather than restoring full-transcript cron.
- Model routing rollback: keep GLM-5 only for core chat unless a specific non-core path has evidence of unacceptable quality.

## Verification Matrix

Unit:

- every LLM path passes provider-side `max_tokens`;
- retry occurs once and no more;
- final failure sends admin notification;
- cache key prevents repeat LLM call;
- Redis lock prevents duplicate concurrent attempt;
- oversized transcript follows summary/full/manual policy;
- GLM-5 is not selected for QA defaults.

API:

- admin settings read/update;
- manual bot QA trigger respects budget/mode;
- manual manager QA trigger respects budget/mode;
- disabled mode performs zero LLM calls.

Frontend:

- controls render current settings;
- tooltips explain cost/risk;
- warnings for full transcript and GLM override.

Integration with mocked OpenRouter:

- usage logs include cached token fields;
- cache settings are included when enabled;
- combined manager response returns client message plus KB candidate only when requested.

Stage closeout:

- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest tests/ -v --tb=short`
- `scripts/orchestration/run_process_verification.sh`

