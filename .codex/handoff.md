# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: delivered locally with all gates green and pushed to `origin/main`
with CI green, which deploys. Nine rounds were read blind with the owner's
authority: six on the frozen twenty, weighted mean 14.6 to 18.7 of 30, and
three over the whole Arabic population, 9.6 to 10.6. `tj-fcv8`, `tj-l0e3`,
`tj-fcfn`, `tj-jfmv`, `tj-40gc` and `tj-z1fn` are found, fixed and closed. On
the twenty, every rule the set can charge reads 2.00 except rule 5 at 1.95.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`,
  and the prompt and guards consume the same immutable set. The name ask is
  state-owned: `customer_name_asked` is recorded only when an ask reaches the
  customer, and `_store_name_gate_pending_request` is the one re-elicitation
  trigger. A name in the current inbound message joins the current-message
  facts, so a first-turn signature cannot receive another name question in
  either language -- `tj-40gc` added the Arabic introduction shapes, bounded
  like the English ones so a statement about the request is never a sender.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate; unavailable, rejected, empty and `cannot_fix` fall
  back to the validated grounding repair. It notifies on failure by default and
  only an offline diagnostic passes `notify_on_failure=False`. Its protected
  journal lives in the Git common dir, never the working tree.
- `--second-reader` adds the paid reader beside the root, never instead, and is
  off by owner decision. It set the paid model as the judge until 2026-08-13
  and had raised `KeyError` since the vendor split, so no two-reader round had
  ever run.
- The paid round sends the prompt production sends, built from the product's
  own functions so a round follows them when they change: runtime directives,
  the ask permission list, and the name read out of the opening. It does *not*
  search the catalog the way production does -- see `tj-rcg5`. `FROZEN_SETS`
  registers which sets may be measured and `preflight --set` names one.
- `consultative_opening_directive` takes `opening_states_the_offer` and the
  opening's own text, so a first turn is told what it will begin with rather
  than asked what it already said -- the self-cancelling shape removed on
  2026-08-08. It also states the options a discovery question may offer, kinds
  of work or space, positively and with no prohibition, under the 2026-08-10
  observation that this model follows an instruction and loses a ban.
  `solution_consultation_directive` carries rules 9 and 10 one stage later.
- `collapse_question_form` runs before the first-turn opening guard, not after,
  under its unchanged `REDUCING` contract: the guard folds the canonical name
  question on and the collapse drops every question after the first, so the old
  order deleted that fold every first turn. A folded pair counts as one.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`,
  7 records differing -- dialogs 28, 875 and 1291, each read and intended. It
  was 55 until the guard order was restored on 2026-08-13, and the 7 are a
  strict subset: 48 removed, none introduced.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051, notifications suppressed; delivery is 20 of 20 with no handoffs.
- `tj-7gpw`: every number measured before 2026-08-12, 18.94 included, was
  scored on a prompt missing the runtime directives and the ask permission
  list, so nothing after is comparable. The replacement baseline is
  `tj-7gpw-parity-baseline-c-20260812`, digest `61b6c9229ab295a4…`.
- Six rounds on the same twenty, same reader, one change each, all accepted.
  Weighted mean 14.6 to 18.7 of 30, last interval [15.6, 21.7]; raw 10.6 to
  13.8; the 11 low-ceiling openings 75% to 100% of their 9.6 and the 9 others
  78% to 99% of 30.0. Attribution per round is in Beads. One `tj-l0e3` round is
  discarded as unfaithful under `tj-l0e3.2`.
- The Arabic rounds over `arabic-12`, every Arabic opening the corpus has, 12
  of 1358 -- a population, not a sample. Weighted 9.6 to 10.6, low band 93% to
  99%. That mean is *not* comparable to the twenty's: 11 of 12 sit in the 9.6
  band against 11 of 20, so only the band compares. The hypothesis that an
  English directive fails to reach Arabic is disproved. What Arabic cost was
  `tj-40gc` and `tj-z1fn`, both closed.
- `tj-z1fn` is the lesson worth keeping. Quoting the canonical opening helped
  Arabic and cost English rule 7 2.00 to 1.80: four replies answered the
  quotation with a capability list. Naming what the opening leaves uncovered --
  the customer -- removed them. Measure both sets before shipping a shared
  directive.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and format clean over `src/ tests/ scripts/`; Mypy clean over 174 source
  files; full Pytest `3695 passed, 19 skipped`; process verification passed. The
  protected replay moved once and on purpose, toward the frozen `1fc87c04…`
  baseline: 55 differing records to 7, the 7 a strict subset of the 55, so 48
  were removed and none introduced. It has not moved since; `tj-fcfn` is
  generation-side and the aggregate stands at `1b425bd1…`.

## Constraints

- Push to `origin/main` was authorized on 2026-08-12 and performed. No PR,
  deploy, production/staging mutation, model-configuration change or real-user
  message is authorized or performed.
- Paid calls: 60 on the repair judge, all on stored dialogs 819 and 789 with the
  failure page suppressed. The owner then authorized, on 2026-08-12, a
  re-baseline round, the paired `tj-fcv8` round and the `tj-ge07` baseline as
  one block, then on 2026-08-13 the `tj-l0e3`, `tj-fcfn`, Arabic and `tj-z1fn`
  rounds, and the two-reader round. Total spent $0.1908 across ten rounds, of
  which $0.1627 is the single paid second reader and $0.0045 bought nothing: $0.0020 to four attempts killed by upstream 429s and a 503, and
  $0.0025 to the `tj-l0e3` round discarded as unfaithful under `tj-l0e3.2`. The `tj-ge07` baseline
  is authorized and deliberately not taken. The canonical runtime target
  remains `https://noor.starec.ai`; it was not contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change` — no module was
  added or moved; `graph-reviewed: no-change-needed` — Graphify is not
  initialized.

## Next recommended

Next stage id: not opened. Recommended action: re-read one stored round under
`docs/root-reading-convention.md` and report the drift. No deploy authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage after selecting the next open Beads goal.

## Tracker after the 2026-08-13 audit

- 27 live issues audited against current state; 17 closed with recorded
  reasons, 1 deferred. Nothing closed on a title alone. Verified in code:
  `tj-6f4z`, `tj-07bs`, `tj-g3f`. Superseded by measurement or owner decision:
  `tj-wvo4`, `tj-odeq`, `tj-vz7o.8`, `tj-vz7o.9`, `tj-vz7o.10`, `tj-vz7o.12`,
  `tj-vz7o.13`, `tj-swgu.14`, and the P0 epics `tj-2m5m` and `tj-swgu`. Not to
  be done as written: `tj-vz7o.4`, `tj-vz7o.5`, `tj-ge07`, `tj-2m5m.4`.
  `tj-i653` deferred: it needs live state.
- A candidate explanation was rejected rather than used: `tj-jlx4` looked like
  reader variance, but the gap is 2.0 while S07 moved 6.58 with non-overlapping
  ranges, and the bead already diagnosed a content choice -- a closing turn
  offering two coffee tables to a lab that asked about fume hoods. Open at P2.
- Priority inversion named: `tj-final27.6` is engineering-complete, disabled
  safe and policy-gated, and waits on one written client sentence -- a referral
  policy or an explicit exclusion -- which blocks `tj-final27.9`, the final
  acceptance pack. Raised to P1 for what it blocks.

## Owner decisions of 2026-08-13

- Referrals wait on the owner's own message. Do not chase, and do not read the
  missing policy as a defect; `tj-final27.6` is engineering-complete and is all
  that blocks `tj-final27.9`.
- Rule 11: disposition 3. A discount is a manager's decision or is already in
  the catalog price, so Noor never offers one and the zero is policy; every
  score prints the 28/30 policy cap beside it. The permitted shape ships:
  verified rows as one package at the catalog price.
- The client document was decided, not asked. It leads with the Zoho deal
  export: outcomes are visible for 192 of 1400 dialogues, so we can say Noor
  does what the rubric asks but not that Noor sells. The four-criteria figure
  is reframed on the owner's point that people not doing a thing is no evidence
  against it. The evaluator prompt is withdrawn.
- Deploy and live verification are authorized. Production is current, not
  stale: CI deploys on any push to `main` touching `src/` and the job succeeded
  on `d19bfdb`, the last such commit, carrying every fix of 12-13 August.
  `/api/v1/health` reads ok. `tj-9scy`: no endpoint reports the deployed SHA,
  which is why a stale assumption about the live build went unchecked.

## Handed to another agent

- `.codex/handoff-chatgpt5-2026-08-13.md` is the prompt for ChatGPT-5 to close
  `tj-9scy`, `tj-f6yp` and `tj-rcg5`. `prompt-check --kind handoff --profile
  gpt-5.6` passes with a size warning only. Each bead's `DESIGN` carries the
  spec; the prompt defers to it.
- `tj-vz7o.12` was nearly handed over with the wrong diagnosis and is closed
  instead. It read as "the reply has catalog rows and quotes none". The rows
  for dialog 436, "I looking Office table", are two executive chairs and a
  portable skincare fridge, identically in all six rounds; declining them was
  right. The cause is `tj-rcg5`: `catalog_matches` scores keyword overlap where
  production searches semantically, so "office" carries "Executive Office
  Chair". A directive to quote what you are handed would have put a skincare
  fridge in front of a desk buyer. This bounds the rounds as `tj-7gpw` did: any
  judgement of how a reply used the catalog was made against evidence
  production would not supply. Rules 8 and 9 are exposed.

## Explicit defers

- Seven rules of fifteen cannot be charged by any rig this project has: 14 and
  15 need a tool-filled next step or a deferred decision (one second message in
  913 defers), 6, 10 and 13 a project signal (9 of 913), 11 a two-family order
  (16 of 106), 12 a later turn. This bounds what any opening round can claim
  and it closed four beads. The two-turn set is kept for a tools-enabled rig.
- The reader gap is a number, `tj-4q79`: one round carried both readings, the
  root judge blind and `z-ai/glm-5.2` paid beside it at $0.1627. Mean absolute
  gap 2.0 raw points per opening, worst 4.0; rules 1, 2 and 8 agree exactly,
  the paid reader harsher on 4 (-0.80), 9 (-0.70) and 5 (-0.50). A paired delta
  under about 2 raw points is inside reader variance: the session series clears
  it, but no single round should be defended by its total. No second reader
  again by owner decision, so `docs/root-reading-convention.md` holds the 0/1/2
  standard. The re-read that would make it a drift number is still owed.
- Rule 5's ceiling on the frozen twenty is 1.95, not 2.00: dialog 28 is a job
  application with no furniture need and rule 5 is charged anyway. The measured
  1.95 is that ceiling; the rubric is not changed for it.
- `tj-ee5f.1` needs real transports and production producers; `tj-ee5f.5`
  waits on the Wazzup provider fixing delivered/read callbacks, which is
  theirs, not ours.
