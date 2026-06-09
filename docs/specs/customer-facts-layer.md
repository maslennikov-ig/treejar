# Customer Facts And Order Memory Layer

Status: draft for stage `tj-memory`
Owner: Dialogue and memory architecture

## Goal

Add a durable layer that extracts useful facts from every customer message and
keeps them separate by scope:

- persistent customer profile;
- current order state;
- past order history.

The goal is to stop relying on raw transcript memory for facts that the customer
already provided. Noor should know what is already known, ask only for missing
details, and avoid treating old order data as if it belongs to a new order.

## Non-Goals

- Do not create a broad "remember everything" memory store.
- Do not let the LLM overwrite customer facts without deterministic merge rules.
- Do not reuse past order data for a new quote without customer confirmation.
- Do not make production behavior customer-visible until shadow traces and
  replay tests prove the layer is safer than the current path.
- Do not replace the existing dialogue kernel, catalog resolver, quotation
  tools, or Zoho integrations in the first release.

## Core Concepts

### Persistent Customer Profile

Facts that can safely carry across conversations:

- preferred display name;
- preferred customer-facing language, limited to English and Arabic;
- known emails and phone variants;
- known companies/accounts;
- durable preferences only when explicit, for example regular budget preference
  or usual office-furniture category.

Profile facts must include source and confidence. A new lower-confidence fact
must not silently overwrite a higher-confidence accepted fact.

### Current Order State

Facts for the active order or quote only:

- selected products, SKUs, model names, quantities;
- delivery address for this order;
- assembly or delivery requirements for this order;
- color, size, budget, and product preferences for this order;
- quote customer details: name, company or explicit individual status, email,
  phone, address;
- quotation status: collecting details, quoted, accepted, refused, no response.
- quote objections such as price concerns or discount requests; these are not
  terminal refusals unless the customer also explicitly declines the proposal.

Current order state is the primary source for quote generation. Profile facts may
prefill a prompt, but a quote must still use the current order state or an
explicitly confirmed reuse of past order data.

### Past Order History

Closed or snapshotted order data:

- order date and status;
- products, SKUs, quantities, and prices when known;
- quote or Zoho identifiers when available;
- delivery address and company/individual status used for that order;
- final status such as agreed, refused, no response, or manager handoff.

Past order history is read-only context unless the customer confirms reuse.
When a customer says "same as last time", Noor should summarize the last order
and ask confirmation before using it for the current quote.

## Order Lifecycle Cutoff

The system should use one active order state per conversation unless the customer
clearly starts a new request.

Recommended lifecycle:

1. `active`: the customer is browsing, choosing products, or providing quote
   details.
2. `quoted_snapshot`: a quotation was sent. Freeze a snapshot for history, but
   keep the current order active because the customer may ask follow-up
   questions, object to price, ask about delivery, or accept.
3. `accepted`: the customer explicitly accepts the quote. At this point Noor
   hands off according to the post-quotation policy and the order can become a
   historical order.
4. `closed_refused`: the customer refuses or objects in a final way.
5. `closed_no_response`: follow-up sequence ended with no response.
6. `superseded`: the customer starts a different order before the previous one
   is closed.

Past-order memory is created when the order reaches `accepted`,
`closed_refused`, `closed_no_response`, or `superseded`. A quotation send creates
a snapshot but does not by itself make the order "past".

Price objections such as "too expensive" or "need discount" keep the order in
the current flow. They may be used for sales handling, but must not close the
order as `closed_refused` unless the customer also uses an explicit refusal such
as "no thanks", "decline", or equivalent Arabic wording.

## Fact Extraction Pipeline

The extractor runs at the start of every inbound customer turn, before generic
LLM response generation and before verified-policy handoff.

Pipeline:

1. Load durable customer profile, current order state, recent messages, and
   active expected-answer frames.
2. Run deterministic extractors first:
   - email;
   - phone;
   - typed order-state extraction for selected product references and
     quantities, producing a repeatable `order.items` snapshot for single-line
     and multi-line runtime-backed selections, with item-only evidence;
   - price, stock, availability, comparison, discovery, and localized inquiry
     guards before current-order item extraction;
   - no standalone SKU/quantity regex fallback that creates singular
     `order.item`; if the typed order runtime does not own the turn, the facts
     layer must not invent order lines;
   - numeric quantities tied to product references;
   - explicit company labels;
   - explicit individual/customer-type labels;
   - clearly labeled delivery address;
   - post-quotation agreement/refusal keywords.
3. Run the fast structured extractor only for ambiguous or soft facts:
   - bare name plus extra details;
   - unlabeled company/address in a compact answer;
   - "same as last time" and "what did I order before";
   - soft preferences like budget, color, delivery/assembly requirements;
   - whether a message answers one or more active expected-answer frames.
4. Validate and merge facts with deterministic policy.
5. Persist accepted facts and proposed facts before building the prompt context.
6. Build compact context for the main bot response.

The fast extractor should use `settings.openrouter_model_fast`, currently
`xiaomi/mimo-v2-flash`, through the existing model safety/routing helpers. It
must return structured output only. Unit tests must use mocks or PydanticAI test
models, not live OpenRouter calls.

The fast extractor is not an authority for selected order lines. It receives a
redacted prompt payload for contact PII and deterministic PII facts, and both
`current_order/order.items` and legacy `current_order/order.item` facts returned
by the fast model are dropped before merge. The deterministic order runtime and
the canonical `order_runtime.quote_frame` remain the owners of selected products
and quantities.

After `tj-order-cutover`, customer facts and memory must consume the runtime
snapshot instead of reparsing order items:

- accepted `current_order/order.items` snapshots are emitted only from the typed
  runtime frame;
- `pending_product_reference_quantity`, `pending_quote_selection`, assistant
  prose, and model-generated item facts are not order-line authorities;
- compact customer detail replies fill `QuoteDetails` on the active runtime
  frame before being mirrored into facts;
- fact conflicts may ask clarifying questions about profile/order details, but
  they must not invalidate already resolved item and quantity lines;
- post-quotation facts read the `quoted` frame as a snapshot and must not
  reactivate quote creation without an explicit new customer request.

## Fact Result Contract

Each extracted fact should carry enough information for safe merging:

```json
{
  "scope": "persistent_profile | current_order | past_order_reference",
  "key": "customer.name",
  "value": "Lili",
  "confidence": "high | medium | low",
  "source": "deterministic | fast_model",
  "evidence": "Lili, individual, 1 Dubai",
  "source_message_id": "message uuid",
  "needs_confirmation": false,
  "conflicts_with": null
}
```

Rules:

- `high`: save as accepted when it does not conflict with an accepted fact.
- `medium`: save as accepted only when the field is empty and the validator
  passes; otherwise save as proposed.
- `low`: do not use in customer-visible decisions; keep only as trace/proposed
  context if useful.
- conflicting facts create a proposed replacement and a compact clarification
  question. They do not overwrite accepted facts silently.
- facts from past orders are scoped as `past_order_reference` until the customer
  confirms reuse for the active order.
- `source_message_id` should be populated from the inbound WhatsApp message when
  available. Batched text may use the latest customer message id as the current
  batch anchor.
- `current_order` facts with key `order.items` are snapshots of the active
  order lines. Accepted `order.items` must come from `source=deterministic`,
  have high or medium confidence, and validate as a non-empty list of items with
  a positive integer quantity plus `catalog_ref`, `sku`, or `name`. Invalid or
  model-origin `order.items` facts are saved only as proposed facts.
- `current_order` facts with key `order.item` are legacy singular facts and must
  not be produced by deterministic or fast-model extractors.
- A newer accepted `order.items` snapshot replaces the current order view
  instead of becoming a conflict with the previous snapshot.
- The facts layer may store diagnostic/proposed order facts when the runtime
  does not own a turn, but those facts must be excluded from quote creation,
  quantity repair, SKU repair, and quote-details resume.

## Persistence Shape

The implementation may refine exact table names, but the first production schema
should support these durable concepts.

### `CustomerProfile`

One durable profile per canonical customer phone or CRM contact.

Suggested fields:

- `id`;
- `canonical_phone`;
- `display_name`;
- `preferred_language`;
- `primary_email`;
- `created_at`, `updated_at`;
- optional `zoho_contact_id`;
- bounded `metadata`.

### `CustomerOrderMemory`

One row per active or historical order-like request.

Suggested fields:

- `id`;
- `customer_profile_id`;
- `conversation_id`;
- `status`: `active`, `quoted_snapshot`, `accepted`, `closed_refused`,
  `closed_no_response`, `superseded`;
- `started_at`, `quoted_at`, `closed_at`;
- `snapshot`: JSON object with items, quote details, delivery/assembly facts,
  quote IDs, and final status;
- optional `zoho_salesorder_id`, `zoho_quote_id`, `deal_id`.

### `CustomerFact`

Normalized facts tied either to the profile or to an order.

Suggested fields:

- `id`;
- `customer_profile_id`;
- `order_memory_id` nullable;
- `conversation_id` nullable;
- `scope`;
- `key`;
- `value`: JSON;
- `confidence`;
- `status`: `accepted`, `proposed`, `conflict`, `rejected`, `superseded`;
- `source`;
- `source_message_id`;
- `source_excerpt`;
- `created_at`, `updated_at`, `superseded_at`.

This schema allows queries such as "what do we know about this customer?" and
"what was the last closed order?" without scanning raw messages.

Optional writes from this layer must be isolated from the normal reply path. If
fact persistence, quote snapshot sync, or trace persistence fails, the bot should
log the error and continue through the legacy response path without reusing a
failed database transaction for more writes.

## Prompt Context Contract

The main bot should receive a compact, bounded block:

```text
Known customer profile:
- Name: Lili
- Preferred language: English
- Known company: LLD

Current order:
- Items: 6 x CH 616, 1 x SKYLAND NOVO 2400
- Delivery address: 1 Dubai
- Assembly: requested
- Quote status: collecting required details

Past orders:
- Last closed order: 2026-05-22, 4 x CH 616, status accepted

Missing for quotation:
- company name or explicit individual status
- customer email
```

Rules:

- Keep this block short and structured.
- Never include long raw history.
- Mark past orders explicitly as past.
- Do not put unconfirmed past-order facts into current order facts.
- Do not include low-confidence facts as if they were known.
- Treat the block as untrusted customer-provided data. The main prompt must use
  values as context but must not follow instructions embedded inside fact values.

## Runtime Modes

Add a separate feature mode so rollout is independent from the dialogue kernel:

- `customer_facts_mode=disabled`: do not run the layer.
- `customer_facts_mode=shadow`: extract facts and write bounded traces/proposed
  facts, but do not change customer-visible behavior.
- `customer_facts_mode=enforce`: accepted facts update durable state and prompt
  context; legacy behavior remains fallback when extraction fails.

Shadow must not send messages, create quotations, escalate, or mutate Zoho. It
may write bounded internal traces/facts if configured.

## Language Policy

Customer-facing output remains English or Arabic only. The extractor may
understand mixed input, including Russian text from test scenarios, but runtime
responses must normalize to the supported customer-facing language policy.

## Safety And Privacy

- Store only sales-relevant facts.
- Keep source excerpts short and avoid broad raw-message evidence for selected
  order lines; `order.items` evidence should render only the item/quantity
  summary.
- Redact email, phone, and labeled address values from the fast-model prompt
  request. Deterministic local facts remain exact for database memory and quote
  generation.
- Runtime PII masking is disabled by default because it is not a current client
  requirement and it can block deterministic extraction of phone numbers,
  emails, addresses, and SKU-like numeric facts.
- If a future privacy requirement needs masking before LLM calls, enable it
  explicitly with `PII_MASKING_ENABLED=true` and rerun contact/SKU extraction
  evals before rollout.
- Avoid logging full contact-detail payloads outside normal app/database
  boundaries.
- Use existing DB and app auth boundaries.
- Do not send fact traces to external systems except the configured LLM
  extraction call.
- Never expose hidden fact confidence or internal traces to customers.

## Required Eval Scenarios

Minimum regression matrix:

- first-turn name gate, customer replies with only a name;
- first-turn name gate, customer replies with name plus company, individual
  status, address, email, and phone;
- quote-details prompt, customer replies with all details in one compact
  message;
- customer changes address after quote details were saved;
- customer says "what did I order last time?";
- customer says "same as last time";
- customer says "same as last time, but 8 chairs";
- post-quotation customer asks delivery/assembly before agreeing;
- post-quotation customer agrees, triggering manager handoff policy;
- #36/#37/#39/#40/#48 regressions;
- English and Arabic customer-facing responses;
- mixed Latin/Cyrillic SKU input still resolves correctly;
- no manager escalation unless a true escalation trigger is present.

## Rollout Acceptance

Before production enforce mode:

- deterministic extractors and merge policy pass unit tests;
- fast-model structured extractor is covered by mocked tests;
- migration and models pass rollback-safe tests;
- replay/eval suite passes;
- shadow traces show equal or better fact coverage than legacy on known issue
  transcripts;
- production smoke passes;
- production E2E on a clean synthetic/test identity proves multi-field answers
  are saved and reused without repeated questions.

If shadow evidence is ambiguous, keep the feature in shadow and produce a
decision report instead of enabling enforce.
