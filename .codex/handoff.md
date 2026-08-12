# Orchestrator Handoff

Updated: 2026-08-12
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 are delivered locally with all requested gates green, and the
post-acceptance audit fix `tj-w224` is delivered on top of them. `main` is
pushed to `origin/main` with CI green. `tj-9e15` and `tj-3h0w` are closed. No
deploy or runtime mutation was authorized or performed.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by
  `permitted_asks_for_turn`; the prompt and deterministic guards consume the
  same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask actually reaches the customer, and never reconstructed from previous
  assistant text. `name_chase` reads that slot itself, not the permission
  derived from it. The name gate is the one re-elicitation trigger:
  `_store_name_gate_pending_request` clears the slot when it parks a customer
  request behind the name, so the guard cannot remove the gate's own question.
- A name present in the current inbound message participates in the same
  current-message facts used by rendering and later persistence. A first-turn
  signature therefore cannot receive another name question.
- The opening guard recognises an introduction as our persona *and* our company,
  after URLs are excluded, in Latin or Arabic script. It removes at most one
  sentence and preserves the whole model reply when removal would leave no
  meaningful text. Recognising the company alone was shipped and reverted in
  `tj-w224`: it deleted answering sentences such as "Treejar supplies new office
  furniture, but we don't buy customer-owned tables", and it also stripped the
  canonical opening off quotation replies.
- `question_form` runs on first turns under its unchanged `REDUCING` contract
  and still proves `only_asks_were_dropped`. `name_chase` remains first-turn
  gated because the recorded evidence shows that lifting it changes nothing.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix`
  outcomes fall back to the validated deterministic grounding repair.
- A fallback containing only Noor's own opening plus a question creates the
  manager handoff. A substantive fallback is sent without a handoff.
- `run_repair_judge` notifies on failure by default; only the diagnostic replay
  passes `notify_on_failure=False`. Production keeps the page: an unavailable
  judge no longer costs the customer their reply, but a paid vendor going dark
  is still worth hearing about. The protected journal is in the Git common
  directory and never stores dialog text in the working tree.
- Guard modes in `src/llm/response_policy.py` did not change.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
  It was not re-baselined.
- Current policy replay aggregate is
  `825f26ca85533b6d6499b4606a2e0fcb87df1ee10ce7fba2dbd434381b965900`:
  55 intended records differ across the three stored runs. One current reply is
  grounding-flagged, `tj-vz7o-luna-glm-20260810-rerun/789`, which is the
  baseline's own behaviour restored and is what the repair path exists for.
- Dialogs 28, 436, 789, 875 and 1291 were read individually. The differences
  are bounded to duplicate identity/name asks or question folding described in
  the stage artifact.
- D6 used exactly eight approved repair-judge calls: four each for dialogs 819
  and 789, $0.00066402 total, zero failed calls, zero unusable stubs and all
  eight notifications disabled. Dialog 789 escalated 4/4 by the explicit
  opening-plus-question rule; dialog 819 escalated 0/4 and shipped a
  substantive reply. Read honestly, the judge contributed nothing in 8 of 8:
  every correction was rejected, 819 four times as `correction_still_flagged`
  and 789 four times as `correction_has_no_answer`, and all eight deliveries
  came from the deterministic fallback. Whether the paid judge earns its place
  on this path was then measured in `tj-3h0w`.
- `tj-3h0w`, twenty approved calls under current code, $0.001573056, zero
  failures and zero unusable stubs: no judge answer was byte-identical to the
  deterministic candidate (0/20), so unanchoring works. Delivery is thin.
  Dialog 819 delivered 0/10 judge corrections, 8/10 rejected as
  `correction_still_flagged`; dialog 789 delivered 2/10. Eighteen of twenty
  deliveries came from the deterministic fallback. The judge also approved a
  guard-flagged 819 reply 2/10, which ships the flagged claim unchanged and
  makes the same input escalate or not depending on the run: `tj-uhbq`.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Focused D1-D5 set: 960 passed. Full `tests/test_llm_engine.py`: 823 passed.
  Focused D6/response-policy set: 102 passed.
- Ruff check and format are clean over `src/ tests/ scripts/`; Mypy is clean over
  174 source files; full Pytest is `3642 passed, 19 skipped`; process
  verification passed. Re-run after `tj-w224` and `tj-9e15`. GitHub CI on
  `origin/main` is green for `e1e61ed`.

## Constraints

- Push to `origin/main` was authorized by the owner on 2026-08-12 and performed.
  No PR, deploy, production/staging mutation, model-configuration change or
  real-user message is authorized or performed.
- Paid calls: eight for D6 plus twenty authorized for `tj-3h0w`, all on stored
  dialogs 819 and 789, all with the failure page suppressed. No further paid
  call is permitted without new authority.
- The canonical runtime target remains `https://noor.starec.ai`; it was not
  contacted or changed.

## Documentation and graph review

- `docs-reviewed: updated` — the stage summary, artifact and this handoff record
  the durable policy and privacy-safe proof.
- `project-index: reviewed-no-change` — no module was added, removed or moved.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: not opened

Recommended action: select the next open Beads goal from current repository
truth. Do not push or deploy this stage without new authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after selecting the next open Beads goal from
current repository truth.

## Explicit defers

- `tj-2m5m.4`: separate out-of-scope discovery work remains tracked in Beads.
- `tj-uhbq`: the repair judge can approve a reply the grounding guard flagged.
  Owner decision pending; no further paid measurement until it is taken.
- Deployment and live runtime verification are outside this local stage and
  were not authorized.
