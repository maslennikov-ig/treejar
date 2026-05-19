# Dialogue State Kernel Specification

Status: draft for stage `tj-gh20`
Owner: Dialogue State Kernel stream

## Goal

Introduce a LangGraph-based Dialogue State Kernel that owns durable routing
state for sales conversations without changing customer-visible behavior until
the shadow data proves that the kernel matches the current runtime.

The kernel is a state and routing layer, not a replacement for the existing LLM,
catalog, quotation, manager handoff, or messaging providers. In v1 it must make
legacy behavior observable first, then gradually enforce only explicitly
allowlisted flows.

## Non-Goals For v1

- Do not add `langgraph-checkpoint-postgres` in v1.
- Do not move conversation truth out of the existing database model.
- Do not create, send, or mutate Zoho quotations, PDFs, WhatsApp messages,
  Telegram alerts, GitHub issues, or Beads from shadow execution.
- Do not close GitHub #11 until Lilia answers the pending clarification
  questions. The kernel may model #11 as a hold state, but closure remains
  blocked.

## Runtime Modes

### `legacy`

- Default mode.
- The existing runtime remains the source of behavior.
- The bridge may call the runner to read config, but LangGraph graph execution
  must short-circuit before graph invocation.
- No new customer-visible side effects are allowed from the kernel.
- This mode is the fallback for any missing config, unknown mode, or kernel
  initialization failure.

### `shadow`

- The existing runtime remains authoritative for replies and side effects.
- The kernel receives the same conversation input and current metadata, then the
  legacy path remains authoritative for the actual customer-visible outcome.
- Shadow execution must be side-effect free:
  - no provider calls;
  - no outbound audit rows;
  - no escalation creation or notification;
  - no quotation/PDF/SaleOrder creation;
  - no mutation outside the shadow namespace in `Conversation.metadata_`;
  - no GitHub, Beads, deploy, or production-control mutation.
- Shadow output is persisted only as diagnostic metadata under
  `metadata_["dialogue_kernel"]["traces"]`, with bounded entries and redacted
  message excerpts where needed.
- Shadow mismatches are telemetry/eval findings, not runtime failures.

### `enforce`

- The kernel may make routing decisions only for an explicit allowlist.
- Any route not in the allowlist must fall back to legacy behavior.
- The initial allowlist is narrow:
  - first-turn unknown-name gate with pending request preservation;
  - name-only reply that resumes a pending name-gate request;
  - product/SKU reference clarification when quantity is missing;
  - product/SKU quantity selection telemetry after an assistant product-choice
    prompt, with legacy fallback until the kernel owns stock/price/quote side
    effects end to end;
  - quotation detail collection while `pending_quote_selection` exists;
  - hold state for #11 bulk/sample/discount ambiguity.
- Enforce mode must still block side effects unless the selected route declares
  the side-effect family and the family is allowlisted for that route.
- If the kernel cannot load state, cannot parse metadata, or produces an
  unknown route, the runtime must fall back to legacy for that turn.

## Durable State

The durable state lives in `Conversation.metadata_`.

The kernel state namespace is `dialogue_kernel`:

```json
{
  "dialogue_kernel": {
	  "state": {
	      "version": 1,
	      "thread_id": "conversation:<uuid>",
	      "active_flow": "product_selection",
      "slots": {
        "customer_name": null,
        "company": null,
        "customer_type": null,
        "delivery_address": null,
        "selected_items": [],
        "pending_product_refs": ["SKYLAND NOVO 2400"],
        "quote_sent": false,
        "post_quotation_status": null
      },
      "last_question": null,
      "trace_history": []
    },
    "traces": []
  }
}
```

Rules:

- Existing metadata keys such as `customer_name`, `name_gate_pending_request`,
  `pending_quote_selection`, and `quote_customer_details` remain supported.
- The kernel may mirror legacy keys into `dialogue_kernel.state.slots`, but v1 must
  preserve compatibility with existing readers.
- `thread_id` must be stable per conversation and suitable for LangGraph
  checkpoint addressing. Use `conversation:<uuid>` or another deterministic
  conversation-scoped value.
- v1 uses the existing row persistence for `Conversation.metadata_`; it must not
  require the Postgres LangGraph checkpointer package.
- Metadata writes must be bounded and schema-versioned. Invalid or oversized
  kernel state is ignored and replaced from legacy metadata.

## LangGraph Shape

The initial graph is a small `StateGraph` over the persisted kernel state:

1. `load_state`: read legacy metadata and normalize slots.
2. `classify_turn`: infer the route candidate from the new user message,
   previous assistant turn, and durable slots.
3. `guard_side_effects`: derive allowed side-effect families for the selected
   route and mode.
4. `route_flow`: produce the next route/flow and slot updates.
5. `persist_shadow_or_enforce`: write bounded diagnostic state in shadow mode
   or allowed durable state in enforce mode.

The graph output is a decision object:

```json
{
  "route": "product_selection_legacy_delegate",
  "flow": "product_discovery",
  "slots": {},
  "side_effects_allowed": false,
  "allowed_side_effects": [],
  "fallback_to_legacy": true,
  "reason_codes": ["sku_selection_after_product_choice"]
}
```

## Route Contract

Routes must be stable strings because replay fixtures and telemetry depend on
them.

| Route | Flow | Purpose |
| --- | --- | --- |
| `name_gate` | `identity_capture` | Ask for name before first-turn sales work when the customer is unknown. |
| `name_gate_resume` | `product_discovery` or `quotation_build` | Store a name-only reply and resume the preserved request. |
| `product_clarify` | `product_discovery` | Ask clarifying product questions without escalation. |
| `product_selection_legacy_delegate` | `product_discovery` | Recognize exact SKU/model quantity turns but leave quote side effects to legacy in v1. |
| `selection_confirmation` | `quotation_build` | Future route for kernel-owned selected SKU/model and quantity confirmation. |
| `quote_resume_missing_details` | `quotation_build` | Preserve pending quote context and ask only for missing quote details. |
| `policy_no_handoff` | `product_discovery` | Veto manager handoff when product + quantity alone lacks fulfillment intent. |
| `post_quotation_hold` | `manager_review_hold` | Hold #11-like bulk/sample/discount ambiguity until Lilia answers. |
| `legacy_fallback` | `legacy` | Defer to the existing runtime. |

## Side-Effect Policy

The side-effect families are:

- `customer_message`
- `product_media`
- `manager_escalation`
- `telegram_notification`
- `zoho_sale_order`
- `quotation_pdf`
- `whatsapp_media`
- `metadata_update`

In `shadow`, every decision must report `side_effects_allowed=false` and
`allowed_side_effects=[]`.

In `enforce`, side effects require both:

1. mode-level enablement for `enforce`;
2. route-level allowlist membership.

Initial enforce route side-effect defaults:

| Route | Allowed side effects in v1 |
| --- | --- |
| `name_gate` | `metadata_update`, `customer_message` |
| `name_gate_resume` | `metadata_update`, `customer_message` |
| `product_clarify` | `metadata_update`, `customer_message` |
| `product_selection_legacy_delegate` | none from the kernel |
| `selection_confirmation` | none from the kernel in v1 |
| `quote_resume_missing_details` | `metadata_update`, `customer_message` |
| `policy_no_handoff` | `customer_message` |
| `post_quotation_hold` | `metadata_update`, `customer_message` |
| `legacy_fallback` | none from the kernel |

Zoho, PDF, WhatsApp media, Telegram, and manager escalation side effects remain
legacy-owned in v1 unless a later stage adds a dedicated allowlist and tests.

## Issue Coverage

- #36: name-gate must persist and resume the customer's substantive request.
- #37: product/brand/SKU plus quantity alone must not become
  `order_confirmation` manager handoff.
- #39: SKU selection variants such as `CH 616`, `CH-616`, `CH616`, and mixed
  Latin/Cyrillic forms must preserve product/quote selection.
- #40: terse quotation details must preserve `pending_quote_selection` and ask
  only for missing required fields.
- #11: bulk/sample/discount post-quotation behavior remains a hold state; do
  not close or enforce final behavior until Lilia answers.

## Rollout Gates

1. Add replay fixtures and docs.
2. Build a local eval runner that reads `tests/fixtures/dialogue/*.json`.
3. Run fixtures against the legacy runtime and kernel shadow output.
4. Enable shadow mode in a safe environment and compare mismatch telemetry.
5. Move one allowlisted route at a time to enforce mode only after green replay,
   green targeted tests, and explicit stage approval.
