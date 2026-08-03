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
- Owner decision on `R-01` (2026-08-03): use
  `dialogue_kernel_mode=enforce` as the code default now. Keep
  `dialogue_kernel_enforced_flows` empty, so typed reconciliation and
  write-back govern the default path while customer replies remain
  model-owned. A stored runtime override can still select another mode; this
  local round does not change runtime configuration.
- Do not add a per-conversation model override.
- Select the main-chat and background winners independently.
- Do not exclude low-coverage scenarios from scoring. Unexpectedly low
  applicability is an evaluator failure. **Amended after review:** keeping the
  scenario is correct, but the score must not be published as a normal score.
  See `R-06`.
- Do not impose an arbitrary ratio for static replies. A static reply is
  forbidden when it replaces a model-owned recommendation. **Amended after
  review:** that rule needs a measurement to be enforceable. See `R-03`.

### Budget decisions for the paid battle (owner-confirmed 2026-08-03)

These supersede the unresolved GLM-5.2 cap question in `.codex/handoff.md`.

- `max_tokens=2200` stays.
- Candidates run in ascending exact-provider estimated cost: cheapest first.
- The per-model hard cap of USD 1 is **not** raised for any candidate.
- Unused allowance from a completed candidate carries forward to the next
  candidate, but can never lift a candidate above its own USD 1 cap.
- A pre-call reservation is conservative; after each response it is replaced by
  the provider-reported actual cost, and the freed difference returns to the
  shared allowance. The conservative pre-flight estimate therefore sizes the
  reservation and no longer blocks the round on its own.
- A response cut off by `max_tokens` is recorded `TRUNCATED`. It is a harness
  budget event, not a model quality failure, and is not scored as one.
- The full `S01`-`S10` production suite runs only for the winning pair.
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

Keep `max_tokens=2200`; do not reduce answer capacity to satisfy the theoretical
all-retries maximum. Within each round, run candidates in ascending exact
first-party estimated cost. Unused batch allowance carries forward to later
candidates, but no candidate may borrow enough to exceed its own per-model cap.
Before every request, reserve its worst-case cost; after the response, reconcile
the reservation to provider-reported actual cost so unused output allowance is
released. Stop before a request that cannot fit the remaining cap.

`finish_reason=length` is `TRUNCATED`, not a model-quality score. Preserve the
attempt, stop that candidate/configuration for review, and do not automatically
retry it. The complete production S01-S10 suite is run only for the selected
main/background pair, not for every comparison candidate.

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
challenger wins and configuration must change is a new task created for it.
(`tj-ee5f.14` is the harness repair task added by the review round.)

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

## Review outcome (independent, Opus 5, 2026-08-03)

Reviewed range `f831e6c..3701c1e` on `codex/tj-ee5f-quality-model-battle`, four
read-only streams plus gate re-execution. Local gates are green at `3701c1e`:
ruff, ruff format, mypy (165 files), `pytest tests/` 2750 passed 19 skipped,
`run_process_verification.sh`.

Engineering quality is high where the work landed. Evaluator applicability and
`/30` normalization are done well; the fail-closed consent guard before Zoho,
PDF, and messaging is stricter than required; harness isolation from production
is genuine; no acceptance-scenario wording was hardcoded into product code.

The stage is not complete. Of the six deterministic acceptance failures, only
`S05` is closed. The paid comparison must not run until `R-09` through `R-15`
are fixed, because the harness in its reviewed form cannot return a winner
other than the incumbent.

### Must-fix

| id | Defect | Evidence |
|---|---|---|
| `R-01` | Typed dialogue state does not govern the default path. `dialogue_kernel_mode` defaults to `legacy`; `run_dialogue_kernel` returns before the stage write-back, so the reconciler, recomputed stage, and typed consent are inert. Verified by replay: `legacy` ends at `greeting`, `shadow`/`enforce` reach `solution`. | `src/core/config.py:53`, `src/dialogue/runner.py:112-124`, `:159-161` |
| `R-02` | `S08`/`S10` reproduce verbatim. An explicit refusal is stored as `DEFERRED`; `QuoteConsent.DECLINED` is never written by the engine. Both consumers render duplicated "on hold" literals from untyped memory, and the forced `quote_on_hold=True` when `not offer_quote_for_turn` survives. | `src/llm/engine.py:8802-8806`, `:9646`, `:13087`, `:13100`, `:15080-15088` |
| `R-03` | `S04` reproduces. `_materialize_verified_catalog_facts` still replaces the model answer wholesale; unchanged in range. No substitution-rate instrumentation exists, and two deterministic paths are tagged `provider_reported`, so any threshold on `usage_provenance` undercounts by construction. Split cost provenance from text provenance. | `src/llm/engine.py:14285-14288`, `:2578`, `:14340`, `:15357` |
| `R-04` | `S03` reproduces. `StockSnapshot` is write-only on the live path; its only readers sit behind a five-condition gate that runs with tools disabled. `search_products` prints local `Product.stock`. `source="catalog"` and an `unconfirmed` provenance are never constructed. | `src/llm/engine.py:12608-12613`, `:12354`, `:1271` |
| `R-05` | The premature-detail gate is still lexical. A delivery-address request without the word "quotation" passes; conversely a `granted` conversation without an active frame is intercepted and re-asked. | `src/llm/engine.py:9521-9552` |
| `R-06` | Low coverage now scores higher than before. An `S02`-shaped profile with four applicable rules yields `30.0/30`, `rating="excellent"`, and stays in the aggregate; the `low_coverage` flag exists but is published nowhere outside `LLMAttempt.result_json`. Keep the scenario, publish coverage, and stop `/30` renormalization from converting a collapsed denominator into a top score. | `src/quality/schemas.py:316`, `:103`, `tests/test_quality_evaluator.py:250-397` |
| `R-07` | The owner-facing quality report renders normalized `points` against nominal `weight`, printing impossible values such as `7.5/6`; not-applicable blocks print `0.0/6`. Live via `src/quality/job.py:346-366`. | `src/services/notifications.py:332` |
| `R-08` | The product prompt contradicts the enforced limit: it forbids more than two `search_products` calls while the code now allows up to six, so `S01` coverage cannot improve. Remove the numeric rules; net prompt size must not grow. | `src/llm/prompts.py` rules 10, 11, 13 vs `src/llm/engine.py:2669-2671` |
| `R-09` | The core round cannot produce a winner. `critical_required_phrases` equals `required_phrases` in all six hard cases, so every gate-passing candidate scores exactly `30.0/30`, the gap is always zero, and the tie always keeps the incumbent. Critical phrases must be a strict subset, and `required_phrases` must carry quality checks that can fail partially without elimination. | `scripts/model_battle_cases.py:418-419, 459-460, 484-485, 514-515, 533-534, 551-552`; `scripts/model_battle.py:1503`, `:1529`, `:873-883` |
| `R-10` | The round is also forced to `blocked`. Disagreement detection requires exact equality of `applicable_rules`, but the judge receives a bare sorted string array with no label dictionary, and the `±2.0` band against a constant `30.0` obliges the judge to score at least `28/30` everywhere. | `scripts/model_battle.py:634-690`, `:2144`, `:2248-2256` |
| `R-11` | Blind judge scores are computed, sealed, and then discarded: core ranking uses only the deterministic checklist, and the judge contributes a binary `critical_failure` gate. Decision `D-2` is satisfied in form only. | `scripts/model_battle.py:2219-2265`, `:796-799` |
| `R-12` | Cost accounting is dead and blocks the budget decisions above. `usage: {"include": true}` is never sent, so `usage.cost` never arrives, the post-hoc cap always passes on zeros, the cost tie-break compares zeros, and reported spend will be `0.00`. Actual-cost reconciliation, carry-forward, and cheapest-first ordering all depend on fixing this first. | `scripts/model_battle.py:1320-1345`, `:1183-1185`, `:1200-1221`; cf. `src/llm/safety.py:396-397` |
| `R-13` | In `S05` the allowed-number set is empty, so any digit fails grounding and eliminates the candidate from the whole round — a numbered list is enough. | `scripts/model_battle.py:1495`, `:84`; `scripts/model_battle_cases.py:114-122` |
| `R-14` | Live scoring and rescoring build different grounding sets, so a candidate can be eliminated in round 0 by a stricter rule than the one the report applies. Extract one shared builder. | `scripts/model_battle.py:1628-1635` vs `:2313-2321` |
| `R-15` | Blindness is procedural, not mechanical: `sales_results.jsonl` sits in the same output directory with plaintext `model` and `final_content`, and labels come from one rotated permutation, so identifying one candidate reveals all. Separately, `tool_results` are withheld from the judge although the rubric requires it to detect invented commercial facts. | `scripts/model_battle.py:2794`, `:1656-1667`, `:507-516`, `:2122-2147` |
| `R-16` | Coverage planning returns `None` instead of a partial plan with a numeric gap, and one unsolved family voids the whole plan including solved families. `CatalogDecision` has no gap field and the validator treats incomplete coverage as an error. Required by decision `D-3` and by plan Task 2. | `src/llm/engine.py:1846-1851`, `:2001-2002`, `:1277-1285`, `:1321-1322` |
| `R-17` | Model identity and parameter hygiene are unaddressed in product code: a model id that is not in the OpenRouter catalog, a hardcoded reasoning-disabled set, and cache control gated on an `anthropic/` prefix. No capability table and no machine-readable `unsupported` field in run artifacts. | `src/core/config.py:41`, `src/llm/safety.py:48-49`, `scripts/model_battle.py:1826-1849` |
| `R-18` | Stage documents overclaim. The summary states the deterministic causes behind all six failures are remediated; four are not. One artifact sentence is simply false: it says the deterministic materializer runs only behind a `verified-catalog-functional-failure` marker, which describes one materializer and omits the unmarked one in `R-03`. | `.codex/stages/tj-ee5f/summary.md:12-15`; `.codex/stages/tj-ee5f/artifacts/tj-ee5f.7-8-quality-remediation.md:45`, `:144-146` |
| `R-19` | Hard-case content does not match the scenario ids it carries, so the round is no longer comparable with the `a2f245c` acceptance evidence: `S01` is name-gate resume, `S02` is English rather than Arabic, `S03` is no-match rather than the stock conflict, `S04` is stock consistency rather than the consent gate, `S05` is quote decline rather than the twelve-seat configuration. | `scripts/model_battle_cases.py:381-556` |
| `R-20` | The owner-confirmed budget rules are not implemented: no cheapest-first ordering, no carry-forward of released allowance, no `TRUNCATED` status, and the pre-flight estimate still hard-blocks above USD 1 instead of sizing a reservation. | `scripts/model_battle.py:2728-2745`, `:128-178` |

### High-value improvements

- Search allowance uses `planning.families` accumulated across turns, so a
  single-family follow-up inherits a limit of six; the stated acceptance case
  "single family keeps a cap of two" fails on the live path, and no test covers
  it (`src/llm/engine.py:1739-1744`).
- `DialogueState.load` ignores the canonical `order_runtime.quote_workflow`
  once kernel fields exist, giving three representations of consent
  (`src/dialogue/state.py:153-161`).
- A refusal after a sent quotation cannot become `declined`: the
  post-quotation branch precedes the consent signal, and the reducer rewrites
  to `GRANTED` (`src/dialogue/runner.py:243-262`, `src/dialogue/reducer.py:61-64`).
- `_has_canonical_quote_workflow` blocks conversations started before deploy,
  which have no canonical key. Four `create_quotation` tests had to be handed
  consent artificially to keep passing (`tests/test_e2e_tools.py`).
- `_QUOTE_DECLINE_RE` is tested before `_QUOTE_DEFER_RE`, so "no quotation for
  now, maybe later" classifies as `DECLINED` (`src/dialogue/runner.py:571-601`).
- The noise rule uses `pstdev` across all case-replication scores, mixing
  between-case variance into a between-replication measure and biasing toward
  the incumbent; tool discipline is missing from the tie-break chain
  (`scripts/model_battle.py:819`, `:866`).
- `parallel_tool_calls=false` is not set for GLM-5.2, the only candidate that
  supports parallel calls, while the gate requires exact tool-sequence equality.
- The background profile lists both the disputed model id and its dated
  replacement; if the former is absent from the catalog the background round
  cannot start, and the tie baseline points at it (`scripts/model_battle.py:63-65`).
- `--repetitions` defaults to 2 while hard profiles require exactly 3, and
  `--output-dir` defaults into a different closed stage's directory.
- No system-prompt digest exists anywhere in the tree, so section 5 cannot put
  one in the winner acceptance manifest. `TURN_SETTLE_SECONDS` never existed in
  this repository; that half of the harness hygiene item is out of scope here.
- `select_hard_profile_winner` is tested only on `practical_tie`; the `winner`
  branch is uncovered, and the fixtures use scores the real scorer cannot
  produce, which is why `R-09` survived the suite.

### Open question for the owner

`R-01` decides how much of this stage is real. Either the typed dialogue kernel
becomes the default runtime path in this stage, or the stage states plainly
which fixes stay inert, behind which flag, and when they are switched on. This
is a product and rollout decision, not a technical default.

Resolved by the owner on 2026-08-03: use `enforce` as the code default now,
with an empty enforced-flow allowlist. Focused tests must prove that typed state
is reconciled and persisted while legacy/model response generation remains the
fallback.
