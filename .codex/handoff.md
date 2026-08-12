# Orchestrator Handoff

Updated: 2026-08-12
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 are delivered locally with all requested gates green, and the
post-acceptance audit fix `tj-w224` is delivered on top of them. `main` is
pushed to `origin/main` with CI green. `tj-9e15` and `tj-3h0w` are closed. No
deploy or runtime mutation was authorized or performed. A measured round was
taken on 2026-08-12 with the owner's authority, read blind by the root judge,
and it found a customer-visible defect that no earlier round could have seen.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`;
  the prompt and deterministic guards consume the same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask actually reaches the customer, and never reconstructed from previous
  assistant text. `name_chase` reads that slot itself, not the permission
  derived from it. The name gate is the one re-elicitation trigger:
  `_store_name_gate_pending_request` clears the slot when it parks a customer
  request behind the name, so the guard cannot remove the gate's own question.
  A name in the current inbound message participates in the same
  current-message facts used by rendering and persistence, so a first-turn
  signature cannot receive another name question.
- The opening guard recognises an introduction as our persona *and* our company,
  after URLs are excluded, in Latin or Arabic script. It removes at most one
  sentence and preserves the whole model reply when removal would leave no
  meaningful text. Recognising the company alone was shipped and reverted in
  `tj-w224`: it deleted answering sentences and stripped the canonical opening
  off quotation replies.
- `question_form` runs on first turns under its unchanged `REDUCING` contract
  and still proves `only_asks_were_dropped`. `name_chase` remains first-turn
  gated because the recorded evidence shows that lifting it changes nothing.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix`
  outcomes fall back to the validated deterministic grounding repair. A
  fallback containing only Noor's own opening plus a question creates the
  manager handoff; a substantive fallback is sent without one.
- `run_repair_judge` notifies on failure by default; only an offline diagnostic
  passes `notify_on_failure=False`. Production keeps the page: an unavailable
  judge no longer costs the customer their reply, but a paid vendor going dark
  is still worth hearing about. The protected journal is in the Git common
  directory and never stores dialog text in the working tree. Guard modes in
  `src/llm/response_policy.py` did not change.
- `solution_consultation_directive` carries rules 9 and 10 into the
  presentation turn, which the opening directive never reached. One stage only,
  so the two never share a turn or double their one-question bound, and the
  same transactional-narrowing stand-down applies. It is generation-side, so
  the protected replay cannot see it and does not.
- The paid acceptance round now sends the prompt production sends.
  `build_generation_messages` appends `[RUNTIME DIRECTIVES]` from the product's
  own `engine._turn_runtime_directives`, and `[PERMITTED ASKS THIS TURN]` from
  `permitted_asks_for_turn` with the frozen set's own properties. Both come from
  the product functions, so a round follows them when they change.
- `consultative_opening_directive` takes `opening_states_the_offer`. The caller
  knows whether the deterministic opening will be prepended to this reply, so
  on a first turn the directive says the offer is already stated and must not
  be repeated. This is not the self-cancelling condition removed on
  2026-08-08: that one asked the model what it had already said, this one is
  code stating what the reply will begin with.
- A round survives a busy provider. A 200 carrying an `error` object and no
  choices, or a refusal with a busy status, produced no completion, so both are
  retried with backoff and every provider error is recorded; an empty or
  truncated completion is an answer and is never re-rolled, a bad request is
  never repeated, and a request whose outcome is unknown is never repeated.
- Catalog-supported skus are removed from a reply before the acceptance
  grounding check reads it: the asserted-number pattern reads inside an
  identifier, so `1.2T` in a quoted sku yielded a bare `2` that no price
  supported. An invented identifier still carries whatever it asserts. The
  public summary names the judge that read the round, taken from the results.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate is
  `825f26ca85533b6d6499b4606a2e0fcb87df1ee10ce7fba2dbd434381b965900`: 55
  intended records differ across the three stored runs. One current reply is
  grounding-flagged, `tj-vz7o-luna-glm-20260810-rerun/789`, which is the
  baseline's own behaviour restored and is what the repair path exists for.
  Dialogs 28, 436, 789, 875 and 1291 were read individually; the differences
  are bounded to duplicate identity/name asks or question folding.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051, every notification suppressed. D6 (8): the judge contributed
  nothing. `tj-3h0w` (20): unanchoring works, delivery 2 of 20. `tj-3i8m` found
  why -- a flag arrived as the bare string `future_stock_check` -- and once each
  flag carried `flagged_sentences` and `rules`, delivery was 20 of 20 with zero
  handoffs. `tj-b9mg` (32) read the wording: correct on both dialogs. Two
  refinements were reverted; one produced "assembly is not a service we offer",
  false and caught by no guard. Rules are written to be safe if quoted, because
  the judge quotes them almost verbatim. `tj-uhbq`, closed: an approval means
  the judge read the reply and found it supported, so we send the original.
- `tj-7gpw`: every number this project has measured, the 18.94 baseline
  included, was scored on a prompt missing two blocks production always sends:
  the runtime directives the turn earns, and the ask permission list. Directive
  work read as unmeasured because the paid round did not send it either. The
  consequence is recorded rather than hidden: no round after this fix is
  comparable to the 18.94 baseline.
- The measured round of 2026-08-12, `tj-7gpw-parity-baseline-c-20260812`:
  twenty Luna generations plus one repair-judge call, $0.0054, judged by the
  root orchestrator reading blind. Weighted mean 14.6/30, 95% interval
  [12.0, 17.1]; raw mean 10.6; 11 openings against a 9.6 ceiling reach 7.2 and
  9 against a 30.0 ceiling reach 23.5. Zero critical failures, 20/20 in the
  customer's language, accepted. `generation_prompt_set_digest` is
  `61b6c9229ab295a4…`, which differs from every earlier round because those
  rounds sent a prompt production does not send. This is the new baseline;
  18.94 is not comparable to it.
- What that reading found: 18 of 20 replies said Treejar's line of business
  twice, three as a lower-case fragment copied out of the directive's own
  example clause. That is `tj-fcv8`.
- The paired round, `tj-fcv8-paired-b-20260812`: same twenty openings, same
  reader, same prompt, only the directive changed. Twenty generations, no
  repair call, $0.0036. Rule 7 moves +0.45 (1.50 to 1.95), rule 2 +0.15, rule 4
  +0.15; the fragments are gone, 0 against 3, and one reply of twenty still
  doubles. Weighted mean 14.6 to 15.0, and the low-ceiling band from 75% of its
  ceiling to 82%. Rule 5 moves the other way, -0.15: three replies traded "what
  are you furnishing" for a product menu or a width choice. One reader on
  twenty openings, not chased, recorded rather than rounded away. Rules 3, 8
  and 9 did not move. Rule 3 is 0.20 of 2 in both rounds: 19 of 20 replies
  never ask how to address the customer although the ask was permitted every
  time. Not yet opened as work.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and format clean over `src/ tests/ scripts/`; Mypy clean over 174 source
  files; full Pytest `3680 passed, 19 skipped`; process verification passed.
  The protected policy replay aggregate is unchanged at `825f26ca85533b6d…`
  against the frozen `1fc87c04…` baseline: today's work is generation-side and
  harness-side, and the deterministic reply chain did not move.

## Constraints

- Push to `origin/main` was authorized by the owner on 2026-08-12 and performed.
  No PR, deploy, production/staging mutation, model-configuration change or
  real-user message is authorized or performed.
- Paid calls: 60 on the repair judge, all on stored dialogs 819 and 789 with
  the failure page suppressed. The owner then authorized, on 2026-08-12, a
  re-baseline round, the paired `tj-fcv8` round and the `tj-ge07` baseline as
  one block. Spent: $0.0054 for the re-baseline, $0.0036 for the paired round,
  $0.0020 lost to four attempts killed by upstream 429s and a 503. The
  `tj-ge07` baseline is authorized and deliberately not taken, for the reason
  above. The canonical runtime target remains `https://noor.starec.ai`; it was
  not contacted or changed.

## Documentation and graph review

- `docs-reviewed: updated` — the stage summary, artifact and this handoff record
  the durable policy and privacy-safe proof.
- `project-index: reviewed-no-change` — no module was added or moved.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: not opened. Recommended action: `tj-ge07` part two, the second
turn in the harness. Do not deploy without new authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after selecting the next open Beads goal from
current repository truth.

## Explicit defers

- `tj-ge07` part two was stopped before it was built, and the baseline round it
  would have fed was not paid for. Rule 14 needs `confirmed_next_step`, which is
  a quote, CRM, a scheduled follow-up or the closing stage -- every one of them
  tool-filled, and the harness forbids tools by contract. Rule 15 needs the
  customer to defer the decision, and across all 913 evaluated corpus dialogs
  with a text follow-up exactly one second message does; on the frozen twenty it
  is zero. Thirty real second messages read like "Only 3" and "Can you share the
  details": the detector is right, the conversation is simply not there at turn
  two. Nine of 913 signal a project, so rules 6, 10 and 13 cannot be charged on
  a representative twenty either. The stage is slot-driven and slots are
  tool-filled, so a tool-free second turn stays at `greeting` and
  `solution_consultation_directive` never fires. A second turn would still buy
  the selling-turn guards firing in a measured round for the first time; that is
  worth having and is not what the task was opened for, so it waits on a
  decision.
- `tj-ge07`: the frozen two-turn set exists, `tj-ge07-two-turn-20260812`, seed
  `20260812`, twenty scenarios over five managers, stored human mean raw total
  5.2, manager-cluster interval [1.43, 6.05]. The manifest is tracked and
  text-free. The harness still generates one turn.
- Rule 3, the name ask, is missing from 19 of 20 openings while permitted every
  time. Read in both rounds, not opened as work, not fixed.
- `tj-2m5m.4`: the prompt half is delivered and unmeasured, and the owner
  decided on 2026-08-12 that the structural job slot waits for the numbers. It
  now waits for something no round can give it: the solution stage needs slots,
  slots need tools, and the acceptance harness forbids tools. Separate
  out-of-scope discovery work also remains tracked in Beads.
- Deployment and live runtime verification are outside this local stage and
  were not authorized.
