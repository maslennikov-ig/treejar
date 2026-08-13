# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-rcg5-semantic-catalog-evidence`
Status: `tj-9scy`, `tj-f6yp` and `tj-rcg5` are closed and deployed. The seven
defects the 2026-08-13 audit left -- `tj-eedk`, `tj-d651`, `tj-rdqc`, `tj-qfsy`,
`tj-izkn`, `tj-hls5`, `tj-bzr0` -- are closed in one tested commit each,
`c058d08`..`869ee2a`, on local `main` and **not pushed**: a push auto-deploys
and needs the owner's word.

Documentation: `docs-resolve` covered pgvector and pinned model revisions; local code owns Treejar behavior.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`,
  and the prompt and guards consume the same immutable set. The name ask is
  state-owned: `customer_name_asked` is recorded only when an ask reaches the
  customer, and `_store_name_gate_pending_request` is the one re-elicitation
  trigger. A name in the current inbound message joins the current-message
  facts, so a first-turn signature cannot receive another name question in
  either language -- `tj-40gc` added the Arabic introduction shapes, bounded
  like the English ones so a statement about the request is never a sender.
  `asks_the_company_activity` records the one-turn cooldown only when a signal
  sits inside a question sentence -- `tj-eedk`: bare phrases let "day to day
  office use" close the ask nobody made. The broad phrase scan survives under
  its own name, because suppressing the carry is not writing state.
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
  the ask permission list, and the name read out of the opening. Its measured
  catalog evidence now comes from exact local pgvector through
  `src.rag.pipeline.search_products`; a protected artifact pins that path before
  provider work. `FROZEN_SETS` registers measurable sets and `preflight --set`
  names one. The opening's price anchor comes from the pinned catalog snapshot
  through the same `anchor_line_from_catalog_rows` production uses, so rules 2
  and 7 are comparable again; `preflight --catalog-snapshot` is required and
  hashed against the artifact's own catalog digest before any provider call.
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

- `/api/v1/health` resolves the release SHA once per process and answers a
  commit SHA or `unknown`, bounded by pattern and length in the schema.
- CI job `semantic-evidence` runs the exact-pgvector producer test against a
  pgvector service on every change to `scripts/corpus_bridge/` or `src/rag/`,
  and reads the outcome so a skip cannot pass. It is not in `deploy`'s needs.

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
  78% to 99% of 30.0. Per-round attribution is in Beads; one `tj-l0e3` round is
  discarded as unfaithful under `tj-l0e3.2`.
- The Arabic rounds over `arabic-12` cover every Arabic opening the corpus has,
  12 of 1358 -- a population, not a sample. Weighted 9.6 to 10.6, low band 93%
  to 99%. That mean is *not* comparable to the twenty's: 11 of 12 sit in the 9.6
  band against 11 of 20, so only the band compares. The hypothesis that an
  English directive fails to reach Arabic is disproved; what Arabic cost was
  `tj-40gc` and `tj-z1fn`, both closed.
- `tj-z1fn` is the lesson worth keeping. Quoting the canonical opening helped
  Arabic and cost English rule 7 2.00 to 1.80: four replies answered it with a
  capability list, and naming what the opening leaves uncovered -- the customer
  -- removed them. Measure both sets before shipping a shared directive.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff, format and Mypy clean; process verification passed. The protected
  replay has not moved since it was restored toward the frozen `1fc87c04…`
  baseline; the aggregate stands at `1b425bd1…`. It cannot show a SELLING-turn
  change: it pins `is_first_turn=True` and no record carries a foldable
  ask-list.

## Constraints

- Push to `origin/main` was authorized on 2026-08-12 and performed. No PR,
  deploy, production/staging mutation, model-configuration change or real-user
  message is authorized or performed.
- Paid calls total $0.1908 across ten authorized rounds, of which $0.1627 is
  the single paid second reader and $0.0045 bought nothing (upstream 429s/503,
  and the `tj-l0e3` round discarded under `tj-l0e3.2`). Per-round authorization
  and attribution are in Beads. The `tj-ge07` baseline is authorized and
  deliberately not taken.
- `https://noor.starec.ai/api/v1/health` was read once on 2026-08-13,
  unauthenticated and read-only. Nothing else on the runtime was contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change` — no module was
  added or moved; `graph-reviewed: no-change-needed` — Graphify is not
  initialized.

## Next recommended

Next stage id: not opened
Recommended action: select the next open Bead after this delivery.

## Starter prompt for next orchestrator

Use $orchestrator-stage after selecting the next open Beads goal.

## Tracker after the 2026-08-13 audit

- 27 live issues audited against current state; 17 closed with recorded
  reasons, 1 deferred, none on a title alone. The per-issue disposition is in
  Beads. `tj-i653` deferred: it needs live state.
- The delivery audit reopened two of the three and opened seven defects; all
  seven are closed above, and `tj-rcg5` itself stayed closed throughout.
- `tj-jlx4` is not reader variance: the gap is 2.0 while S07 moved 6.58 with
  non-overlapping ranges, and the bead diagnoses a content choice -- two coffee
  tables offered to a lab that asked about fume hoods. Open at P2.
- `tj-final27.6` is engineering-complete, disabled safe and policy-gated, and
  waits on one written client sentence -- a referral policy or an explicit
  exclusion. It blocks `tj-final27.9`, so it is P1 for what it blocks.

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
- Deploy and live verification are authorized, and that authorization was
  spent: `origin/main` is `87b6879` and production runs `5318e49`. The seven
  audit fixes above are a separate push and a separate authorization.

## Active handoff

- `tj-rcg5` implements the two-stage route: exact local pgvector retrieval
  through `src.rag.pipeline.search_products`, then a fail-closed measured
  consumer. The normative spec is
  `docs/superpowers/specs/2026-08-13-semantic-catalog-evidence-boundary-spec.md`;
  the executable plan is
  `docs/superpowers/plans/2026-08-13-semantic-catalog-evidence-boundary.md`.
- Final protected evidence uses 332 catalog rows, BGE-M3 revision
  `5617a9f61b028005a4858fdac845db406aefb181`, exact pgvector extension `0.8.5`
  and retrieval code `05f6c8e765c6fdc0d473968ba6e42aee26bea40e5bb3a9aa6819e896fffd97e4`.
  Golden P@3/R@3/nDCG@3 is `0.7222/0.8333/0.8333`, zero hard failures; the
  frozen twenty also has zero hard failures. Presence of rows never creates a
  duty to quote them; only qrels-confirmed SKUs reach generation.
- Exact SKU is owned by the direct `get_stock`/catalog route, not semantic
  search: BGE-M3 input carries no SKU and a real SKU query missed its product,
  so semantic qrels exclude it rather than mask the route boundary.

## Explicit defers

- Seven rules of fifteen cannot be charged by any rig this project has: 14 and
  15 need a tool-filled next step or a deferred decision (one second message in
  913 defers), 6, 10 and 13 a project signal (9 of 913), 11 a two-family order
  (16 of 106), 12 a later turn. This bounds what any opening round can claim
  and it closed four beads. The two-turn set is kept for a tools-enabled rig.
- The reader gap is a number, `tj-4q79`: mean absolute 2.0 raw points per
  opening, worst 4.0, measured once against a paid reader at $0.1627. A paired
  delta under about 2 points is inside reader variance, so no single round is
  defended by its total. Detail and per-rule split are in the bead and in
  `docs/root-reading-convention.md`. The re-read that would make it a drift
  number is still owed.
- Rule 5's ceiling on the frozen twenty is 1.95, not 2.00: dialog 28 is a job
  application with no furniture need and rule 5 is charged anyway. The measured
  1.95 is that ceiling; the rubric is not changed for it.
- `tj-ee5f.1` needs real transports and production producers; `tj-ee5f.5` waits
  on the Wazzup provider fixing delivered/read callbacks, which is theirs.
