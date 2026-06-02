# Dialogue State Kernel Specification

Status: v1 kernel spec extended by stage `tj-gh48` for expected-answer frames
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
- Shadow output may persist bounded diagnostic kernel state and traces under
  `metadata_["dialogue_kernel"]`, including `state.expected_answer_frames` and
  `traces`. Shadow must still avoid mutation outside that namespace and must not
  create customer-visible or provider side effects.
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
      "expected_answer_frames": [],
      "trace_history": []
    },
    "traces": []
  }
}
```

Rules:

- Existing metadata keys such as `customer_name`, `name_gate_pending_request`,
  `pending_quote_selection`, and `quote_customer_details` remain supported.
- `last_question` remains supported as a legacy compatibility field. New
  routing must prefer `expected_answer_frames` when present.
- The kernel may mirror legacy keys into `dialogue_kernel.state.slots`, but v1 must
  preserve compatibility with existing readers.
- `thread_id` must be stable per conversation and suitable for LangGraph
  checkpoint addressing. Use `conversation:<uuid>` or another deterministic
  conversation-scoped value.
- v1 uses the existing row persistence for `Conversation.metadata_`; it must not
  require the Postgres LangGraph checkpointer package.
- Metadata writes must be bounded and schema-versioned. Invalid or oversized
  kernel state is ignored and replaced from legacy metadata.

## Expected Answer Frames

The #47 hotfix proved that checking only the latest assistant question is useful
for a narrow regression, but it is not a robust dialogue policy. A customer can
ask an unrelated delivery question, add details, or wait several turns before
answering the earlier product-choice question. Production routing must therefore
track explicit expected answers as durable state.

An `ExpectedAnswerFrame` is a small state object representing a question Noor has
asked and the answer shape Noor is waiting for. It is a short-term dialogue
memory object, not a long-term customer preference. Frames live inside
`DialogueState` and are stored under
`metadata_["dialogue_kernel"]["state"]["expected_answer_frames"]`.

Frame schema:

```json
{
  "frame_id": "product_preference:20260602:abc123",
  "flow": "product_selection",
  "question_kind": "product_preference",
  "prompt_key": "workspace_luma_novo_preference",
  "status": "active",
  "priority": 80,
  "asked_at": "2026-06-02T10:00:00Z",
  "expires_at": "2026-06-02T10:30:00Z",
  "max_customer_turns": 6,
  "turns_seen": 0,
  "expected_slots": [
    {
      "slot": "workspace_preference",
      "required": true,
      "accepted_values": ["open", "private", "novo", "luma"],
      "aliases": {
        "open": ["more open", "for team", "collaborative", "novo"],
        "private": ["private", "more privacy", "luma", "individual"]
      }
    }
  ],
  "source_refs": [
    {"kind": "product_family", "value": "SKYLAND NOVO"},
    {"kind": "product_family", "value": "LUMA"}
  ],
  "metadata": {
    "assistant_message_id": "optional-message-id",
    "origin": "legacy_bridge"
  }
}
```

Required fields:

- `frame_id`: stable unique key; deterministic when possible for idempotency.
- `flow`: one of the kernel-supported flows.
- `question_kind`: narrower intent such as `name_gate`, `product_preference`,
  `sku_quantity`, `quote_details`, or `post_quote_approval`.
- `status`: `active`, `fulfilled`, `interrupted`, `expired`, or `cancelled`.
- `priority`: higher priority frames match first when multiple frames are active.
- `expected_slots`: one or more slot descriptors with accepted values and
  aliases. Free-text slots such as `delivery_address` may define validators
  instead of enumerated values.
- `source_refs`: product/SKU/model/quotation references needed to interpret a
  terse answer.
- `asked_at`, `expires_at`, `max_customer_turns`, `turns_seen`: expiry controls.

Lifecycle:

1. When Noor asks a question that expects a customer answer, push a new active
   frame. If the same question is retried, update the existing active frame
   instead of appending duplicates.
2. At the start of every customer turn, increment `turns_seen` for active frames
   and expire any frame past `expires_at` or `max_customer_turns`.
3. Match incoming text against active frames before generic verified-policy
   handoff, but after hard blockers such as complaints, refunds, explicit human
   requests, payment terms, credit, warranty, and other escalation triggers.
4. If exactly one active frame matches, fill its slots, mark it `fulfilled` when
   all required slots are present, and route the turn through the frame's flow.
5. If a customer asks an unrelated but answerable service question, handle it as
   an interruption and keep the frame active unless the new intent explicitly
   cancels or replaces it.
6. If multiple frames match with similar confidence, ask a compact clarification
   instead of guessing.
7. Keep only a bounded active/history set, for example up to 8 active frames and
   20 recent fulfilled/interrupted/expired frames.

Frame matching must never be a broad search over raw conversation text. The
matcher reads structured frame state and small source refs, then uses
deterministic rules or a structured classifier to decide:

```json
{
  "matched": true,
  "frame_id": "product_preference:20260602:abc123",
  "confidence": "high",
  "filled_slots": {"workspace_preference": "open"},
  "route": "product_preference_answer",
  "interruption": false,
  "blocker": null
}
```

This keeps long-dialog context durable without sending an ever-growing transcript
to the model or letting stale messages distract routing.

## LangGraph Shape

The implemented runner loads state before graph execution, then runs a small
compiled `StateGraph`:

1. `expire_frames`: age active `ExpectedAnswerFrame` entries and mark expired
   frames before route matching.
2. `match_expected_answer`: check the new customer message against active
   frames and produce a bounded match payload.
3. `decide`: choose the route, fill required slots only when the match is
   fulfilled, and fall back to legacy when the route is not handled by the
   kernel.

After graph output, `run_dialogue_kernel` applies mode/allowlist gating, sets
`side_effects_allowed`, and persists bounded trace metadata when tracing is
enabled.

The graph output is a decision object:

```json
{
  "route": "product_selection_legacy_delegate",
  "flow": "product_selection",
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
| `post_quotation_hold` | `post_quotation_hold` | Hold #11-like bulk/sample/discount ambiguity until Lilia answers. |
| `product_preference_answer` | `product_selection` | Fill a product preference frame such as open/NOVO vs private/LUMA and continue product handling without manager handoff. |
| `expected_answer_clarify` | current active flow | Ask which pending question the customer is answering when multiple active frames match. |
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
| `product_preference_answer` | `metadata_update`, `customer_message` |
| `expected_answer_clarify` | `metadata_update`, `customer_message` |
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
- #47: product preference answers such as `I prefer more open for team` must be
  treated as answers to an active product preference frame even after bounded
  interruptions, not as verified-policy manager handoff.
- #11: bulk/sample/discount post-quotation behavior remains a hold state; do
  not close or enforce final behavior until Lilia answers.

## Rollout Gates

1. Add replay fixtures and docs.
2. Build a local eval runner that reads `tests/fixtures/dialogue/*.json`.
3. Run fixtures against the legacy runtime and kernel shadow output.
4. Enable shadow mode in a safe environment and compare mismatch telemetry.
5. Move one allowlisted route at a time to enforce mode only after green replay,
   green targeted tests, and explicit stage approval.
6. For expected-answer frames specifically, keep production in `shadow` until
   traces prove at least:
   - no duplicate side effects;
   - no false suppression of true escalation triggers;
   - #36/#37/#39/#40/#47 replay fixtures pass;
   - long-dialog stress keeps active frames across interruptions and expires
     stale frames.
