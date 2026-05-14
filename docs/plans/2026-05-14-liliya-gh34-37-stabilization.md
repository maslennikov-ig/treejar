# Liliya GitHub Issues 34-37 Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the four new client-facing regressions from GitHub issues #34-#37 without reintroducing the gh12 name-gate, exact-quote, or escalation side effects.

**Architecture:** Keep the fixes deterministic and close to the existing routing boundaries. Bare quantity+SKU should be parsed before full LLM routing, product+quantity-only order_confirmation should be vetoed before manager notification, name-gate should persist and resume the prior substantive request, and product media should preserve internal selection metadata without sending a redundant customer-visible caption message.

**Tech Stack:** Python 3.13, FastAPI runtime, PydanticAI agent tools, SQLAlchemy async models, Wazzup messaging provider, pytest/ruff/mypy, Local Beads.

---

## Scope And Source Issues

- `tj-gh14`: stage epic for GitHub #34-#37.
- `tj-gh14.1` / GitHub #34: bare quantity+SKU such as `5 x CH 190` must enter exact_quote, not order_confirmation escalation.
- `tj-gh14.2` / GitHub #37: product+quantity alone must not escalate to manager without explicit fulfillment intent and logistics.
- `tj-gh14.3` / GitHub #36: after name collection, continue the customer's already stated request instead of asking a generic opener; inspect stage reset path.
- `tj-gh14.4` / GitHub #35: product recommendations should send text + image, not text + image + redundant caption text.

Do not comment on or close GitHub issues until explicit approval after implementation and verification.
Do not deploy, mutate production config, or run live WhatsApp/media/voice tests without explicit approval.

## Comments Analysis

- #34 has no comments. The issue body includes a concrete root-cause proposal: `_has_exact_commitment_intent` currently rejects bare quantity+SKU because there is no quote/stock/price term, then full LLM escalates. Adopt the idea, but implement a dedicated parser helper instead of making generic exact intent too broad.
- #35 has no comments. The issue body matches current code: `ProductMediaPayload.caption` flows into `send_wazzup_media_with_audit`, and Wazzup sends caption as a second text. Adopt, but preserve internal/audit caption data for later product selection resolution.
- #36 has no comments. The issue body points at greeting prompt and possible escalation reset. Adopt the context-loss diagnosis; verify reset separately because `src/services/conversation_reset.py` intentionally creates a new greeting conversation only for explicit Telegram reset.
- #37 has one comment from Liliya: the same product+quantity-only escalation happened twice in one conversation. Treat as P0 and add a deterministic tool-level veto, not prompt-only wording.

## Similar Resolved Work

- `tj-gh12.2` / GitHub #22/#28: SKU homoglyph and spaced-code parsing. Reuse `_normalize_sku_homoglyphs`, `_SKU_SIGNAL_RE`, and `_canonicalize_sku_signal`.
- `tj-gh12.16`: first-turn unknown-name gate must not create product media or escalation side effects.
- `tj-gh12.18`: name-only reply after name gate must capture name without escalation.
- `tj-gh12.19`: `1 x CH-620` missing-data quotation gate must avoid manager escalation.
- GitHub #29: first-turn name gate policy; #33: required quotation data gate.

## Documentation

- Context7 checked `/pydantic/pydantic-ai`: `@agent.tool` functions can use `RunContext` deps and return ordinary values. This supports adding a safe tool-level `order_confirmation` veto that returns an instruction string without calling manager notification.
- No new Wazzup API behavior is needed; local `send_media_detailed` already documents that captions are sent as a second text message.

## Parallel Decomposition Matrix

| Stream | Goal | Agent | Write Zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: exact quote + escalation guard | Fix #34 and #37 deterministic LLM routing and tool veto | local or worker | `src/llm/engine.py`, `src/llm/order_handoff.py`, `src/llm/prompts.py`, `tests/test_llm_engine.py`, `tests/test_llm_order_handoff.py` | Must be sequenced with any other `engine.py` edits | `uv run pytest tests/test_llm_engine.py tests/test_llm_order_handoff.py -v --tb=short` | sequential | Central shared `engine.py` and escalation behavior; conflict-prone. |
| B: name-gate request resume | Fix #36 pending-request preservation and stage-regression tests | local or worker after A | `src/llm/engine.py`, optional `src/services/escalation_state.py`, `src/services/conversation_reset.py`, `tests/test_llm_engine.py`, `tests/test_conversation_reset.py` | Depends on A if both edit routing around `process_message` | targeted `test_llm_engine.py` + reset tests | sequential | Shares the same `process_message` entrypoint as A. |
| C: product media caption suppression | Fix #35 without breaking selection metadata | worker if subagents are allowed | `src/llm/engine.py`, `src/services/chat.py`, `src/services/outbound_audit.py`, `tests/test_services_chat_batch.py`, `tests/test_outbound_audit.py`, `tests/test_product_images.py` | Can start after design is fixed; watch for `ProductMediaPayload` type conflicts | targeted media/audit tests | parallel-capable with B only if write ownership excludes `engine.py` or starts after payload shape is agreed | Mostly service/media path, but the payload type lives in `engine.py`. |
| D: orchestration and closeout | Beads, stage docs, issue comments after approval | local | `.codex/stages/tj-gh14`, `.codex/handoff.md`, Beads | After code streams pass | process verification + stage closeout | local | Small orchestration work. |

No built-in subagents have been launched for planning. If implementation is authorized, use subagents only for stream C after the `ProductMediaPayload` shape is decided; keep streams A/B central edits sequential.

## Task 1: RED Tests For Bare Quantity+SKU Exact Quote

**Files:**
- Modify: `tests/test_llm_engine.py`

**Step 1: Add parser regressions**

Add tests near existing exact quote parser tests:

```python
@pytest.mark.parametrize(
    ("text", "expected_qty", "expected_sku"),
    [
        ("5 x CH 190", 5, "CH-190"),
        ("CH 190 x 5", 5, "CH-190"),
        ("3 x 00-07024023", 3, "00-07024023"),
        ("5 x СН 190", 5, "CH-190"),
    ],
)
def test_extract_exact_quote_candidate_accepts_bare_quantity_sku(
    text: str, expected_qty: int, expected_sku: str
) -> None:
    candidate = extract_exact_quote_candidate(text)
    assert candidate is not None
    assert candidate.quantity == expected_qty
    assert candidate.sku == expected_sku
```

Add a negative control:

```python
@pytest.mark.parametrize(
    "text",
    [
        "what chairs do you have?",
        "show me options for desks",
        "5 tables for office ideas",
        "from 500 to 600 AED",
    ],
)
def test_extract_exact_quote_candidate_keeps_consultative_queries_out(text: str) -> None:
    assert extract_exact_quote_candidate(text) is None
```

**Step 2: Add process regression**

Adapt the existing `test_process_message_exact_quote_missing_details_accepts_quantity_x_sku` to cover:

```python
text = "5 x CH 190"
conv.customer_name = "Jio"
conv.metadata_ = {"quote_customer_details": {"name": "Jio"}}
```

Expected:
- response model ends with `|exact-quote-missing-details`
- `conv.escalation_status == "none"`
- `notify_manager_escalation` not awaited
- pending quote source is `exact_quote`
- pending quote item is `{"sku": "CH-190", "quantity": 5}`

**Step 3: Run RED**

Run:

```bash
uv run pytest tests/test_llm_engine.py::test_extract_exact_quote_candidate_accepts_bare_quantity_sku tests/test_llm_engine.py::test_extract_exact_quote_candidate_keeps_consultative_queries_out -v --tb=short
```

Expected before implementation: at least the bare quantity+SKU cases fail.

## Task 2: Implement Bare Quantity+SKU Parser

**Files:**
- Modify: `src/llm/engine.py`

**Step 1: Add dedicated helper**

Near `_SKU_SIGNAL_RE`, add a helper that uses the existing SKU regex instead of creating a broader intent rule:

```python
_BARE_QUANTITY_SKU_RE = re.compile(
    r"(?:(?P<qty1>\d{1,4})\s*(?:x|times|pcs?|pieces?|units?|qty|×)\s*"
    r"(?P<sku1>(?:[a-z]{1,4}[-\s]?\d{2,8}|\d{2,}(?:-\d{2,})+|[a-z0-9]+(?:-[a-z0-9]+)+))"
    r"|(?P<sku2>(?:[a-z]{1,4}[-\s]?\d{2,8}|\d{2,}(?:-\d{2,})+|[a-z0-9]+(?:-[a-z0-9]+)+))"
    r"\s*(?:x|times|pcs?|pieces?|units?|qty|×)\s*(?P<qty2>\d{1,4}))",
    re.IGNORECASE,
)
```

Add:

```python
def _extract_bare_quantity_sku_candidate(text: str) -> ExactQuoteCandidate | None:
    normalized_text = _normalize_sku_homoglyphs(text)
    match = _BARE_QUANTITY_SKU_RE.search(normalized_text)
    if match is None:
        return None
    raw_qty = match.group("qty1") or match.group("qty2")
    raw_sku = match.group("sku1") or match.group("sku2")
    if raw_qty is None or raw_sku is None:
        return None
    sku = _extract_sku_signal(raw_sku)
    if sku is None:
        return None
    return ExactQuoteCandidate(
        quantity=int(raw_qty),
        item_candidate=_normalize_sku_homoglyphs(raw_sku).strip(),
        sku=sku,
    )
```

**Step 2: Use it before generic intent gate**

At the top of `extract_exact_quote_candidate`:

```python
bare_candidate = _extract_bare_quantity_sku_candidate(text)
if bare_candidate is not None:
    return bare_candidate
```

Keep `_has_exact_commitment_intent` conservative for regular product text.

**Step 3: GREEN**

Run:

```bash
uv run pytest tests/test_llm_engine.py::test_extract_exact_quote_candidate_accepts_bare_quantity_sku tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_accepts_bare_quantity_x_sku -v --tb=short
```

Expected: new parser and process regressions pass.

## Task 3: RED Tests For Product+Quantity No-Escalation

**Files:**
- Modify: `tests/test_llm_engine.py`
- Modify: `tests/test_llm_order_handoff.py`

**Step 1: Add router controls**

In `tests/test_llm_order_handoff.py`, add:

```python
@pytest.mark.parametrize(
    "text",
    [
        "I need 2 mobile tables and 2 Skyland Novo 2400",
        "2 Skyland Novo 2400 and 2 conference tables",
        "5 x CH 190",
    ],
)
def test_product_quantity_without_fulfillment_is_not_high_confidence_order(text: str) -> None:
    assert is_high_confidence_first_turn_order(text) is False
```

Keep existing true cases for delivery/install/location/deadline.

**Step 2: Add LLM tool-veto process regression**

Use a `FunctionModel` that tries to call `escalate_to_manager` with `order_confirmation` for:

```python
message = "I need 2 mobile tables and 2 Skyland Novo 2400"
```

Expected:
- `notify_manager_escalation` is not awaited
- `conv.escalation_status == "none"`
- final response does not say manager was notified
- model receives a tool result telling it to continue sales/quotation support instead of escalation

**Step 3: Run RED**

Run:

```bash
uv run pytest tests/test_llm_order_handoff.py tests/test_llm_engine.py::<new_test_name> -v --tb=short
```

Expected before implementation: tool-veto test fails because `escalate_to_manager` notifies manager.

## Task 4: Implement Order Confirmation Guard

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `src/llm/order_handoff.py`
- Modify: `src/llm/prompts.py`

**Step 1: Add deterministic guard helper**

In `src/llm/engine.py`, add helper(s) near exact quote/order helpers:

```python
def _has_order_confirmation_fulfillment_evidence(text: str) -> bool:
    normalized = _normalize_text(_normalize_sku_homoglyphs(text))
    has_explicit_fulfillment = bool(
        re.search(
            r"\b(?:please deliver|arrange delivery|arrange installation|confirm the order|place the order|go ahead with delivery)\b",
            normalized,
        )
    )
    has_delivery_or_install = bool(
        re.search(r"\b(?:deliver|delivery|delivered|install|installation|installed)\b", normalized)
    )
    has_location_or_time = bool(_LOCATION_RE.search(normalized) or _TIMEFRAME_RE.search(normalized))
    return has_explicit_fulfillment or (has_delivery_or_install and has_location_or_time)
```

Prefer reusing existing `order_handoff.py` regexes if exposing a local helper is cleaner than duplicating regexes.

**Step 2: Veto unsafe order_confirmation tool calls**

At the start of `escalate_to_manager`, before `notify_manager_escalation`:

```python
if escalation_type == "order_confirmation" and not _has_order_confirmation_fulfillment_evidence(ctx.deps.user_query):
    logger.info("Vetoed order_confirmation escalation without fulfillment evidence")
    return (
        "Do not escalate this as an order confirmation yet. The customer has product and quantity only. "
        "Continue the sales conversation: confirm the requested items, check stock/pricing or offer a quotation, "
        "and ask for fulfillment details only when needed."
    )
```

This is the hard safety net for #37.

**Step 3: Prompt tightening**

In `ESCALATION GUIDELINES`, add explicit wording:

```text
Product name/SKU + quantity alone is never enough for order_confirmation, even if the product was just shown.
Do not infer delivery/order-placement intent from repeated product+quantity messages.
```

**Step 4: GREEN**

Run:

```bash
uv run pytest tests/test_llm_order_handoff.py tests/test_llm_engine.py::<new_order_veto_test> -v --tb=short
```

## Task 5: RED Tests For Name-Gate Pending Request Resume

**Files:**
- Modify: `tests/test_llm_engine.py`
- Modify: `tests/test_conversation_reset.py`

**Step 1: Store pending request on first unknown-name turn**

Add a test where a first-turn product request with unknown `customer_name` returns `name-gate` and stores metadata:

```python
assert conv.metadata_["name_gate_pending_request"]["text"] == "I want 2 tables"
```

**Step 2: Resume after name-only reply**

Add a test with:
- `conv.customer_name is None`
- `conv.metadata_["name_gate_pending_request"]["text"] = "I want 2 tables"`
- current message: `"Jio"` or `"My name is Jio"`

Expected:
- `conv.customer_name == "Jio"`
- response does not contain generic `"What do you need?"`
- `sales_agent.run` is called with runtime directive / user query that includes `"I want 2 tables"`
- no manager escalation
- pending request is consumed or marked consumed

**Step 3: Reset safety test**

In `tests/test_conversation_reset.py`, add a test documenting that explicit Telegram reset is the only path that creates a new greeting conversation. Do not change reset behavior unless issue evidence shows a reset command was involved.

**Step 4: Run RED**

Run:

```bash
uv run pytest tests/test_llm_engine.py::<new_name_gate_tests> tests/test_conversation_reset.py -v --tb=short
```

## Task 6: Implement Name-Gate Pending Request Resume

**Files:**
- Modify: `src/llm/engine.py`
- Possibly modify: `src/llm/prompts.py`

**Step 1: Add metadata helpers**

Use a bounded metadata payload:

```python
NAME_GATE_PENDING_REQUEST_KEY = "name_gate_pending_request"
```

Store only if the first-turn text has a substantive request:
- not just greeting/social text
- contains product/SKU/quantity/search terms
- trim to a safe max length, e.g. 1000 chars

**Step 2: Store on first-turn name gate**

In the `if is_first_turn and customer_name_was_unknown:` branch:

```python
await _store_name_gate_pending_request(db, conv, combined_text)
```

Keep gh12 behavior: return only name question, no product media, no escalation.

**Step 3: Resume on name-only reply**

In `_is_name_only_customer_detail_reply` branch:
- Store `customer_name` first.
- If pending request exists, do not return the generic static opener.
- Consume pending request.
- Continue into normal LLM routing using the pending request as the effective user requirement and a runtime directive:

```text
The customer just provided their name. Acknowledge it briefly, then continue the already stated request: <pending request>. Do not ask what they need again.
```

If the pending request is an exact quote candidate, let the exact_quote deterministic path handle it.

**Step 4: Prompt support**

In `STAGE_RULES["greeting"]`, add:

```text
If the customer already stated a product/request before giving their name, acknowledge the name and continue that prior request. Do not ask again what they need.
```

**Step 5: GREEN**

Run:

```bash
uv run pytest tests/test_llm_engine.py::<new_name_gate_tests> -v --tb=short
```

## Task 7: RED Tests For Product Media Captions

**Files:**
- Modify: `tests/test_services_chat_batch.py`
- Modify: `tests/test_outbound_audit.py`
- Modify: `tests/test_product_images.py`
- Modify: `tests/test_llm_engine.py`

**Step 1: Chat batch expectation**

Update `test_process_incoming_batch_sends_deferred_product_media_after_bot_reply`:

```python
assert mock_wazzup.send_media.await_args.kwargs["caption"] is None
mock_wazzup.send_text.assert_awaited_once()  # bot reply only, not product caption
```

**Step 2: Audit metadata expectation**

Add/update a test so product media can store internal caption metadata on the media audit row without creating a `message_type="caption"` audit row and without calling provider `send_text`.

**Step 3: Selection resume guard**

Update selection tests to prove prior product media remains selectable either via media audit `caption` metadata or another explicit metadata field.

Run RED:

```bash
uv run pytest tests/test_services_chat_batch.py::test_process_incoming_batch_sends_deferred_product_media_after_bot_reply tests/test_outbound_audit.py tests/test_product_images.py -v --tb=short
```

## Task 8: Implement Product Media No-Caption Sends

**Files:**
- Modify: `src/llm/engine.py`
- Modify: `src/services/chat.py`
- Modify: `src/services/outbound_audit.py`

**Step 1: Make product media caption internal**

Option preferred:
- Add `send_caption: bool = True` and `audit_caption: str | None = None` to `send_wazzup_media_with_audit`.
- Set `media_audit.caption = audit_caption or caption`.
- Only create/send caption audit rows when `send_caption and caption`.
- Pass `caption if send_caption else None` to provider.

**Step 2: Use no-caption mode for product media**

In `_send_deferred_product_media` and immediate product-media send path:

```python
await send_wazzup_media_with_audit(
    ...,
    caption=None,
    audit_caption=item.caption,
    send_caption=False,
)
```

Quotation PDFs should keep the existing default and continue sending their intentional caption.

**Step 3: Update selection lookup**

Change `_load_product_media_caption_rows` so it can read product media rows with `message_type == "media"` and `source == "product_media"` where `caption` or `content` has the internal selection caption.

**Step 4: GREEN**

Run:

```bash
uv run pytest tests/test_services_chat_batch.py tests/test_outbound_audit.py tests/test_product_images.py tests/test_llm_engine.py::test_process_message_confirms_selection_from_prior_product_media_captions -v --tb=short
```

## Task 9: Integration Sweep

**Files:**
- No new files expected beyond tests and implementation files.

Run targeted suites:

```bash
uv run pytest tests/test_llm_order_handoff.py tests/test_llm_engine.py -v --tb=short
uv run pytest tests/test_services_chat_batch.py tests/test_outbound_audit.py tests/test_product_images.py -v --tb=short
uv run pytest tests/test_conversation_reset.py -v --tb=short
```

Run full gates:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
scripts/orchestration/run_stage_closeout.py --stage tj-gh14
```

## Task 10: Delivery And Issue Reconciliation

**Files:**
- Create/update: `.codex/stages/tj-gh14/summary.md`
- Create/update: `.codex/stages/tj-gh14/artifacts/*.md`
- Modify: `.codex/handoff.md`

Steps:

1. Commit implementation in small commits grouped by Beads stream.
2. Push and deploy only after explicit approval.
3. Run post-deploy API smoke if deploy is approved:

```bash
uv run python scripts/verify_api.py --base-url https://noor.starec.ai
```

4. Run controlled production E2E only with explicit approval and bounded synthetic phone strategy.
5. Comment/close GitHub #34-#37 only after approval and after deployed evidence exists.

## Acceptance Checklist

- #34: `5 x CH 190`, `CH 190 x 5`, `3 x 00-07024023`, and Cyrillic homoglyph variants enter exact_quote and do not escalate.
- #37: product+quantity-only messages never create order_confirmation escalation; explicit delivery/order-placement examples still do.
- #36: name-only reply after name gate continues the prior request and does not ask generic `What do you need?`.
- #35: customer sees no redundant product caption text after product image; internal selection metadata still works.
- All targeted and full gates pass.
- Beads `tj-gh14.1` through `tj-gh14.4` are updated with evidence before close.
