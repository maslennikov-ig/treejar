# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Accepted stage id: `tj-rt7w-real-split`
Status: `tj-rt7w.1`-`.6`, `.8`, `.9`, `.10`-`.13` closed. `tj-rt7w.7` and `.14`
are open; `.7` is the last thing between the epic and its close.

Documentation: no external/versioned boundary — this stage changes internal
first-party Python structure only.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- Every text guard is bounded: letters or digits in, letters or digits out. It
  catches F5. It does not stop a guard shrinking four sentences to one word --
  `tj-rt7w.14`, recorded rather than promised.
- The opening, selling-turn, closed-question, and premature quote-detail guards
  are pure module functions with explicit state, not engine closures.
- `src/llm/money.py` owns every currency pattern in `src/llm/`, enforced by an
  AST test.
- The unsupported customer-owned-furniture service family is blocked. The
  prompt was tried first with exactly three authorized Luna calls.
- **F1 and F3 are closed.** One turn is `_Turn` (the shared state and the
  operations over it), `_TurnConfig` (the config reads, taken once) and
  `_QuoteFacts` (the quote facts, read once then amended by the name gate),
  with eleven phase functions over them. Longest function 259 lines;
  `process_message_impl` 163; no closure anywhere in the file. Two tests hold
  that: `test_llm_message_processor_structure.py` for the bound,
  `test_llm_message_processor_patch_points.py` for the patch points.
- `process_message` is still the 40-line public facade and `engine.py` is
  11,849 lines. Both were already true; what is new is that the sequence behind
  the facade is now what the facade claimed.
- The impl is fully type-checked. It imports `src.llm.engine` as a module, so
  the suite's `src.llm.engine.*` patches still land and Mypy still checks.
  `get_system_config` is imported *inside* the two calls that use it for the
  same reason, and a test now derives that rule from the suite.
- Catalog planning/materialization is in `src/llm/catalog_planning.py`; response
  transport is in `src/llm/response_runtime.py`; the turn sequence is in
  `src/llm/message_processor.py`; order/quote routes are in
  `src/llm/order_quote_routes.py`.
- No existing test was edited anywhere in this epic.
- The canonical runtime target remains `https://noor.starec.ai`; nothing has
  been pushed, deployed, or applied to production or staging.
- Production data is Postgres in `noor-db-1` on `noor-server`, not Supabase.
- Luna remains the main generation model. The owner requires the agent itself to
  be the result judge, not the product's built-in judge.
- The protected corpus remains outside Git under the git-common-dir
  orchestration state. Tracked evidence may carry `dialog_id` and integers only.
- Both scoring rulers and applicability/rubric logic remain frozen. Never treat
  movement smaller than the measurement uncertainty as evidence.

## Delivered commits

- `e647458` — `.1`, block unsupported used-furniture service promises.
- `75962a6` — `.2`, prevent guards from blanking replies.
- `7c0bd64` — `.3`, centralize money parsing.
- `7c6427b` — `.4`, extract pure response-policy guards.
- `3199b1a` — `.5`, route every reply through one text policy.
- `4640602` — `.6`, split message processing runtime (facade only).
- `dab7795` — `.13`, merge `21d4dec`: the Step 6 revision had never reached main.
- `a4e3647` — `.8`, the stage close left main red on a pin it was right to trip.
- `dce7442` — `.9`, the message processor gets its types back.
- `8a80c1f` — `.11`/`.12`, last two currency patterns move in.
- `c9d22f9` — `.10` step A, the eight closures that needed no design decision.
- `e600a55` — `.10` step B, the alias preamble goes.
- `190a462` — `.10` step C, the turn becomes an object and its phases functions.

Each closed child has a validated artifact under `.codex/stages/*/artifacts/`.

## Verification

- Tip gates: Ruff and format clean over `src/ tests/`; Mypy clean over 173
  source files; Pytest `3557 passed, 19 skipped`; process verification passed.
- Protected replay: 31 stored raw assistant outputs re-render through the full
  policy chain to an identical digest at `19556ba` and at the tip.
- Guard, policy, catalog-planning, response-runtime, order-quote-route and
  engine sources are byte-identical to `19556ba`.

## Active work

- `tj-rt7w.7` is open and now unblocked. It is the paired measured round after
  the structural work, on the frozen twenty openings, seed `20260810`, paired
  against `8cfbe91`. The expected result is no movement: no step in this epic
  targets the rubric, and movement smaller than the instrument's uncertainty is
  not evidence. It is run for the critical-failure count and for a read of the
  three paths that now run grounding for the first time.
- **`.7` needs current owner authority.** The owner recorded 20 Luna + 20 GLM
  calls (about $0.18) for exactly this task; no paid call has been made in this
  session, and the authority to spend must be current, not inherited.
- Epic `tj-rt7w` stays in progress until `.7` is completed or dispositioned.

## Constraints

- No push, PR, deploy, production/staging mutation, model-configuration change,
  or real-user message occurred or is implied by these local commits.
- Do not retire deterministic routes in this stream; that separate 8,259-line
  scope remains intentionally deferred.
- Preserve unrelated owner work and keep corpus text outside the repository.
- After every handoff edit, run
  `python3 scripts/orchestration/repin_traceability_sources.py`.

## Documentation and graph review

- `docs-reviewed: updated` — handoff, stage summary and artifact describe the
  split, its bound, and the regression it caused.
- `project-index: reviewed-no-change` — no module added, moved or renamed.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: `tj-rt7w-measured-round`

Recommended action: `tj-rt7w.7`, once the owner confirms the paid calls now.
Nothing else in the epic is blocked, and nothing else is worth doing first:
`.14` owes a measured round of its own under R5, so it queues behind `.7` by
the same rule.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-rt7w-measured-round` and Bead `tj-rt7w.7`. Ask
for the paid-call authority by name and amount before spending anything. Run the
paired round on the frozen twenty openings at seed `20260810` against `8cfbe91`,
same second reader, judged by the agent itself per the standing owner decision.
Report the delta with its uncertainty and per attainable ceiling, never an
absolute level, and treat no movement as the expected result.

## Explicit defers

- `tj-rt7w.7`: paired 20+20 measured round, open, waiting on current authority.
- `tj-rt7w.14`: the R2 bound has no semantic half; a fix owes a measured round.
- Deterministic-route retirement: explicitly outside this stream.
- Deployment and any live proof: not authorized or performed here.
