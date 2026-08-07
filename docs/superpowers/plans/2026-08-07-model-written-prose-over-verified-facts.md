# Model-Written Prose Over Verified Facts — Plan

> Implement in epic `tj-swgu` against current `origin/main`. Preserve all
> unrelated and untracked user files. The live re-run needs separate explicit
> owner authority.

**Spec:** `docs/superpowers/specs/2026-08-07-model-written-prose-over-verified-facts-design.md`

**Level:** integration

## Boundary and streams

| Stream | Beads | Write area | Proof |
|---|---|---|---|
| Handoff policy | `tj-rily` | verified-answer policy, its tests | low-risk classes reach the model |
| Route retirement | `.1`, `.4` | `src/llm/engine.py`, `tests/test_llm_engine.py` | behaviour pinned, template text gone |
| Repair path | `.2` | `src/llm/engine.py`, focused tests | detection kept, substitution demoted |
| Action-bearing wrap | `.3` | `src/llm/engine.py`, `src/llm/order_quote_routes.py` | write unchanged, prose model-written |
| Consultative gap | `.5` | `runtime_directives` construction, focused tests | frozen prompt unchanged |
| Provenance guard | `.6` | acceptance capture, `scripts/e2e_acceptance/*` | new routes surface as a number |
| Integration | `.7` | stage docs, Beads, live re-run | one acceptance on one identity |

`.1`, `.2`, `.5`, `.6` and `tj-rily` are independent and can run in parallel.
`.4` waits on `tj-rily`. `.3` waits on `.2`. `.7` waits on all six.

## Scope ledger

- `name-gate` is out of scope. It is a first-turn identity gate, not a
  replacement for an answer.
- `tj-g51h` closes with `.4`; `tj-v41l` closes with `.2`. Both stay open until
  their parent lands, so a route that survives review still gets fixed in place.
- `tj-g3f` is unrelated and stays out of this epic.
- No task changes when a side effect runs. If one appears to require that, stop
  and raise it rather than reordering the write.

## Task 0: Land the planning package

**Beads:** `tj-swgu`

1. Spec and plan committed, epic and children created with dependencies wired.
2. `bd ready` shows `tj-rily`, `.1`, `.2`, `.5`, `.6` unblocked and `.3`, `.4`,
   `.7` blocked.

**Done when:** the graph matches this document and both files are in `main`.

## Task 1: Narrow the verified-answer handoff

**Beads:** `tj-rily`

**Files:** the verified-answer policy module and its tests.

**TDD steps:**

1. Red test: a delivery/assembly availability question and a saved-context
   summary request do not return `policy_action == "handoff"`.
2. Red test: the classes that must still escalate — discounts, exceptional
   terms, anything in the `manager_required` capability mode — still do.
3. Narrow the decision to those classes.
4. Run the policy, engine and escalation suites.

**Done when:** both low-risk classes reach the model with their override routes
disabled, no `manager_required` class stops escalating, and the reason each
class sits where it does is recorded in the module rather than in a test name.

## Task 2: Retire `stock-price-options`

**Beads:** `tj-swgu.1`

**Files:** `src/llm/engine.py`, `tests/test_llm_engine.py`.

**TDD steps:**

1. Rewrite `test_process_message_stock_price_question_returns_catalog_option_list`
   and `test_exact_sku_stock_request_returns_only_requested_variant` to assert
   behaviour — SKU, live stock, unit price, requested-quantity total, no
   alternatives, no quotation — instead of the rendered template.
2. Confirm they fail against the template, which omits the total.
3. Delete `_stock_price_resolved_options`'s route branch and
   `_stock_price_options_response`.
4. Check the fall-through: the S06 counterfactual showed the turn landing in
   `selection-confirmation` before reaching the model. Assert which route owns
   the turn now, and that it is the model.
5. Run the engine and order-quote suites.

**Done when:** the tests pin behaviour, the template text is gone from the
codebase, and no other route silently inherits the turn.

## Task 3: Repair instead of replace on the verified-catalog check

**Beads:** `tj-swgu.2` (closes `tj-v41l`)

**Files:** `src/llm/engine.py`, focused tests.

**TDD steps:**

1. Red test on the S05 turn-4 shape: a rejected catalog decision produces one
   repair attempt carrying a directive that names the specific defect.
2. Red test: the template is reached only when the repair also fails.
3. Red test for `tj-v41l`: whatever ships keeps every requested product family,
   states coverage without contradicting the lines above it, and renders product
   names without escaping artefacts.
4. Route rejection into the existing repair-directive mechanism; demote
   `_materialize_verified_catalog_recovery` to second fallback.
5. Run the engine, catalog and claim-contract suites.

**Done when:** a rejected decision is repaired rather than replaced, the
template is provably second, and the arithmetic defect the checker exists to
catch is still caught.

## Task 4: Retire `service-availability` and `saved-context-summary`

**Beads:** `tj-swgu.4` (blocked by `tj-rily`; closes `tj-g51h`)

**Files:** `src/llm/engine.py`, `tests/test_llm_engine.py`.

**TDD steps:**

1. Rewrite `test_process_message_delivery_assembly_interruption_in_expected_frame_answers_without_handoff`
   and `test_process_message_saved_context_summary_does_not_handoff` to assert
   no escalation and a model-written answer, not the template text.
2. Red test for `tj-g51h`: the summary carries parsed products and quantities
   and contains no inbound message text.
3. Delete both route branches and their renderers.
4. Run the engine, policy and escalation suites.

**Done when:** neither turn escalates, both are model-written, and the products
slot holds a parsed requirement.

## Task 5: Wrap the three action-bearing routes

**Beads:** `tj-swgu.3` (blocked by `tj-swgu.2`)

**Files:** `src/llm/engine.py`, `src/llm/order_quote_routes.py`, focused tests.

**TDD steps:**

1. Red test per route: the write happens first and unconditionally, and still
   happens when the model run raises.
2. Red test per route: the customer-visible sentence is model-written, and every
   number in it equals the one the route computed.
3. Red test per route: a failed model run falls back to the existing renderer
   with the write already durable.
4. Wrap `selection-confirmation`, `exact-quote-deterministic` and
   `sales-opportunity` in that order.
5. Run the order-quote, CRM, quotation and engine suites.

**Done when:** no write moved, no number drifted, and each route degrades to
today's behaviour rather than to silence.

## Task 6: Close the consultative gap on comparison turns

**Beads:** `tj-swgu.5`

**Files:** the `runtime_directives` construction path, focused tests.

**TDD steps:**

1. Red test: on a state showing a direct comparison or a closed product
   question, the run carries a directive asking for a recommendation plus one
   useful clarification or a concrete next step.
2. Red test: the frozen product system prompt is byte-identical.
3. Red test: any bundle or incentive the directive invites stays evidence-bound
   under the claim contract.
4. Add the directive.
5. Run the engine, prompt-freeze and claim-contract suites, then the bait
   counter-set.

**Done when:** S04's shape ends with a recommendation and a next step, the
frozen prompt is unchanged, and the counter-set shows no new unsupported fact.

## Task 7: Record provenance and stop silent accretion

**Beads:** `tj-swgu.6`

**Files:** acceptance capture, `scripts/e2e_acceptance/*`, focused tests.

**TDD steps:**

1. Record `text_provenance` per turn in the acceptance capture alongside the
   route label already stored.
2. Add a registry entry per existing deterministic customer-visible route: why
   it exists and the date it was last re-checked against the current model.
3. Red test: a new route without a registry entry fails.
4. Backfill the nine from `tj-ja1v`.

**Done when:** the capture carries provenance, the registry is complete, and an
unregistered route cannot land.

## Task 8: Re-run the acceptance and close out

**Beads:** `tj-swgu.7` (blocked by all six)

**TDD steps:**

1. Full gates: ruff, format, mypy, `pytest tests/`.
2. Deploy, then read back the runtime identity.
3. **Stop for owner authority** before the live run. It sends real WhatsApp and
   writes real Zoho records.
4. Issue a fresh authority bundle, capture S01–S10, score all ten, read back
   S09/S10 external effects, clean up test data.
5. Publish the comparison against 18.4 and 18.0 and close the epic.

**Done when:** the epic acceptance in the spec is met, or the shortfall is named
per scenario with evidence.

## Stop conditions

- Any task that appears to require moving, delaying or conditioning a side
  effect. Raise it instead.
- Any change that would grow the frozen product system prompt or alter
  `AC-01..AC-30`.
- Any live run, push or deploy without current explicit owner authority.
- A retirement that cannot be pinned by a behaviour test: keep the route and fix
  it in place under its own bug instead.
