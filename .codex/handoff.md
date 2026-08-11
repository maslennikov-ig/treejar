# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Accepted stage id: `tj-rt7w-verification-fixes`
Status: `tj-rt7w.1`-`.6` closed earlier; `.8`, `.9`, `.11`, `.12`, `.13` closed
here after verification found the stage tip red and three claims overstated.
`tj-rt7w.7`, `.10` and `.14` are open.

Documentation: no external/versioned boundary — this stage changes internal
first-party Python ownership and response policy only.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- Every text guard is bounded: letters or digits in, letters or digits out. It
  catches F5. It does not stop a guard shrinking four sentences to one word --
  `tj-rt7w.14`, recorded rather than promised.
- The opening, selling-turn, closed-question, and premature quote-detail guards
  are pure module functions with explicit state, not engine closures.
- `src/llm/money.py` owns every currency pattern in `src/llm/`, enforced by an
  AST test. Four vocabularies remain, deliberately and documented; one named
  exception is a units list, not a money pattern.
- The unsupported customer-owned-furniture service family is blocked. The
  prompt was tried first with exactly three authorized Luna calls; one measured
  failure admitted the bounded grounding rule.
- `process_message` is a 40-line public facade over `process_message_impl`,
  which is **1,947 lines with 15 nested closures**. The audited defect was 1,827
  lines and 17 closures, so `.6` moved and renamed the monolith rather than
  splitting it; F1 and F3 are not closed. `engine.py` at 11,849 lines is real:
  3,823 lines genuinely moved to `catalog_planning.py`.
- The impl is fully type-checked. `.6` passed the engine in as `runtime: Any`
  and read 160 names off it, so mypy checked nothing across the hot path; it now
  imports the module, which resolves the same attributes at the same moment.
- Catalog planning/materialization is in `src/llm/catalog_planning.py`; response
  transport is in `src/llm/response_runtime.py`; the orchestration sequence is
  in `src/llm/message_processor.py`; order/quote routes and their declared
  deterministic labels are in `src/llm/order_quote_routes.py`.
- Existing `src.llm.engine.*` runtime patch points remain available. No existing
  test was edited for behavior-preserving children `.2`, `.3`, `.4`, or `.6`.
- Protected replay for `.6`: 20 stored raw outputs matched commit `3199b1a`
  exactly. The response-policy and guard sources did not change in `.6`.
- `.5` changed only `dialog_id=789` and `dialog_id=819` on the three formerly
  short exits. Root read both complete before/after replies: `789` lost the
  unsupported service offer; `819` gained the owner-approved commitment for its
  recorded deferral. The former full chain changed 0 of 20 outputs.
- The canonical runtime target remains `https://noor.starec.ai`; nothing from
  this stage was pushed, deployed, or applied to production or staging.
- Production data is Postgres in `noor-db-1` on `noor-server`, not Supabase.
- Luna remains the main generation model. The owner requires Codex itself to be
  the result judge, not the product's built-in judge.
- The protected corpus remains outside Git under the git-common-dir orchestration
  state. Tracked evidence may carry `dialog_id` and integers only.
- Both scoring rulers and applicability/rubric logic remain frozen. Never treat
  movement smaller than the measurement uncertainty as evidence.

## Delivered commits

- `e647458` — `.1`, block unsupported used-furniture service promises.
- `75962a6` — `.2`, prevent guards from blanking replies.
- `7c0bd64` — `.3`, centralize money parsing.
- `7c6427b` — `.4`, extract pure response-policy guards.
- `3199b1a` — `.5`, route every reply through one text policy.
- `4640602` — `.6`, split message processing runtime (facade only, see above).
- `dab7795` — `.13`, merge `21d4dec`: the Step 6 revision and the orchestrator
  prompt had never reached main.
- `a4e3647` — `.8`, the stage close left main red; `--source` re-pins one named
  frozen source deliberately instead of widening the silent-drift set.
- `dce7442` — `.9`, the message processor gets its types back.
- `8a80c1f` — `.11`/`.12`, last two currency patterns move in; R2 states the
  bound that shipped.

Each closed child has a validated artifact under
`.codex/stages/tj-rt7w-overcomplication/artifacts/`.

## Verification

- The `.6` report of `3547 passed` was never true on its tip. `58a64de` edited
  `.codex/project-index.md` without re-pinning the manifest and left three
  failures; the closeout's 107 selected tests and process verification do not
  cover that file. Bisected: 44 passed at `4640602`, 3 failed at `58a64de`.
- Tip gates now: Ruff and format clean over `src/ tests/ scripts/`; Mypy clean
  over 173 source files; Pytest `3554 passed, 19 skipped`, zero failures;
  process verification passed.
- No existing test was edited in any commit of this stage; five test files were
  added or extended by addition only.

## Active work

- `tj-rt7w.7` is open and now depends on `.10`. It is the paired measured round
  *after* the structural work, and the structural work has not happened yet.
- The owner has authorized its exact 20 Luna + 20 GLM calls (about $0.18) and
  requires Codex to judge the results. A later stage must still record and use
  that authority only for `.7`; this closeout used no paid call.
- Epic `tj-rt7w` stays in progress until `.7` is either completed or explicitly
  dispositioned by its own scope.

## Constraints

- No push, PR, deploy, production/staging mutation, model-configuration change,
  or real-user message occurred or is implied by these local commits.
- Do not retire deterministic routes in this stream; that separate 8,259-line
  scope remains intentionally deferred.
- Preserve unrelated owner work and keep corpus text outside the repository.
- After every handoff edit, run
  `python3 scripts/orchestration/repin_traceability_sources.py`.

## Documentation and graph review

- `docs-reviewed: updated` — handoff, stage summary, artifacts, and project
  index now describe the accepted module boundaries and verification.
- `project-index: updated` — stable `src/llm/` ownership entries name the new
  catalog, orchestration, policy, and response-runtime modules.
- `graph-reviewed: no-change-needed` — optional Graphify output is not
  initialized, and this `slice_acceptance` boundary is below the configured
  integration/release refresh policy.

## Next recommended

Next stage id: `tj-rt7w-real-split`

Recommended action: `tj-rt7w.10`, the split `.6` reported and did not do. It is
now safe to attempt for the first time: the impl is fully typed, so mypy catches
a mis-threaded local, and it cannot have caught one before. There is no
constraint conflict -- the two AST route tests read `engine.process_message`,
where the wrappers live, so the impl can be split without editing any test.
`.7` waits on `.10`: measuring the structural work before the structure exists
would measure nothing.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-rt7w-real-split` and Bead `tj-rt7w.10`, whose
notes carry the plan. Read `AGENTS.md`, `.codex/orchestrator.toml`, this handoff
and the over-complication spec first. Introduce a turn-state dataclass, then
extract phases in order, running the full suite and the twenty stored raw
outputs after each. Guard and policy sources must stay byte-identical. Edit no
existing test: if a step needs one edited, the step is wrong -- stop and say so,
which is the report `.6` owed and did not make. No paid call, push or deploy.

## Explicit defers

- `tj-rt7w.7`: paired 20+20 measured round, open, now blocked on `.10`.
- `tj-rt7w.10`: the genuine split, open with a plan in its Bead notes.
- `tj-rt7w.14`: the R2 bound has no semantic half; a fix owes a measured round.
- Deterministic-route retirement: explicitly outside this stage.
- Deployment and any live proof: not authorized or performed here.
