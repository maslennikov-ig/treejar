# Project Index - Treejar AI Sales Bot

Stable navigation map for this repository. Keep operational state in
`.codex/handoff.md` and stage history under `.codex/stages/`, not here.

## Runtime Shape

- Single-repo Python/FastAPI runtime for the Treejar WhatsApp AI sales assistant.
- Canonical live runtime target: `https://noor.starec.ai`; production path is `/opt/noor`.
- Primary app entrypoint: `src/main.py`; background worker entrypoint: `src/worker.py`.
- Admin/operator surfaces are served by the API plus `frontend/admin` assets.
- Main delivery branch is `main`; use dedicated worktrees for delegated streams.

## Primary Entrypoints

- `AGENTS.md` - portable repo contract and safety boundaries.
- `.codex/orchestrator.toml` - machine-readable orchestration and verification contract.
- `.codex/handoff.md` - current operational truth only.
- `README.md` - product/runtime overview and developer quick start.
- `src/main.py` - FastAPI application wiring.
- `src/api/v1/router.py` and `src/api/telegram_webhook.py` - public API and Telegram callback surfaces.
- `src/llm/engine.py`, `src/llm/order_quote_routes.py`, `src/llm/prompts.py`, `src/llm/communication_policy.py`, `src/llm/fact_extractor.py`, and `src/llm/closed_question_guard.py` - sales-agent tools, deterministic order/quote routing, guarded routing, prompt policy, customer-fact extraction, and closed-question repair.
- `src/dialogue/` - LangGraph dialogue-state kernel, side-effect-free typed order-state runtime, slot state, trace reducer, expected-answer frame matcher, and catalog reference parsing.
- `src/services/customer_memory.py` and `src/models/customer_memory.py` - durable customer profile facts, current-order memory, past-order history, and compact prompt context.
- `scripts/orchestration/run_process_verification.sh` - process-contract verification entrypoint.

## Core Subsystems

- `src/api/` - FastAPI routes, webhook handlers, admin/dashboard API boundaries.
- `src/core/` - settings, database, Redis, security, cache, discount helpers.
- `src/models/` and `src/schemas/` - SQLAlchemy persistence and Pydantic contracts.
- `src/llm/` - PydanticAI agent, tool routing, deterministic order/quote route adapter, safety, verified answers, order handoff.
- `src/dialogue/` - explicit dialogue state kernel plus typed product/quantity extraction contract; rollout modes are dialogue-kernel owned, while order runtime feeds engine/facts/memory adapters.
- `src/rag/` - knowledge/product search and embedding pipeline.
- `src/integrations/` - Wazzup messaging, Zoho CRM, Zoho Inventory, Telegram notification clients.
- `src/services/` - business services for chat, customer memory, notifications, follow-up, reports, media, PDF, referrals.
- `src/quality/` - AI and manager quality evaluation jobs, schemas, and transcript handling.
- `migrations/` - Alembic database migrations.
- `frontend/admin/` - admin/dashboard frontend build assets used by regression tests.
- `tests/` - pytest coverage for API, LLM flows, integrations, orchestration, and services.

## Integrations And Sources Of Truth

- Treejar Catalog API is the customer-facing product discovery, media, and catalog-price source.
- Zoho Inventory is the exact stock, draft Sale Order, quotation, and order-execution source.
- Zoho CRM stores customer/deal CRM context and source attribution.
- Wazzup is the WhatsApp transport; outbound sends should go through audit helpers.
- Telegram is the manager/operator alert and callback channel.
- Redis stores runtime cache, idempotency, temporary quotation PDFs, and background job state.
- PostgreSQL/Supabase is the durable application database; pgvector backs knowledge/product search.

## Verification

- Process contract: `scripts/orchestration/run_process_verification.sh`.
- Code-change gates from `.codex/orchestrator.toml`:
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
- Stage closeout: `scripts/orchestration/run_stage_closeout.py --stage <stage_id>`.

## Conventions And Boundaries

- Beads is the task source of truth; do not add another task ledger.
- Keep `.codex/handoff.md` compact and current-state only.
- Keep stage summaries/artifacts under `.codex/stages/<stage_id>/`.
- Do not deploy, mutate production config, or send live WhatsApp/media/voice tests without explicit approval.
- Update this index when stable entrypoints, routes, subsystem ownership, integrations, or verification commands change.
- Do not add stage history, current blockers, deployment logs, or temporary task notes to this file.
