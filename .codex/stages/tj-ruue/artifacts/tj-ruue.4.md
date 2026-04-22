---
task_id: tj-ruue.4
stage_id: tj-ruue
repo: treejar
branch: codex/tj-ruue-summary-transcript-builder
base_branch: codex/live-triage-20260417
base_commit: 313a0bab4e792506210fce4f0edc570d4af29594
worktree: /home/me/code/treejar/.worktrees/codex-tj-ruue-summary-transcript-builder
status: returned
verification:
  - Context7 PydanticAI docs query: passed
  - Context7 Pydantic v2 docs query: passed
  - Context7 SQLAlchemy docs query: passed
  - Orchestrator review fix tj-ruue.4.1: passed
  - uv run --extra dev python -m pytest -s tests/test_llm_attempts.py tests/test_quality_transcript_context.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_quality_transcript_context.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q: passed
  - uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.4.md: passed
  - git diff --check: passed
  - npm ci in frontend/admin: passed
  - uv run python -m pytest -s tests/ -v --tb=short: passed
changed_files:
  - .codex/stages/tj-ruue/artifacts/tj-ruue.4.md
  - docs/reports/code-reviews/2026-04/CR-2026-04-22-tj-ruue-summary-transcript-builder-orchestrator.md
  - src/llm/attempts.py
  - src/quality/config.py
  - src/quality/evaluator.py
  - src/quality/job.py
  - src/quality/manager_evaluator.py
  - src/quality/manager_job.py
  - src/quality/transcript_context.py
  - tests/test_e2e_stage2.py
  - tests/test_llm_attempts.py
  - tests/test_manager_evaluator.py
  - tests/test_manager_job.py
  - tests/test_quality_evaluator.py
  - tests/test_quality_job.py
  - tests/test_quality_transcript_context.py
---

# Summary

Implemented the summary-mode transcript builder for AI quality review.

The new `src/quality/transcript_context.py` builds rules-first bounded review
contexts for bot QA, red flags, and manager QA. Summary mode includes compact
metadata, first turn, latest turns, manager segment, promises/commitments,
escalation/handoff markers, and any existing fast conversation summary. Red
flags use a smaller context budget, and manager QA emphasizes the
post-escalation segment plus compact prior context.

`AIQualityRunGate` now carries `transcript_mode`, scheduled bot QA/red flags/
manager QA pass that mode into evaluators, and LLM attempt `input_hash` /
`settings_hash` include transcript mode plus
`quality-review-context-summary:v1`. Final bot QA, red flags, and manager QA
all return local insufficient-evidence/no-action style results without provider
calls when transcript mode is `disabled`. Summary mode is the default path and
does not send full raw transcripts. Full transcript mode remains explicit and
is reached only when the caller/gate passes `full`.

Orchestrator review found and fixed `tj-ruue.4.1`: durable terminal attempt
reuse was still keyed only by the old logical DB key, so a previous terminal
`no_action`/`success` could block re-evaluation after `transcript_mode`,
summary prompt version, or model settings changed. `begin_llm_attempt()` now
reuses terminal attempts only when incoming `input_hash` and `settings_hash`
match; changed hashes reopen the attempt under the existing Redis lock and
clear stale result/error fields.

Context7 facts recorded:

- PydanticAI structured output is declared with Pydantic `BaseModel` via
  `Agent(..., output_type=...)`; typed output is available on `result.output`.
- PydanticAI run-level `ModelSettings(max_tokens=...)` has highest precedence
  over agent/model defaults, which supports provider-side output caps.
- PydanticAI `UsageLimits` supports `request_limit`, response/output token
  limits, and total token limits; response token exceptions can be observed
  after a provider response, so provider-side `max_tokens` remains mandatory.
- Pydantic v2 supports `Field` constraints, `default_factory`, and
  `ConfigDict(extra="forbid")`; no new Pydantic schema was required for this
  task.
- SQLAlchemy 2.0 async ORM uses `AsyncSession.execute(select(...))` and
  scalar retrieval for async reads; ORM attribute assignment is tracked and
  flushed/committed by the unit of work. This task reads existing
  `ConversationSummary` rows and does not change the persistent model schema.

# Verification

Verification run:

- `uv run --extra dev python -m pytest -s tests/test_llm_attempts.py tests/test_quality_transcript_context.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q` -> passed, `113 passed`.
- `uv run --extra dev python -m pytest -s tests/test_quality_transcript_context.py tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q` -> passed, `96 passed`.
- `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_quality_evaluator.py tests/test_manager_evaluator.py tests/test_llm_conversation_summary.py tests/test_llm_context.py -q` -> passed, `91 passed`.
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed, `Success: no issues found in 121 source files`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-ruue/artifacts/tj-ruue.4.md` -> passed, `artifact validation OK`.
- `git diff --check` -> passed.
- `npm ci` in `frontend/admin` -> passed; npm reported existing Node engine warnings for packages requiring Node 20+ while local Node is 18.19.1, plus existing high-severity audit findings.
- `uv run python -m pytest -s tests/ -v --tb=short` -> passed after `npm ci`, `720 passed, 19 skipped`.

# Risks / Follow-ups / Explicit Defers

- No production deploy, staging/prod mutation, commit, push, or PR was done.
- The builder reuses existing `ConversationSummary` text when present but does
  not force a new summary LLM call inline. This avoids extra QA cron spin; the
  existing conversation summary path remains the fast/safety-bounded path when
  summary refresh jobs run.
- Full transcript mode is still callable from code, but scheduled jobs only
  reach it through `AIQualityRunGate.transcript_mode`, whose config validation
  requires the existing full-transcript warning override.
- Attempt state now treats changed transcript/settings hashes as a new billable
  attempt on the same logical row; this intentionally trades exact historical
  result preservation in the attempt row for correct re-evaluation after admin
  policy changes.
- A subagent code review was not dispatched because this session allows
  subagents only on explicit user request. Local diff review plus tests,
  ruff, and mypy were used instead.
