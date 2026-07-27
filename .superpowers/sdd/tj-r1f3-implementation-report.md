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

## Remaining environment-level checks

- Independent delta review.
- Full release tests and process verification owned by stage closeout.
- Deployment and exact release/model/service/API readback.
- Only with fresh explicit authorization: bounded provider smoke and manual
  semantic review.

No external or live action was performed in this stream.
