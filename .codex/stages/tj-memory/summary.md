# Stage tj-memory: Customer Facts And Order Memory Layer

Updated: 2026-06-04
Status: spec and task graph created; implementation pending
Branch: `codex/tj-memory-customer-facts-layer`
Base: `origin/main` at `d49abcfc0606102b2098880245723e6fda999193`
Beads: `tj-memory` epic with child tasks `tj-memory.1` through `tj-memory.7`

docs-reviewed: updated - new architecture spec and implementation plan added.
graph-reviewed: no-change-needed - Graphify is not configured; no
`graphify-out/GRAPH_REPORT.md` or `[knowledge_graph]` configuration exists.

## Goal

Create a durable facts layer so Noor extracts useful information from every
customer message, separates persistent customer profile from active order state
and past orders, and avoids re-asking or losing already-provided facts.

## Current State

- GitHub #48/tj-gh49 is closed and delivered.
- Production still runs the dialogue kernel in enforce mode only for
  `product_selection`.
- This stage starts a new architecture stream. It does not change production
  behavior yet.

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
| B | `tj-memory.2` | Persistence and memory service skeleton | db specialist/worker | models, migration, service tests | A | model/migration tests | parallel later | Disjoint from extractor |
| C | `tj-memory.3` | Fact extractor | worker | `src/llm/fact_extractor.py`, tests | A | extractor tests | parallel later | Pure extraction boundary |
| D | `tj-memory.4` | Order lifecycle | worker | `src/services/customer_memory.py`, lifecycle tests | B interface | service tests | parallel later | Service-level boundary |
| E | `tj-memory.5` | Engine/prompt integration | orchestrator | `src/llm/engine.py`, prompt/context tests | B+C+D | targeted LLM tests | sequential | Central routing file |
| F | `tj-memory.6` | Regression/eval suite | worker/local | fixtures/tests | C+E | replay + engine tests | parallel later | Test-only after interfaces |
| G | `tj-memory.7` | Rollout and production evidence | orchestrator/deploy specialist | config/artifacts | full green | smoke/E2E | sequential final | External delivery |

## Verification

Passed for this spec-only step:

- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-memory/artifacts/tj-memory.1-spec.md`
- `scripts/orchestration/run_process_verification.sh`

Full code gates will run after implementation starts.

## Explicit Defers

- `tj-gh21` remains blocked on approved Wazzup WABA EN/AR templates.
- Production deploy/enforce mode for this layer requires separate approval and
  production evidence.
