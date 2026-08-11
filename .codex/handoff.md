# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Accepted stage id: `tj-rt7w-overcomplication`
Status: children `tj-rt7w.1` through `.6` are closed in six local commits.
`tj-rt7w.7` remains open and unstarted by stage scope.

Documentation: no external/versioned boundary — this stage changes internal
first-party Python ownership and response policy only.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- Every text guard is bounded: it may remove a sentence but cannot blank the
  reply. Meaningful shorter replacements remain valid; character count is not
  a correctness signal.
- The opening, selling-turn, closed-question, and premature quote-detail guards
  are pure module functions with explicit state, not engine closures.
- `src/llm/money.py` owns money recognition and canonical decimal rendering for
  engine budgets, extraction, grounding, and the opening guard.
- The unsupported customer-owned-furniture service family is blocked. The
  prompt was tried first with exactly three authorized Luna calls; one measured
  failure admitted the bounded grounding rule.
- `process_message` is a 40-line public facade and `src/llm/engine.py` is 11,849
  lines. `tests/test_llm_engine_structure.py` enforces both settled limits.
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
- `4640602` — `.6`, split message processing runtime.

Each closed child has a validated artifact under
`.codex/stages/tj-rt7w-overcomplication/artifacts/`.

## Verification

- Final `.6` gates: Ruff passed; format passed over 367 files; Mypy passed over
  173 source files; Pytest `3547 passed, 19 skipped`; process verification
  passed.
- Focused engine and deterministic-route set: 917 passed.
- Stage closeout receipt is recorded by
  `scripts/orchestration/run_stage_closeout.py` at `slice_acceptance`.

## Active work

- `tj-rt7w.7` is deliberately open and unstarted. It is the paired measured
  round after the structural work, not part of this stage's delivery.
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

Next stage id: `tj-rt7w-measured-round`

Recommended action: open a separate stage for `tj-rt7w.7`; do not fold its
paid paired measurement into the accepted structural stage.

Open a separate stage for `tj-rt7w.7`. Re-read its Bead before starting, use the
frozen twenty openings and paired baseline, make exactly the authorized calls,
judge the complete results directly as Codex, report only derived identifiers
and integers in tracked artifacts, and leave production untouched.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-rt7w-measured-round` and Bead `tj-rt7w.7`.
Read `AGENTS.md`, `.codex/orchestrator.toml`, this handoff, the over-complication
spec, and the `.7` issue before acting. Keep the frozen rulers unchanged, make
only the authorized 20 Luna + 20 GLM calls, act as the result judge yourself,
keep corpus text outside Git, and do not push or deploy.

## Explicit defers

- `tj-rt7w.7`: paired 20+20 measured round, open and unstarted.
- Deterministic-route retirement: explicitly outside this stage.
- Deployment and any live proof: not authorized or performed here.
