# Stage tj-memory: Customer Facts And Order Memory Layer

Updated: 2026-06-04
Status: deployed; production E2E passed; rollout config gated; PII masking disabled by default
Branch: `main`
Base: `origin/main` at `d49abcfc0606102b2098880245723e6fda999193`
Beads: `tj-memory` epic with child tasks `tj-memory.1` through `tj-memory.10`

docs-reviewed: updated - architecture spec, plan, stage artifacts, and handoff
cover the delivered memory layer and production E2E evidence.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.
project-index: reviewed-no-change - this closeout changed behavior and rollout
evidence, not stable entrypoints, directories, integrations, or verification
commands.

## Goal

Create a durable facts layer so Noor extracts useful information from every
customer message, separates persistent customer profile from active order state
and past orders, and avoids re-asking or losing already-provided facts.

## Current State

- GitHub #48/tj-gh49 is closed and delivered.
- Production still runs the dialogue kernel in enforce mode only for
  `product_selection`.
- Customer facts mode is deployed and config-gated. Production E2E passed with
  temporary `customer_facts_mode=enforce`; after the test, the override was
  deleted and the effective prod value returned to default `disabled`.
- Implemented DB models/migration, memory service, deterministic/fast extractor,
  engine prompt integration, past-order answer path, quotation snapshot sync,
  source message id propagation, and savepoint-backed fail-open handling.
- Review hardening is applied: current-order `individual/company` satisfies the
  quote details gate, price objections stay non-terminal, and optional memory
  writes do not reuse a failed DB transaction.
- Production E2E hotfixes are applied: `2 CH 616 chairs` keeps quantity `2`,
  ignores PII placeholders as SKU candidates, does not repeat already supplied
  quote details, and does not store `Hi Noor` as a customer name fact.
- Runtime PII masking is disabled by default in production because it was not a
  client requirement and can block phone/email/address/SKU fact extraction. It
  remains available only via explicit `PII_MASKING_ENABLED=true`.
- Delivery E2E for the PII/default-off change passed after two blocking fixes:
  first-turn messages that already include a name now skip name-gate, and
  name-gate replies with extra customer details such as
  `Victor PII Test, individual` resume the stored request instead of being
  treated as a generic detail update.

## Decisions

- Use a scoped Customer Facts Layer, not a broad "remember everything" store.
- Store profile facts, current order facts, and past order memories separately.
- A sent quotation creates a snapshot, but the order becomes historical only
  after acceptance, refusal, no-response closure, or supersession.
- Use deterministic extraction first, then `settings.openrouter_model_fast`
  (`xiaomi/mimo-v2-flash` by default) only for ambiguous structured extraction.
- Past order data can answer questions like "what did I order last time" but
  cannot be reused for a new quotation without customer confirmation.

## Parallel Decomposition Matrix

| Stream | Beads | Goal | Owner | Write zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | `tj-memory.1` | Spec and plan | local | docs/specs, docs/superpowers/plans, stage docs | none | artifact/process verification | local | Simple orchestration/docs |
| B | `tj-memory.2` | Persistence and memory service skeleton | db specialist/worker | models, migration, service tests | A | model/migration tests | parallel | Complete |
| C | `tj-memory.3` | Fact extractor | worker | `src/llm/fact_extractor.py`, tests | A | extractor tests | parallel | Complete |
| D | `tj-memory.4` | Order lifecycle | local | service + engine quotation sync | B interface | service/engine tests | sequential | Complete enough for v1 |
| E | `tj-memory.5` | Engine/prompt integration | orchestrator | `src/llm/engine.py`, prompt/context tests | B+C+D | targeted LLM tests | sequential | Complete for disabled/shadow/enforce v1 |
| F | `tj-memory.6` | Regression/eval suite | local | focused tests | C+E | targeted tests | sequential | Focused coverage added; broad replay remains rollout work |
| G | `tj-memory.7` | Rollout and production evidence | orchestrator/deploy specialist | config/artifacts | full green | smoke/E2E | sequential final | Production evidence captured; global enable remains an explicit config decision |

## Verification

Passed for this implementation checkpoint:

- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-memory/artifacts/tj-memory.1-spec.md`
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-memory/artifacts/tj-memory.2-db.md`
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-memory/artifacts/tj-memory.3-extractor.md`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_models.py tests/test_customer_memory_service.py tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_dialogue_config.py -v --tb=short`
- `uv run ruff check ...targeted files...`
- `uv run ruff format --check ...targeted files...`
- `uv run mypy src/`
- `OPENROUTER_API_KEY=dummy uv run pytest tests/test_customer_memory_service.py tests/test_fact_extractor.py tests/test_llm_engine_customer_facts.py tests/test_services_chat_batch.py -v --tb=short` - 46 passed
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short` - 1271 passed, 19 skipped
- `scripts/orchestration/run_process_verification.sh`

Additional delivery and E2E checkpoint:

- Runtime release `ccd8b094b521ed7f899240feaf739c12d4e0ba83`, GitHub Actions
  run `26951658369`, deploy succeeded.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -
  8 passed, 0 failed.
- Final production E2E conversation
  `0e1feaa8-5922-49b9-abb6-9ab111607d92` on
  `+79262810921#tj-memory-e2e-20260604-1231`: Noor confirmed `2 x CH 616 black`,
  no `616 x chairs`, no repeated full name/email/address request, no escalation,
  pending quote unresolved items empty.
- DB readback for the E2E: `quote_customer_details` contains Victor, email,
  `Office 1905, JLT Dubai`, and `individual`; customer facts trace has
  `accepted_count=7`, `conflict_count=0`, `fast_model_called=false`;
  `customer_facts_mode`, trace, and fast extractor overrides restored to `UNSET`.

PII masking default-off delivery checkpoint:

- Commits delivered to `main`: `1421cf91fe2e24a2fee0fd4ebb7c2eb826b1b335`
  (disable masking by default), `ae36633bad5f32fd6be0f1a9cebc96e2487f1c75`
  (honor first-turn customer details), and
  `e4e7ecff52d71434e5f0c179bc166c9e325f05bc` (resume name-gate replies with
  extra customer details).
- GitHub Actions deploy run `26956771039` succeeded; production
  `/opt/noor/.release-sha` is
  `e4e7ecff52d71434e5f0c179bc166c9e325f05bc`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -
  8 passed, 0 failed.
- Final E2E scenario 1:
  `+79262810921#tj-pii-off-e2e-20260604170643`, conversation
  `20bf6801-e24a-4474-a015-2c4be31bc50e`; first message included SKU,
  quantity, name, individual, address, email, and phone; Noor returned
  `selection-confirmation`, saved all details, kept escalation `none`, and
  stored no `[PII-...]` placeholders.
- Final E2E scenario 2:
  `+79262810921#tj-pii-off-e2e-resume-20260604170643`, conversation
  `f9e669ef-b46e-43cf-9096-bd0e50167819`; first message without a name triggered
  `name-gate`, then `Victor PII Test, individual` resumed the original
  `2 x CH 616` request, consumed `name_gate_pending_request`, saved all details,
  kept escalation `none`, and stored no `[PII-...]` placeholders.
- Synthetic E2E conversations from this delivery were closed/resolved after
  readback. The real unsuffixed test phone thread was not mutated.

## Explicit Defers

- `tj-gh21` remains blocked on approved Wazzup WABA EN/AR templates.
- Global production `customer_facts_mode=shadow|enforce` remains a separate
  config decision. The deployed code was verified under temporary enforce and
  then restored to default disabled.
