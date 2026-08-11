# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Accepted stage id: `tj-rt7w-measured-round`
Status: `tj-rt7w.1`-`.13` closed, including `.7`. `.14` is open and owes a
measured round of its own. The epic's structural work is done and measured.

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
- Luna is the product's generation model; GLM is the alternate-vendor model for
  a second opinion or alternate text. **The judge of a measured round is the
  orchestrating agent itself, reading blind**, and a paid model may only be a
  second reader beside it. That is now the harness default rather than a
  directive: `real_opening_acceptance.py` stops after the generation arm and
  writes `reading-pack.json`, and paying a second reader takes
  `preflight --second-reader`.
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

## The measured round, `tj-rt7w.7`

Run at `33c8f1f` on the frozen seed-`20260810` twenty. The owner authorised
20 Luna + 20 GLM and then chose to drop the second reader, so: **20 Luna calls,
zero judging calls, $0.004661**. Report:
`docs/reports/2026-08-11-the-round-after-the-cleanup.md`.

- 20/20 responses, 20/20 evaluations, 20/20 language. **One critical failure in
  1/20**, so the round does not pass its own fourth criterion.
- The failure is `tj-riim`: on the recruitment opening the reply promises to
  route the CV and call back, and can do neither. Not attributable to this epic
  -- nothing here touches recruitment, and the stored `8e50dea` reply on that
  opening was honest. Live defect either way.
- **No paired score delta is reportable.** The judge changed, and the project
  forbids comparing across judges; two judges on the same texts differed by 3.8
  points systematically. This round is the baseline for the next one.
- What the round was for is answered: the epic changed nothing it did not mean
  to, and `tj-rt7w.1` holds in the live path -- dialog 789 no longer offers to
  value customer-owned furniture.
- The three out-of-scope `tj-vz7o.12` defects reproduce unchanged. New detail:
  the missing-quote defect is inconsistent, not absent -- four openings on the
  same run did quote priced rows.

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

Next stage id: `tj-product-defects`

Recommended action: the product track, which has been deferred behind the
cleanup and is now unblocked. Two P0 epics (`tj-2m5m`, `tj-swgu`), then the
reader findings that this round confirmed still live: `tj-riim`, `tj-vz7o.12`,
`tj-wvo4`, `tj-odeq`. `tj-rt7w.14` owes a measured round under R5 and queues
with them.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the product track. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff and
`docs/reports/2026-08-11-the-round-after-the-cleanup.md` first. Take `tj-riim`
and `tj-vz7o.12` in order of certainty, prompt-first and measured per R5, and
never ride a refactor and a behaviour change in the same round per R6. The next
measured round is the first one comparable with 2026-08-11, because the judge is
the same. Ask for paid-call authority by name and amount before spending.

## Explicit defers

- `tj-rt7w.14`: the R2 bound has no semantic half; a fix owes a measured round.
- `tj-riim`: found by this round, not fixed here; a fix owes a measured round.
- Deterministic-route retirement: explicitly outside this stream.
- Deployment and any live proof: not authorized or performed here.
