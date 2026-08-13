# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-rcg5-semantic-catalog-evidence`
Status: `tj-9scy`, `tj-f6yp` and `tj-rcg5` are closed and deployed. The seven
defects the 2026-08-13 audit left -- `tj-eedk`, `tj-d651`, `tj-rdqc`, `tj-qfsy`,
`tj-izkn`, `tj-hls5`, `tj-bzr0` -- are closed in one tested commit each,
`c058d08`..`869ee2a`, pushed and deployed on owner authorization. Production
runs `2876774`, confirmed through `/api/v1/health`. `tj-68au` then measured the
first round comparable to the six before `4a0883a` on rules 2 and 7, and opened
four defects: `tj-3jo0`, `tj-7vhq`, `tj-b8il`, `tj-zewi`.

Documentation: `docs-resolve` covered pgvector and pinned model revisions; local
code owns Treejar behavior.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`,
  and the prompt and guards consume the same immutable set. The name ask is
  state-owned: `customer_name_asked` is recorded only when an ask reaches the
  customer, and `_store_name_gate_pending_request` is the one re-elicitation
  trigger. A name in the current inbound message joins the current-message
  facts, so a first-turn signature cannot receive another name question in
  either language, Arabic shapes included (`tj-40gc`).
  `asks_the_company_activity` records the one-turn cooldown only when a signal
  sits inside a question sentence (`tj-eedk`); the broad phrase scan survives
  for suppressing the carry, which is not state.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate; unavailable, rejected, empty and `cannot_fix` fall
  back to the validated grounding repair. It notifies on failure by default.
  Its protected journal lives in the Git common dir, never the working tree.
- The paid round sends the prompt production sends, built from the product's
  own functions so a round follows them when they change. Its catalog evidence
  comes from exact local pgvector through `src.rag.pipeline.search_products`,
  pinned by a protected artifact before provider work; `FROZEN_SETS` registers
  measurable sets and `preflight --set` names one. The price anchor comes from
  the pinned snapshot through the same `anchor_line_from_catalog_rows`
  production uses, so rules 2 and 7 compare again; `preflight
  --catalog-snapshot` is required and hashed against the artifact's own catalog
  digest before any provider call.
- `consultative_opening_directive` takes `opening_states_the_offer` and the
  opening's own text, so a first turn is told what it will begin with rather
  than asked what it already said. It states the options a discovery question
  may offer -- kinds of work or space -- positively and with no prohibition,
  under the 2026-08-10 observation that this model follows an instruction and
  loses a ban. `solution_consultation_directive` carries 9 and 10 one stage on.
- `collapse_question_form` runs before the first-turn opening guard, not after,
  under its unchanged `REDUCING` contract: the guard folds the canonical name
  question on and the collapse drops every question after the first. A folded
  pair counts as one.
- `/api/v1/health` resolves the release SHA once per process and answers a
  commit SHA or `unknown`, bounded by pattern and length in the schema.
- CI job `semantic-evidence` runs the exact-pgvector producer test against a
  pgvector service on every change to `scripts/corpus_bridge/` or `src/rag/`,
  and reads the outcome so a skip cannot pass. It is not in `deploy`'s needs.
  `PinnedEmbeddingEngine` passes `local_files_only=True`, so it fetches the
  pinned BGE-M3 revision first and an empty cache fails in seconds.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`,
  7 records differing -- dialogs 28, 875 and 1291, each read and intended.
- Repair judge: 60 calls on stored 819 and 789, $0.0051, 20 of 20 delivered.
- `tj-7gpw`: every number measured before 2026-08-12, 18.94 included, was scored
  on a prompt missing the runtime directives and the ask permission list, so
  nothing before it compares. Baseline `tj-7gpw-parity-baseline-c-20260812`.
- Six rounds on the same twenty, same reader, one change each, all accepted.
  Weighted 14.6 to 18.7 of 30; raw 10.6 to 13.8. Attribution is in Beads; one
  `tj-l0e3` round is discarded as unfaithful under `tj-l0e3.2`.
- The Arabic rounds over `arabic-12` cover every Arabic opening the corpus has,
  12 of 1358 -- a population, not a sample. Weighted 9.6 to 10.6, low band 93%
  to 99%; only the band compares with the twenty's. English directives reach
  Arabic.
- `tj-z1fn` is the lesson worth keeping: quoting the canonical opening helped
  Arabic and cost English rule 7 2.00 to 1.80, and naming what the opening
  leaves uncovered -- the customer -- removed the cost. Measure both sets
  before shipping a shared directive.
- `tj-68au-round-20260813` is the first round after the anchor was restored.
  Raw 13.0 of a 13.2 mean ceiling, [12.2, 13.6]; 16 of 20 openings at their own
  ceiling; zero critical failures; 20/20 in language. Rules 1, 3, 4, 7, 8 and 9
  held at 2.00, rule 7 included, which answers what the round was for:
  returning the price anchor bought no restatement of the offer. Rule 2 fell
  2.00 to 1.90 (`tj-7vhq`, and a coffee table quoted as an office table) and
  rule 5 1.95 to 1.85, on two product-led option lists beside the dialog-28
  ceiling case. The paired raw delta against `tj-z1fn-english-paired-b` is
  -0.75 per opening, inside the 2.0 reader gap, so it stands on those shapes
  and not on any total. Its
  weighted 15.5 against 18.7 is **not** a regression: the map follows the reply,
  so three openings moved to the 9.6 band, 14/6 against 11/9.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and Mypy clean; process verification passed. Format was **not** clean at
  `167936b`: `834da77` left `scripts/corpus_bridge/real_opening_acceptance.py`
  unformatted, invisible to the repo gate because it covers `src/ tests/` only.
  Fixed in place. Pytest at `167936b` in a linked worktree: 3798 collected, 3777
  passed, 20 skipped, 1 failed, the failure being
  `test_the_protected_root_is_outside_the_working_tree`, for the worktree alone.
- The protected replay has not moved: aggregate `1b425bd1…` against the frozen
  `1fc87c04…`, the same 7 records differing on dialogs 28, 875 and 1291. It
  cannot show a SELLING-turn change -- it pins `is_first_turn=True` -- and
  `tj-68au` confirms that from the other side: rule 13 is not applicable on any
  of the frozen twenty and did not move.

## Constraints

- No PR, deploy, production/staging mutation, model-configuration change or
  real-user message is authorized or performed beyond what is recorded here.
- `tj-68au` was owner-authorized on 2026-08-13 and cost $0.006432: 20 Luna
  calls, 0 repair-judge, 0 scoring-judge, no `--second-reader`; the root read it
  blind, free. Running total $0.1972.
- Paid calls before it total $0.1908 across ten authorized rounds, of which
  $0.1627 is the single paid second reader and $0.0045 bought nothing (upstream
  429s/503, and the `tj-l0e3` round discarded under `tj-l0e3.2`). Per-round
  authorization is in Beads. `tj-ge07` is authorized and deliberately not taken.
- `https://noor.starec.ai/api/v1/health` was read once on 2026-08-13, read-only;
  nothing else on the runtime was contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change`;
  `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: not opened
Recommended action: take `tj-3jo0` at P1, the anchor family defect.

## Starter prompt for next orchestrator

Use $orchestrator-stage after selecting the next open Beads goal.

## Tracker

- 27 live issues were audited on 2026-08-13 and 17 closed with recorded reasons,
  none on a title alone; disposition is in Beads. `tj-i653`, `tj-ee5f.1` and
  `tj-ee5f.5` are deferred on state we do not own.
- `tj-jlx4` is not reader variance: the gap is 2.0 while S07 moved 6.58 with
  non-overlapping ranges, and the bead diagnoses a content choice. P2.
- `tj-final27.6` is engineering-complete, disabled safe and policy-gated, and
  waits on one written client sentence. It blocks `tj-final27.9`, hence P1.
- `tj-ee5f.1` needs real transports and production producers; `tj-ee5f.5` waits
  on the Wazzup provider fixing delivered/read callbacks, which is theirs.

## Owner decisions of 2026-08-13

- Referrals wait on the owner's own message. Do not chase, and do not read the
  missing policy as a defect.
- Rule 11: disposition 3. A discount is a manager's decision or is already in
  the catalog price, so Noor never offers one and the zero is policy; every
  score prints the 28/30 policy cap beside it. The permitted shape ships:
  verified rows as one package at the catalog price.
- The client document was decided, not asked. It leads with the Zoho deal
  export: outcomes are visible for 192 of 1400 dialogues, so we can say Noor
  does what the rubric asks, not that Noor sells. Evaluator prompt withdrawn.
- Deploy and live verification were authorized for the seven audit fixes and
  spent. `origin/main` is `167936b` and production runs `2876774`; the two
  commits between touch CI and docs only, so no deploy was due.

## Active handoff

- `tj-rcg5` implements the two-stage route: exact local pgvector retrieval
  through `src.rag.pipeline.search_products`, then a fail-closed measured
  consumer. Spec and plan are `docs/superpowers/{specs,plans}/2026-08-13-semantic-catalog-evidence-boundary*`.
- Final protected evidence uses 332 catalog rows, BGE-M3 revision
  `5617a9f61b028005a4858fdac845db406aefb181`, exact pgvector extension `0.8.5`
  and retrieval code `fe1bae6fad914a3cbdac7463b18372f0e084facb6b3a34890652682d882d1bde`.
  Golden P@3/R@3/nDCG@3 is `0.7222/0.8333/0.8333` with zero hard failures, and
  the frozen twenty has zero too. Presence of rows never creates a duty to
  quote them; only qrels-confirmed SKUs reach generation.
- The code sha moved from `05f6c8e7…` and the artifact was re-produced at
  `167936b` into `tj-68au-evidence-20260813` from the same pinned snapshot,
  qrels and revision, on a throwaway `pgvector/pgvector:pg16` with no residue;
  the body is byte-identical apart from that field. Use it, not the `tj-rcg5`
  artifact, which can no longer preflight because the `tj-rdqc` fix edited a
  file the contract hashes. `tj-zewi` decides what the contract should bind.
- Exact SKU is owned by the direct `get_stock`/catalog route, not semantic
  search: BGE-M3 input carries no SKU, so semantic qrels exclude it rather than
  mask the route boundary.

## Explicit defers

- Seven rules of fifteen cannot be charged by any rig this project has: 14 and
  15 need a tool-filled next step or a deferred decision, 6, 10 and 13 a project
  signal, 11 a two-family order, 12 a later turn. The two-turn set is kept.
- The reader gap is a number, `tj-4q79`: mean absolute 2.0 raw points per
  opening, worst 4.0, measured once against a paid reader at $0.1627. A paired
  delta under 2 points is inside reader variance, so no single round is defended
  by its total. The drift re-read is still owed. `--second-reader` adds that
  reader beside the root, never instead, and is off by owner decision.
- `tj-68au` left two candidate rule-2 cases unadopted in
  `docs/root-reading-convention.md`: the round before carried both and scored
  them 2, so adopting either later moves no delta but needs a re-read.
- Rule 5's ceiling on the frozen twenty is 1.95, not 2.00: dialog 28 is a job
  application with no furniture need and rule 5 is charged anyway, unchanged.
