# tj-r1f3 deterministic customer-output enforcement

## Contract and root cause

The exact AI path is:

1. `process_message()` shapes the customer turn and runs the core PydanticAI
   agent/tools.
2. `_build_llm_response()` unmasks `result.output` and applies existing
   closed-question and opening repairs.
3. The new pure guard classifies and enforces the final model-generated text.
4. Assistant-frame capture, deferred-media selection, and `LLMResponse`
   construction consume only the enforced text.
5. The chat layer later persists and delivers that `LLMResponse.text`.

The failure was not a parsing or prompt-tail assembly defect. Attempt 3 proved
that an advisory prompt can still yield two prohibited customer semantics, and
the application trusted that model output. The smoke evaluator separately had
a narrower actor grammar that missed `arrange for our team to check and get
back`.

## TDD lane and RED evidence

Lane: required. This changes observable customer output and shared release
classification.

Initial exact command:

```text
uv run pytest tests/test_llm_engine.py::test_process_message_repairs_specific_product_showroom_trial tests/test_llm_engine.py::test_process_message_repairs_delegated_future_stock_check tests/test_scripts_verify_model_routes.py::test_sales_case_evaluation_rejects_exact_attempt_3_outputs -q --tb=short
```

Before production changes, the medical process test failed because the returned
text still contained `experience the chair`; the smoke test failed because the
exact delegated stock answer evaluated as `passed=True, failures=[]`. The first
stock process fixture initially took an existing detail/policy route, so its
input was narrowed to a known model route without changing the exact captured
model output.

Corrected stock boundary reproducer:

```text
uv run pytest tests/test_llm_engine.py::test_process_message_repairs_delegated_future_stock_check -q --tb=short
```

It failed because the returned text still contained both `arrange for our team
to check` and `get back to you`. The pure-module RED then failed collection
with `ModuleNotFoundError: src.llm.grounding_output`, proving the component did
not exist before implementation.

## Smallest safe implementation

- Added one pure module under `src/llm/` with typed violation/action results.
- Classification is sentence- and assertion-aware, ignores quoted text, scopes
  stock checks to stock/inventory context, and excludes unrelated checks.
- Bounded repair removes only violating sentences. Empty or still-unsafe repair
  uses deterministic localized EN/AR fallback.
- `_build_llm_response()` invokes it once after existing repairs and before
  frame/media capture. Static and code-owned responses remain outside the guard.
- Structured warning data is limited to action, typed reasons, model, and
  language; raw answer text and PII are never logged.
- The smoke evaluator imports the two production classifiers. Production never
  imports the script.
- Provider usage, model route, tokens, and cost remain unchanged. There is no
  retry, second model call, tool replay, network request, or additional cost.

Tradeoff: sentence removal is deliberately conservative and can omit a safe
clause that shares an unsafe sentence. That is preferred to semantic rewriting;
localized fallback handles cases where no safe sentence remains.

## GREEN and regression evidence

Focused matrix:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py::test_process_message_repairs_specific_product_showroom_trial tests/test_llm_engine.py::test_process_message_repairs_delegated_future_stock_check tests/test_llm_engine.py::test_process_message_media_follows_enforced_customer_text tests/test_llm_engine.py::test_process_message_uses_arabic_grounding_fallback tests/test_llm_engine.py::test_tools_get_stock_returns_zoho_confirmed_price_and_stock tests/test_llm_engine.py::test_tools_get_stock_malformed_inventory_result_is_unresolved tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `57 passed`.

Affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `396 passed`.

Static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/llm/grounding_output.py src/llm/engine.py
```

Result: all passed.

The broader focused Mypy probe that also named
`scripts/verify_model_routes.py` exposed an unchanged baseline
`no-any-return` at line 622. The implementation did not touch that return
boundary; fixing unrelated script typing was intentionally not bundled.

## Review correction RED/GREEN

Independent review identified three reproducible boundary gaps:

1. A successful current-turn stock tool result was not available to the guard,
   so `I can confirm availability: 7 units are currently in stock` was replaced.
2. `Our inventory team will check availability and get back to you` bypassed
   the first-person delegated grammar.
3. `experience the AX-E1` bypassed the product-noun trial grammar.

The focused RED command collected eight cases and produced seven intended
failures plus one existing unconfirmed fail-closed pass. The failures showed an
unsupported `inventory_confirmed` argument, replacement of a real tool-backed
confirmation, and unchanged pure/process/smoke outputs for the two grammar
gaps.

The correction is bounded:

- successful `get_stock` evidence is propagated from copied run dependencies
  to the per-turn dependencies consumed by `_build_llm_response()`;
- present confirmation is exempted only for the narrow current-stock wording
  and only when that evidence flag is true;
- without evidence the same wording still fails closed and smoke still rejects
  it;
- explicit inventory/warehouse-team future callbacks and SKU-shaped showroom
  trials add two classifier grammar branches.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py::test_present_stock_confirmation_requires_current_turn_inventory_evidence tests/test_llm_grounding_output.py::test_classify_grounding_output_covers_review_regressions tests/test_llm_engine.py::test_process_message_preserves_tool_backed_present_stock_confirmation tests/test_llm_engine.py::test_process_message_rejects_present_stock_confirmation_without_tool_evidence tests/test_llm_engine.py::test_process_message_repairs_review_regression_outputs tests/test_scripts_verify_model_routes.py::test_sales_case_evaluation_covers_review_regressions -q --tb=short
```

Result: `8 passed`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `404 passed`.

## Re-review clause-boundary correction

The second independent review confirmed three more bounded classifier edges:

1. Evidence-backed present confirmation was overfit to the colon wording and
   rejected `I can confirm AX-E1 is currently in stock` plus the equivalent
   quantity/SKU form.
2. The prior allow span skipped a greedy direct match that also contained a
   later `I will check inventory again later` clause.
3. Mixed `check stock and delivery` was treated as unrelated because delivery
   was evaluated before the explicit stock object.

The focused RED command collected seventeen cases: nine failed for the intended
reasons and eight existing/negative controls passed. It proved failures at the
pure and `process_message()` boundaries, plus the mixed-object smoke false
negative.

The correction remains narrow:

- the evidence allowance recognizes bounded present confirmation with
  availability, SKU, and optional quantity forms;
- only the completed present-confirmation span is masked before future
  classification;
- same-sentence bounded repair retains that confirmed span and removes the
  later future clause;
- explicit stock/inventory in a mixed check object wins unsafe classification,
  while standalone delivery, dimension, and colour objects remain safe.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py::test_present_stock_confirmation_requires_current_turn_inventory_evidence tests/test_llm_grounding_output.py::test_confirmed_present_stock_does_not_authorize_later_future_check tests/test_llm_grounding_output.py::test_mixed_stock_and_delivery_check_is_unsafe_but_delivery_only_is_safe tests/test_llm_engine.py::test_process_message_preserves_tool_backed_present_stock_confirmation tests/test_llm_engine.py::test_process_message_removes_future_check_after_tool_backed_confirmation tests/test_llm_engine.py::test_process_message_repairs_review_regression_outputs tests/test_scripts_verify_model_routes.py::test_sales_case_evaluation_rejects_re_review_stock_regressions tests/test_scripts_verify_model_routes.py::test_sales_case_evaluation_preserves_unrelated_delivery_check -q --tb=short
```

Result: `17 passed`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `418 passed`.

## Third re-review structural stock-classifier correction

The third independent review exposed that present and future stock semantics
were still coupled:

1. `Current stock is unconfirmed. I can confirm AX-E1 is available.` bypassed
   the guard because `available` was absent from the stock context.
2. Evidence-backed natural present forms using an SKU after the availability
   colon, `has 7 units`, `out of stock`, and `not currently in stock` were
   misclassified as future promises.
3. `warehouse` was treated as strong stock context before delivery was
   considered, so a delivery-timing callback was removed.

The RED runs were separated by contract boundary. The pure module produced 12
intended failures, runtime produced 6, and shared smoke produced 12. The failures
proved the missing typed present violation, the rejected natural evidence-backed
forms, the unblocked `available` assertion, and the false-positive delivery
repair.

The structural correction is bounded:

- added `UNVERIFIED_STOCK_CONFIRMATION` as a distinct typed reason;
- present stock confirmation is classified independently and gated only by
  successful current-turn inventory evidence;
- recognized present spans are excluded from future scanning regardless of
  evidence, while a later future clause remains independently unsafe;
- present grammar covers bounded SKU/quantity positive and negative stock
  statuses without widening into general factual-claim filtering;
- future checks distinguish strong stock words from weak warehouse context;
  explicit delivery wins over warehouse alone, but explicit stock, inventory,
  availability, available, unavailable, out-of-stock, and mixed
  stock-and-delivery objects remain unsafe;
- the shared smoke evaluator imports the same unverified-present classifier and
  reports a distinct failure reason.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py -q --tb=short
uv run pytest tests/test_llm_engine.py -q --tb=short -k 'preserves_tool_backed_present_stock_confirmation or rejects_present_stock_confirmation_without_tool_evidence or preserves_delivery_only_warehouse_check or removes_future_check_after_tool_backed_confirmation'
uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short -k 'covers_review_regressions or rejects_unverified_present_stock_forms or rejects_re_review_stock_regressions or rejects_strong_future_stock_context or preserves_unrelated_delivery_check'
```

Results: `40 passed`; `18 passed, 348 deselected`; and
`18 passed, 33 deselected`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `457 passed`.

Fresh static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/
```

Results: Ruff and format passed; Mypy passed over 163 source files.

## Fourth re-review bounded present-assertion correction

The fourth review identified three remaining bounded gaps:

1. The present status grammar accepted only one `not`/`currently` order and
   misclassified `not in stock`, `currently not in stock`, and `not available`
   as future checks even with tool evidence.
2. Direct SKU-shaped present statements such as `AX-E1 is available` were
   outside the evidence gate unless introduced by `I can confirm`.
3. Warehouse callbacks for plural unrelated objects such as dimensions,
   measurements, sizes, colours, and colors were falsely classified as stock
   checks.

Initial RED at each boundary produced 12 intended failures in pure, runtime,
and smoke tests. A clause-boundary follow-up added comma/coordination and
conditional controls; it produced 2 pure, 2 runtime, and 3 smoke failures for
the intended missing coordination coverage and one legacy smoke-control wording
collision.

The correction remains structural and narrow:

- a shared optional modifier grammar accepts `currently`, `not`,
  `not currently`, and `currently not` before bounded stock states;
- the SKU-shaped subject/status grammar is reused for both prefixed
  confirmations and direct present assertions;
- direct assertions require an assertion clause boundary or `but`/`however`
  coordination and exclude quoted text plus `if`/`whether`/`when` conditions;
- quantity-only status remains valid only under the explicit confirmation
  prefix, preventing expansion into arbitrary availability prose;
- singular and plural unrelated object lexemes share one grammar;
- runtime and shared smoke continue to consume the same production present
  classifier;
- the pre-existing name-gate resume test no longer fabricates an unsupported
  no-tool `CH-620 is available` claim. Its fixture now proves request
  continuation with neutral wording, preserving the test's actual objective.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py -q --tb=short
uv run pytest tests/test_llm_engine.py -q --tb=short -k 'preserves_tool_backed_present_stock_confirmation or rejects_present_stock_confirmation_without_tool_evidence or preserves_delivery_only_warehouse_check or preserves_conditional_sku_stock_control or name_only_reply_resumes_pending_name_gate_request'
uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short -k 'rejects_unverified_present_stock_forms or preserves_unrelated_warehouse_check or preserves_conditional_sku_stock_control or rejects_strong_future_stock_context'
```

Results: `64 passed`; `49 passed, 348 deselected`; and
`37 passed, 36 deselected`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `534 passed`.

Fresh static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/
```

Results: Ruff and format passed; Mypy passed over 163 source files.

## Final bounded contraction, boundary, and quote correction

The final bounded review found three grammar and wiring gaps:

1. Common negative present copulas `isn't` and `aren't`, including curly
   apostrophes, were not part of the evidence-gated present grammar.
2. Direct SKU assertions after em/en dashes, newlines, and newline list markers
   were outside the assertion-boundary grammar.
3. Single-quoted text was not masked, so a quoted delegated future-stock promise
   could be treated as an asserted promise. The smoke evaluator also normalized
   raw replies before shared classification, destroying newline structure and
   curly quote pairing.

RED was symmetric across the customer-output path: pure, runtime, and shared
smoke each produced 12 intended failures.

The correction is limited to shared grammar primitives and classifier wiring:

- the bounded present copula accepts `is`, `are`, `isn't`, and `aren't`;
- curly apostrophes are normalized after quote masking with a same-length
  replacement, preserving match offsets used by bounded repair;
- assertion boundaries include em dash, en dash, newline, and newline-prefixed
  hyphen, asterisk, or bullet list items;
- paired straight and curly single quotes are masked only when they form
  standalone quote delimiters; word-internal apostrophes remain visible, so
  contractions and possessives are not mistaken for quotes;
- conditional `if`/`whether`/`when` controls remain unchanged;
- the smoke evaluator passes raw reply text to all imported production
  grounding classifiers and keeps normalized text only for its legacy local
  checks.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py -q --tb=short
uv run pytest tests/test_llm_engine.py -q --tb=short -k 'preserves_tool_backed_present_stock_confirmation or rejects_present_stock_confirmation_without_tool_evidence or preserves_conditional_sku_stock_control'
uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short -k 'rejects_unverified_present_stock_forms or preserves_conditional_sku_stock_control'
```

Results: `80 passed`; `65 passed, 359 deselected`; and
`37 passed, 52 deselected`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `593 passed`.

Fresh static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/
```

Results: Ruff and format passed; Mypy passed over 163 source files.

## Bounded quote/list interaction correction

The interaction review found two exact composition defects:

1. Production correctly ignored a single-quoted present claim, but the smoke
   evaluator independently scanned raw phrases such as `currently in stock`
   and falsely rejected the otherwise valid reply.
2. A direct SKU list item immediately scoped by `whether:`, `if:`, or `when:`
   was treated as asserted because newline/list boundary recognition discarded
   the preceding conditional scope.

RED produced three conditional-list failures in pure and runtime tests. Smoke
produced those three plus the quoted-present false rejection.

The correction is intentionally small:

- removed the duplicate smoke raw phrase loop for bounded SKU present states;
  the imported quote-aware production classifier now owns that decision;
- retained the existing broad smoke pattern for separate non-SKU inventory
  assertions such as unsupported quantity/warehouse claims;
- extended only the immediate conditional suffix grammar across an optional
  colon and one newline/list marker;
- kept ordinary newline/list assertions unsafe when no immediate
  `if`/`whether`/`when` introducer exists.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py::test_classify_grounding_output_preserves_safe_controls tests/test_llm_grounding_output.py::test_direct_sku_stock_assertion_requires_current_turn_inventory_evidence -q --tb=short
uv run pytest tests/test_llm_engine.py -q --tb=short -k 'preserves_conditional_sku_stock_control or rejects_present_stock_confirmation_without_tool_evidence'
uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short -k 'preserves_conditional_sku_stock_control or rejects_unverified_present_stock_forms or rejects_contradictory_safe_sounding_answers'
```

Results: `43 passed`; `41 passed, 387 deselected`; and
`59 passed, 34 deselected`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `605 passed`.

Fresh static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/
```

Results: Ruff and format passed; Mypy passed over 163 source files.

## Final quote-aware broad smoke correction

Removing the duplicate raw phrase loop fixed quoted SKU alignment but exposed a
separate broad smoke regression. With an otherwise valid unconfirmed prefix,
these non-SKU claims passed:

- `The product is currently in stock.`
- `This chair is in stock.`
- `The chair is available now.`

The production guard intentionally remains SKU-bounded, so expanding runtime
classification would have crossed scope. The correct boundary is shared quote
visibility for the smoke-only broad commercial assertion checks.

RED proved the public helper was absent and all three unquoted broad claims
passed. Their three quoted equivalents already passed as required.

The small correction:

- exposes `visible_grounding_text(raw_text)` from the production grounding
  module;
- preserves source length and word-internal apostrophes while masking supported
  quote spans;
- reuses that helper for all internal production quote masking;
- restores the smoke broad phrase loop over quote-masked normalized text;
- applies the existing broad `_STOCK_ASSERTION_RE` to the same visible text;
- leaves shared SKU classification and runtime enforcement scope unchanged.

Focused GREEN:

```text
uv run pytest tests/test_llm_grounding_output.py::test_visible_grounding_text_masks_quotes_but_preserves_word_apostrophes -q --tb=short
uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short -k 'unquoted_broad_stock_assertions or quoted_broad_stock_assertions or preserves_conditional_sku_stock_control or rejects_unverified_present_stock_forms'
```

Results: `1 passed`; `47 passed, 52 deselected`.

Fresh affected test files:

```text
uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short
```

Result: `612 passed`.

Fresh static checks:

```text
uv run ruff check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run ruff format --check src/llm/grounding_output.py src/llm/engine.py scripts/verify_model_routes.py tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py
uv run mypy src/
```

Results: Ruff and format passed after organizing the new test import; Mypy
passed over 163 source files.

## Remaining environment-level checks

- Independent delta review.
- Full release tests and process verification owned by stage closeout.
- Deployment and exact release/model/service/API readback.
- Only with fresh explicit authorization: bounded provider smoke and manual
  semantic review.

No external or live action was performed in this stream.
