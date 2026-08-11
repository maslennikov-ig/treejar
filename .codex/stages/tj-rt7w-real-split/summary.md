# Stage tj-rt7w-real-split

Status: accepted
Base: `main` at `19556ba`
Acceptance owner: root orchestrator (Claude)

Documentation: no external/versioned boundary — internal first-party Python,
no new dependency, no public contract or version-sensitive behaviour changed.

docs-reviewed: updated — this summary, the handoff and the `tj-rt7w.10`
artifact record the split, the bound it now holds, and the one regression it
caused; no stable contract, navigation, ops or migration doc changes.
project-index: reviewed-no-change — no module added, moved or renamed; all of
it lands inside `src/llm/message_processor.py`.
graph-reviewed: no-change-needed — Graphify is not initialised.

## Goal

`tj-rt7w.10`. `tj-rt7w.6` reported `process_message: 40 lines` and delivered a
facade over a 2,044-line function with 15 nested closures. Close F1 and F3 for
real: no function on the `process_message` path over 300 lines, with the turn's
phases as named functions over explicit state.

Behaviour-preserving throughout. The guard and policy sources must stay
byte-identical, no existing test may be edited, and the stored raw outputs must
replay unchanged.

## Step A — the closures that were nested only because everything was

Eight of the fourteen closures are out, and none of them needed a design
decision first; the capture analysis showed why.

| closure | lines | captured |
|---|---:|---|
| `_is_first_turn` | 17 | nothing |
| `_has_escalation` | 2 | nothing |
| `_deferred_product_media_for_response` | 42 | nothing |
| `_get/_set/_clear_verified_policy_repair_state` | 25 | `conv`, `db` |
| `_ensure_model_runtime` | 20 | `db`, a `nonlocal` memo |
| `_run_prose_agent` | 14 | the memo |

The first three closed over nothing at all. The repair-state trio closed over
exactly the conversation and the session, which is state passed in, not state
captured. `_ensure_model_runtime` was a closure over a `nonlocal` where the memo
and the memoized thing shared one name; it is now `_LazyModelRuntime`.

Result: **1,947 → 1,830 lines, 14 → 6 closures** (`c9d22f9`).

## Step B — the alias preamble

`tj-rt7w.9` turned `runtime.foo` into `engine.foo` and kept the shape it
inherited: 86 local aliases read off the engine at the top of the call, then
used bare 1,600 lines below. That typed correctly and still made a phase
function impossible to lift out — every bare name would have come with it.

`engine.foo` at the call site resolves at the same moment the alias did at
entry, so the patch points are untouched, and the reader can see which
collaborator belongs to the engine. **126 lines out, 138 call sites named**
(`e600a55`).

## Step C — the turn, and its phases

`_Turn` is the state one turn shares and the operations over it: the fourteen
locals that crossed every boundary, and the six response builders that used to
close over them. `opening_anchor_line` was a one-element list purely because a
closure cannot assign to an enclosing local; it is a field.

Two more sets get names: `_TurnConfig`, the seven system-config reads taken
once, and `_QuoteFacts`, the twenty-two facts the quote routes consume — read
once, then amended by the name gate, which is why it is mutable and why nothing
could be bound early.

The sequence is then phases over those three, each returning the reply or
`None`:

| function | lines |
|---|---:|
| `_load_turn` | 126 |
| `_read_turn_config` | 68 |
| `_customer_facts_and_quotation_routes` | 119 |
| `_dialogue_kernel_route` | 128 |
| `_read_quote_facts` | 197 |
| `_capture_details_and_name_gate_routes` | 190 |
| `_pre_policy_routes` | 92 |
| `_search_context_and_policy` | 83 |
| `_verified_policy_routes` | 259 |
| `_verified_catalog_plan_route` | 99 |
| `_sales_agent_route` | 150 |
| `process_message_impl` | **163** |

`_Turn`'s longest method is `render_reply` at 58 lines.

Three duplications collapsed on the way, each because the state became
addressable: the `record_legacy_route` plus expected-answer-frame pair that
`_build_llm_response` and `_build_static_response` each carried is
`_Turn._record_reply_on_conversation`; the catalog-recovery builder is
`_Turn.build_replacement_response`; and `db_model_main if "db_model_main" in
locals()` is a plain name now that it is initialised before the block that
sets it.

## The one thing that broke, and what now catches it

Hoisting `from src.core.config import get_system_config` to the top of the file
looked like tidying. Twelve tests patch `src.core.config.get_system_config`, and
a module-level binding freezes the real function before the patch lands, so
those twelve began running the real config path against a mocked session. They
failed loudly only because that mock returns coroutines; a stricter mock would
have passed while testing nothing — which is the failure mode `tj-rt7w.9` found
three of.

The import went back inside the two calls that use it, with the reason written
where it can be read. `tests/test_llm_message_processor_patch_points.py` gained
the general form of the check: any name this module binds at import time that
the suite patches on its defining module is a disconnected patch. Confirmed red
against the hoisted import, green now.

## The bound is a test now

`tests/test_llm_message_processor_structure.py` asserts what `.6` reported: no
function in the sequence over 300 lines, and no closure in the file at all.
Confirmed red on the pre-split source (six closures, one 1,527-line function)
and green after. `tests/test_llm_engine_structure.py` was not touched — it
asserts on the facade, which is exactly why it could not see this.

## Delivery

Three local commits on `main`: `c9d22f9`, `e600a55`, `190a462`. No push, PR,
merge, deploy, production or staging mutation, model-configuration change,
paid call, or real-user message.

## Verification

- Ruff, format: clean over `src/ tests/`.
- Mypy: clean over 173 source files.
- Pytest: `3557 passed, 19 skipped`, zero failures.
- Protected replay: 31 stored raw assistant outputs re-rendered through the
  full policy chain at `19556ba` and at the tip produce the identical digest
  `1ac73ad9…`.
- Guard, policy, catalog-planning, response-runtime, order-quote-route and
  engine sources are byte-identical to `19556ba`. The whole stage changes one
  source file.
- **No existing test was edited.** One test file added; one extended by
  addition only. Both new assertions confirmed red before green.
