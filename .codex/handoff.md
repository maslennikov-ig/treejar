# Orchestrator Handoff

Updated: 2026-08-12
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 are accepted locally with all requested gates green. No remote or
runtime action is part of this stage.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by
  `permitted_asks_for_turn`; the prompt and deterministic guards consume the
  same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask actually reaches the customer, cleared explicitly for re-elicitation,
  and never reconstructed from previous assistant text.
- A name present in the current inbound message participates in the same
  current-message facts used by rendering and later persistence. A first-turn
  signature therefore cannot receive another name question.
- The opening guard recognises a company-only identity mention after URLs are
  excluded. It removes at most one sentence and preserves the whole model reply
  when removal would leave no meaningful text.
- `question_form` runs on first turns under its unchanged `REDUCING` contract
  and still proves `only_asks_were_dropped`. `name_chase` remains first-turn
  gated because the recorded evidence shows that lifting it changes nothing.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix`
  outcomes fall back to the validated deterministic grounding repair.
- A fallback containing only Noor's own opening plus a question creates the
  manager handoff. A substantive fallback is sent without a handoff.
- Diagnostic repair replay always sets
  `notify_on_failure_override=False`. Its protected journal is in the Git
  common directory and never stores dialog text in the working tree.
- Guard modes in `src/llm/response_policy.py` did not change.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
  It was not re-baselined.
- Current policy replay aggregate is
  `c842132fde97fa2fec40b7bbb5f6c7637a9a61fbc8bbeed7a2268d4f57dd7fc5`:
  56 intended records differ across the three stored runs and no current reply
  is grounding-flagged.
- Dialogs 28, 436, 789, 875 and 1291 were read individually. The differences
  are bounded to duplicate identity/name asks or question folding described in
  the stage artifact.
- D6 used exactly eight approved repair-judge calls: four each for dialogs 819
  and 789, $0.00066402 total, zero failed calls, zero unusable stubs and all
  eight notifications disabled. Judge corrections were never byte-identical
  to the deterministic candidate. Dialog 789 escalated 4/4 by the explicit
  opening-plus-question rule; dialog 819 escalated 0/4.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Focused D1-D5 set: 960 passed. Full `tests/test_llm_engine.py`: 823 passed.
  Focused D6/response-policy set: 102 passed.
- Ruff check and format are clean over `src/ tests/ scripts/`; Mypy is clean over
  174 source files; full Pytest is `3640 passed, 19 skipped`; process
  verification passed.

## Constraints

- No push, PR, deploy, production/staging mutation, model-configuration change
  or real-user message is authorized or performed.
- No further paid calls are needed or permitted by this stage. Eight of the
  maximum twenty approved calls were used, only for dialogs 819 and 789.
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
- Deployment and live runtime verification are outside this local stage and
  were not authorized.
