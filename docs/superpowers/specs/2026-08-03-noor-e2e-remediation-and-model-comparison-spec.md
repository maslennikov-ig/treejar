# Noor E2E Remediation and Model Comparison

**Date:** 2026-08-03  
**Stage:** `tj-ee5f`  
**Level:** integration  
**Scope owner:** `tj-ee5f.1`

## Outcome

Fix the deterministic dialogue, catalog, and scoring defects found by the
production acceptance run before comparing models. Then select the main-chat
and background models independently in an isolated model-battle harness. A
winner-only production acceptance is a later live boundary requiring explicit
authority.

The frozen `AC-01` through `AC-30` snapshot and digest remain unchanged. The
Wazzup delivery/read-status proof in `tj-ee5f.5` remains an external follow-up:
Wazzup support has confirmed a provider bug and no polling API exists.

## Decisions

- Use current `origin/main`; commit `a2f245c` is already in that history.
- Keep one active stage, `tj-ee5f`; do not create another umbrella epic.
- Keep production runtime configuration unchanged during the isolated battle.
- Do not add a per-conversation model override.
- Select the main-chat and background winners independently.
- Do not exclude low-coverage scenarios from scoring. Unexpectedly low
  applicability is an evaluator failure.
- Do not impose an arbitrary ratio for static replies. A static reply is
  forbidden when it replaces a model-owned recommendation.
- Exact scenario transcripts belong only in fixtures or external raw evidence.
- Do not grow the product system prompt. Prefer typed state, pure decisions,
  catalog facts, and compact configuration.
- Public REST/webhook contracts and the database schema do not change. New
  Redis/metadata fields are versioned and read legacy state safely.

## Dialogue and quotation state (`tj-ee5f.8`)

### Typed state

Add two internal enums:

```text
QuoteConsent = not_requested | deferred | declined | granted
QuoteLifecycle = consultation | quote_offered | quote_requested |
                 collecting_details | creating | created
```

Persist the fields in the versioned dialogue metadata. Legacy
`quote_on_hold`/`quotation_hold` is read as `deferred`, but new writes use only
the typed fields.

A pure reconciler derives `sales_stage`, `active_flow`, consent, lifecycle,
and typed slots from confirmed events and performed actions. It must not merely
advance the sales stage by one model-requested edge. Impossible combinations
are removed before routing:

- budget/price/quantity text is not a delivery address;
- product descriptions containing “individual” do not make the customer an
  individual;
- an explicit company wins over ambiguous customer-type inference;
- a quote refusal is `declined`, not a temporary pause;
- a correction updates only the corrected fact.

Product selection may create a quote frame but does not start detail
collection. Address and customer details enter the quote state only after
`QuoteConsent.granted`. The quotation executor has a fail-closed consent guard
before its first Zoho, PDF, or Wazzup operation.

Refusal, objection, delivery questions, and requirement corrections remain
typed priority intents; no additional prompt stage is introduced. Exact-SKU
requests do not receive similar products or a quote offer unless requested.

## Catalog decision (`tj-ee5f.7`)

Introduce an internal `CatalogDecision` containing:

- normalized requirements and product families;
- selected catalog rows and covered seat quantities;
- budget calculation and numerical gap;
- unknown properties and explicit safe claims;
- final recommendation;
- `StockSnapshot` values with `source` and `as_of`.

Treejar Catalog remains the source of product identity, descriptions, and
customer-facing prices. Zoho Inventory is the source of current stock. Within
one turn, a SKU has one authoritative stock value.

The product-search budget is derived from requested families:

```text
min(6, max(2, 2 * number_of_product_families))
```

The public `search_products` signature does not change. When the budget is
nearly exhausted, return a typed warning. When exhausted, synthesize from
facts already found instead of making another search call.

Selection priority is:

1. hard constraints and complete quantity coverage;
2. compatibility;
3. minimal SKU count;
4. budget;
5. relevance;
6. lowest price.

Choose one SKU per family by default, and at most two only when stock requires
it. A partial solution is valid only with the numerical uncovered quantity, a
verified way to close it, and one closing question.

Validate model output against `CatalogDecision`. A deterministic safe fallback
must be labelled in evidence. It is a functional failure in recommendation or
comparison scenarios, even if the customer-visible text is safe. Materialized
catalog facts may constrain or repair unsupported claims, but may not replace
the model-owned recommendation wholesale.

## Evaluator and E2E (`tj-ee5f.12`)

Determine applicability per rule using typed events: catalog use, quotation,
CRM action, refusal, next step, and language. EN/AR/RU detection must not rely
on English keyword lists.

For every block:

- exclude rules explicitly marked not applicable;
- omit a block with no applicable rules from the denominator;
- normalize remaining block weights to a total of `/30`;
- publish coverage diagnostics;
- mark unexpectedly low coverage as evaluator failure without removing the
  scenario from aggregate statistics.

The final result is independently mapped for a blind orchestration audit. A
score difference greater than two points or any applicability disagreement is
`EVAL_DISAGREEMENT` and blocks acceptance.

E2E waits for a terminal turn state with a bounded timeout rather than a fixed
five-second sleep. Production `prompt:*` keys are never cleared. Comparisons
use a protected copy of the effective prompt plus SHA-256; raw prompt and raw
evidence stay outside Git.

## Isolated model battle (`tj-ee5f.13`)

The harness must never call Treejar, Zoho, Wazzup, or production databases and
must not mutate runtime model configuration or business side effects.

### Main chat candidates

1. `z-ai/glm-5.2` (baseline)
2. `deepseek/deepseek-v4-flash-0731`
3. `openai/gpt-5.6-luna`
4. `xiaomi/mimo-v2.5-pro`

Use the matching first-party provider slug with:

```text
provider.only=[owner]
provider.allow_fallbacks=false
provider.require_parameters=true
reasoning.enabled=false
tool_choice=auto
max_tokens=2200
```

Do not send `temperature`, `top_p`, `seed`, penalties, `stop`, or
`parallel_tool_calls`. Record requested/resolved model, endpoint/provider,
effective parameters, tokens, cache usage, cost, and latency.

Hard cases are `S01`, `S02`, `S03`, `S04`, `S05`, and `S08`. Round 0 runs one
attempt per model/case. A functional hard failure eliminates the candidate.
Survivors run two additional replications per case. Only 429, 5xx, and
transport timeout permit one retry, and both attempts remain evidence.

Before paid work, a free metadata preflight validates availability, parameters,
and current prices. Per-model spend is capped at `min(USD 1, 1.25 * estimate)`.

A winner has no hard failure, a median of at least `20/30` on every case, an
average of case medians at least `24/30`, no invented product/commercial facts,
and no loss of locale, intent, quantity, or quote refusal. Rank by quality,
objective assertions, stability, tool discipline, p95 latency, and cost. A
difference below one point or below observed dispersion is a tie; an unresolved
tie keeps GLM-5.2.

### Background candidates

Compare current `deepseek/deepseek-v4-flash` plus all four main-chat candidates
on six short gold fixtures: corrected EN summary, Arabic summary, RU exact-SKU
no-quote extraction, quote consent, customer-fact conflicts, and red flags with
structured evaluator output.

Round 0 runs each model once on all fixtures. Survivors run twice more on the
three most discriminating fixtures. Require 100% valid schemas and critical
fields, at least 95% total accuracy, no invented facts, and no PII leakage. A
tie keeps the current background model.

The sealed report records main and background winners separately. Only if a
challenger wins and configuration must change is `tj-ee5f.14` created.

## Verification and acceptance

Focused red/green coverage is required for state reconciliation, quote consent,
slot conflicts, catalog coverage/budget/stock coherence, EN/AR/RU
applicability, exact `/30` arithmetic, multi-turn battle cases, provider
pinning, parameter filtering, blind mapping, retry accounting, cost caps, and
terminal polling.

After integration, run the release gate once:

```text
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
```

Paid comparison, configuration mutation, push, deploy, and production calls
are separate external boundaries. After explicit authority, deploy the exact
reviewed SHA and run one winner-only production pass over S01-S10 plus EN/AR/
voice canaries, Zoho/PDF/readback/cleanup, and CRM no-quote cleanup. Every
scenario must score at least `20/30`, the mean at least `24/30`, with no
functional failure or unresolved P0/P1. A semantic defect reruns only its
affected scenario.

`tj-ee5f.1` may close after product acceptance. The epic and stage remain open
until the future Wazzup `tj-ee5f.5` status proof is available.
