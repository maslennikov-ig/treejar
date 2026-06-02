# Dialogue State Kernel Eval Plan

Status: draft for stage `tj-gh20`

## Purpose

The eval suite proves that the Dialogue State Kernel preserves the current
customer-safe routing behavior before any route is allowed to run in enforce
mode.

The first corpus is machine-readable JSON under
`tests/fixtures/dialogue/`. Each case describes:

- replay messages;
- initial durable state from `Conversation.metadata_`;
- selected runtime mode;
- expected kernel route and flow;
- expected slots after the turn;
- side-effect policy;
- issue tags and risk notes.

## Runner Contract

The runner should:

1. Load every `*.json` file under `tests/fixtures/dialogue/`.
2. Validate fixture schema version and required fields.
3. Build the kernel state from `initial_metadata`.
4. Replay messages in order, preserving assistant/user roles.
5. Assert the final decision:
   - `expected.route`;
   - `expected.flow`;
   - `expected.slots`;
   - `expected.side_effects_allowed`;
   - `expected.allowed_side_effects`.
6. For `shadow` cases, assert `side_effects_allowed=false` and no provider
   calls were attempted.

The runner should use local models/mocks such as PydanticAI `TestModel` or
`FunctionModel` where an LLM boundary is necessary. It should not use live
OpenRouter, Wazzup, Zoho, Telegram, GitHub, or production data.

## Required Scenarios

### GitHub #36: name-gate resume

Replay:

1. Customer asks for products before the bot knows their name.
2. Bot asks for the name and stores the pending request.
3. Customer replies with a bare or short name.

Expected:

- route `name_gate_resume`;
- flow returns to `product_discovery` or `quotation_build`, depending on the
  stored request;
- `customer_name` is stored;
- `name_gate_pending_request` is consumed or represented as resumed;
- no manager handoff.

### GitHub #37: product quantity is not order confirmation

Replay product/brand plus quantity without fulfillment evidence, for example
`2 Skyland Novo and 2xten`.

Expected:

- route `policy_no_handoff` or `product_clarify`;
- flow `product_discovery`;
- no `order_confirmation` escalation;
- no manager notification.

### GitHub #39: SKU selection after product choice

Replay a bot product-choice prompt followed by `I need 6 CH 616`.

Expected:

- route `product_selection_legacy_delegate` in v1 shadow/enforce telemetry;
- fallback to legacy for customer-visible selection confirmation until the kernel
  owns stock/price/quote side effects end to end;
- selected SKU/model slot includes `CH 616`;
- quantity is `6`;
- no manager handoff.

### GitHub #40: quotation context hardening

Replay active quotation selection followed by terse details such as
`Lil, 1 dubay`.

Expected:

- route `quote_resume_missing_details`;
- flow `quotation_build`;
- `pending_quote_selection` remains present;
- usable name/address details are stored;
- only missing fields are requested;
- no generic opener and no quotation creation until all required fields exist.

### GitHub #47: product preference answer after an interruption

Replay:

1. Assistant asks a product preference question, for example LUMA/private vs
   NOVO/open team workspace.
2. Customer asks a bounded interruption, such as `Can delivery be arranged?`.
3. Bot answers the delivery question without closing the product-preference
   frame.
4. Customer says `I prefer more open for team`.

Expected:

- route `product_preference_answer`;
- flow `product_discovery`;
- slot `workspace_preference=open`;
- active product-preference frame is marked `fulfilled`;
- bot continues NOVO/open product handling;
- no manager handoff and no pending escalation.

Single-turn regression:

- If the preference reply immediately follows the assistant question, the route
  must still pass; this protects the #47 hotfix while the durable frame path is
  rolled out.

### Expected-answer frame ambiguity

Replay:

1. Assistant asks a product preference question.
2. Assistant later asks a quantity question without the preference frame being
   fulfilled.
3. Customer says `the second one`.

Expected:

- if both frames can plausibly interpret the answer, route
  `expected_answer_clarify`;
- response asks which pending question the customer is answering;
- no frame is fulfilled by guessing;
- no manager handoff.

### Expected-answer frame expiry

Replay:

1. Assistant asks a product preference question.
2. More than the configured max customer turns or TTL passes.
3. Customer sends a terse ambiguous phrase such as `open`.

Expected:

- expired frame is not used for routing;
- route falls back to legacy/product clarification;
- expired frame is retained only in bounded history with `status=expired`;
- no stale product preference is silently applied.

### Expected-answer hard blocker override

Replay:

1. Assistant asks a product preference question.
2. Customer replies `I prefer open but I need a manager for a refund complaint`.

Expected:

- hard escalation blocker wins over the frame match;
- frame remains active or interrupted according to implementation policy;
- manager/hard escalation path remains available;
- no product route suppresses complaint/refund handling.

### GitHub #11: post-quotation hold

Replay a post-quotation or late-stage customer flow that involves a bulk order,
sample request, delivery concession, discount negotiation, or showroom visit.

Expected:

- route `post_quotation_hold`;
- flow `manager_review_hold`;
- decision records `blocked_pending_lilia=true`;
- side effects remain disabled in shadow;
- issue #11 is not closable from kernel evidence alone.

### Long-dialog stress

Replay a conversation with at least 12 turns spanning name capture, product
discovery, exact models, generic product clarification, SKU selection, delivery
question, quote detail collection, and a later short follow-up.

Expected:

- durable slots survive across turns;
- active expected-answer frames survive bounded interruptions;
- expected-answer frames expire after configured TTL or max customer turns;
- exact model numbers are not misread as quantities;
- quote context is not lost after unrelated delivery/assembly questions;
- no manager handoff unless a true escalation trigger appears.

### Multilingual and mixed Latin-Cyrillic SKU variants

Replay English, Russian, and mixed Latin/Cyrillic SKU text:

- `CH 616`
- `CH-616`
- `CH616`
- `ch   616`
- `СН 616` where `С` and `Н` are Cyrillic characters
- mixed-language phrases such as `Нужно 6 CH 616` and `I need 6 СН 616`

Expected:

- all supported variants normalize to the same product-selection intent when
  product-choice context exists;
- bare SKU quantity without product-choice context remains guarded;
- non-SKU Cyrillic text is not forced into SKU parsing.

## Acceptance For tj-gh20 v1

- The spec documents legacy/shadow/enforce modes and side-effect constraints.
- The eval doc names all required issue scenarios.
- JSON fixtures cover the required scenarios, validate with `python -m json.tool`,
  and selected cases execute through the kernel runner in tests.
- The runner short-circuits graph execution in legacy mode.
- Shadow mode writes bounded traces with zero kernel side effects.
- Enforce mode handles only allowlisted flows and falls back to legacy for
  exact SKU+quantity selection until a later stage owns quote side effects.
- Expected-answer frame fixtures cover immediate answers, delayed answers after
  interruption, ambiguous answers, expired frames, and hard escalation blockers.

## Out Of Scope

- Enabling production shadow or enforce mode.
- Removing the legacy runtime path.
- Closing GitHub #11.
- Mutating GitHub, production, or provider systems.
