# Orchestrator Handoff

Updated: 2026-08-14
Current branch: `main`
Current stage id: `tj-tjgx-opening-quality`
Status: `tj-tjgx` fixed and accepted the four bounded opening defects measured
by `tj-399z`. Release gates are green at 3803 passed and 20 skipped. Production
still runs `b5ab693`; this task made no live mutation.

Documentation: `docs-resolve` covered pgvector and pinned model revisions; local
code owns Treejar behavior.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`,
  and the prompt and guards consume the same immutable set. The name ask is
  state-owned: `customer_name_asked` is recorded only when an ask reaches the
  customer, so a first-turn signature cannot be asked again in either language
  (`tj-40gc`). `asks_the_company_activity` records its one-turn cooldown only
  when the signal sits inside a question sentence (`tj-eedk`).
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate; every failure mode falls back to the validated
  grounding repair. Its journal lives in the Git common dir.
- The paid round sends the prompt production sends, built from the product's
  own functions so a round follows them when they change. Its catalog evidence
  comes from exact local pgvector through `src.rag.pipeline.search_products`,
  pinned by a protected artifact before provider work; `FROZEN_SETS` registers
  measurable sets and `preflight --set` names one. The price anchor comes from
  the pinned snapshot through the same code production uses; `preflight
  --catalog-snapshot` is required and hashed against the artifact's own catalog
  digest before any provider call.
- A row joins an anchor family only when its name and its catalog taxonomy both
  say so, and joins one -- the first, so a workstation chair is a chair
  (`tj-3jo0`). The database path reads rows and calls that same pure function
  instead of running `MIN(price)` per family in SQL, where the name was all it
  could see. The anchor is withheld on a first turn whose message positively
  says it is about something else -- a job application, a dispatch notice, a
  cold pitch -- and a named piece of furniture wins it back (`tj-7vhq`); silence
  still earns it. Arabic joins its clauses with `،` (`tj-b8il`).
- `consultative_opening_directive` treats the canonical offer as complete,
  ties any later product category to the customer's job, accounts for every
  distinct need before discovery, and uses kinds of work -- focused solo work,
  collaborative meetings, visitor reception -- instead of a desk example
  (`tj-j62b`, `tj-593w`, `tj-1orh`).
- The shared name-question detector recognises bounded “what name should I use
  for you” variants without matching named projects. The opening guard therefore
  does not append a second equivalent name ask (`tj-b8px`).
- `/api/v1/health` resolves the release SHA once per process and answers a
  commit SHA or `unknown`, bounded by pattern and length in the schema.
- CI job `semantic-evidence` runs the exact-pgvector producer test on every
  change to `scripts/corpus_bridge/` or `src/rag/` and reads the outcome, so a
  skip cannot pass. It is not in `deploy`'s needs.
- The retrieval contract binds the four source files that own retrieval plus the
  named definitions in the producer that decide what it returns, not the whole
  producer file -- binding that stranded every artifact when `tj-rdqc` added a
  validator to it. `PINNED_RETRIEVAL_CONTRACT_SHA` fails in the commit that moves
  the digest, and `stale-evidence` names what to re-produce (`tj-zewi`).

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate
  `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`, 7 records
  differing on dialogs 28, 875 and 1291, each read and intended.
- Repair judge: 60 calls on stored 819 and 789, $0.0051, 20 of 20 delivered.
  `tj-7gpw`: nothing measured before 2026-08-12, 18.94 included, compares; the
  baseline is `tj-7gpw-parity-baseline-c-20260812`.
- Six rounds on the same twenty, same reader, one change each, all accepted:
  weighted 14.6 to 18.7 of 30, raw 10.6 to 13.8, attribution in Beads, one
  `tj-l0e3` round discarded under `tj-l0e3.2`. `arabic-12` is every Arabic
  opening the corpus has, 12 of 1358; only its band compares with the twenty's.
- `tj-z1fn` is the lesson worth keeping: quoting the canonical opening helped
  Arabic and cost English rule 7 2.00 to 1.80, and naming what the opening
  leaves uncovered -- the customer -- removed it. Measure both sets first.
- `tj-68au-round-20260813` is the first round after the anchor was restored.
  Raw 13.0 of a 13.2 mean ceiling, [12.2, 13.6]; 16 of 20 at their own ceiling;
  zero critical failures; 20/20 in language. Rules 1, 3, 4, 7, 8 and 9 held at
  2.00, rule 7 included, which answers what the round was for: the price anchor
  bought no restatement of the offer. Rule 2 fell 2.00 to 1.90 (`tj-7vhq`, and a
  coffee table quoted as an office table) and rule 5 1.95 to 1.85, on two
  product-led lists beside the dialog-28 ceiling case. The paired raw delta
  against `tj-z1fn-english-paired-b` is -0.75 per opening, inside the 2.0 reader
  gap, so it stands on those shapes and not on any total. Weighted 15.5 against
  18.7 is **not** a regression: the map follows the reply, so three openings
  moved to the 9.6 band, 14/6 against 11/9.
- `tj-399z-round-20260814` measures the four fixes. Raw 12.8 of a 13.2 mean
  ceiling, [12.2, 13.4]; 13/20 at their own ceiling; weighted 15.2; zero
  critical failures. Per rule: 1 2.00/2.00, 2 1.95/2.00, 3 2.00/2.00,
  4 1.95/2.00, 5 1.80/1.95, 7 1.95/2.00, 8 1.83/2.00 (n=6), 9 2.00/2.00
  (n=6). Against `tj-68au`, raw -0.15 and weighted -0.28, both inside the 2.0
  reader gap. Dialog 28 moved only rule 2, 1 to 2. AED 491 is credible beside
  the priced workstation rows. Rule 13 remains inapplicable on all twenty.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Focused TDD first failed in four intended cases, then passed 85/85. Ruff,
  format, Mypy and process verification pass. Full pytest is 3803 passed,
  20 skipped, 0 failed: exactly five new passing tests over the 3798/20/0
  baseline.
- Protected replay is unchanged: current `1b425bd1…` against frozen
  `1fc87c04…`, the same 7 records on dialogs 28, 875 and 1291. No re-baseline.

## Constraints

- No PR, deploy, production/staging mutation, model-configuration change or
  real-user message was made.
- `tj-tjgx` made zero paid calls; it used only local tests and stored replay.
- `tj-399z` was owner-authorized in the current session and cost $0.006473: 20
  Luna calls, zero repair-judge and scoring-judge calls, no second reader; root
  read it blind for free. Recorded paid-round total is now about $0.2037.
- `https://noor.starec.ai/api/v1/health` was read once on 2026-08-13; nothing
  else on the runtime was contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change`;
  `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: not opened
Recommended action: deploy `main` only with fresh owner authorization, then run
a new paired measured round if the owner wants product-level evidence.

## Starter prompt for next orchestrator

Use $orchestrator-stage after selecting the next open Beads goal.

## Tracker

- 27 live issues were audited on 2026-08-13 and 17 closed with recorded reasons,
  none on a title alone; disposition is in Beads. `tj-jlx4` is not reader
  variance -- the gap is 2.0 while S07 moved 6.58 with non-overlapping ranges --
  and stays open at P2.
- `tj-final27.6` is engineering-complete and waits on one written client
  sentence. It blocks `tj-final27.9`, hence P1. Deferred on state we do not own:
  `tj-i653`; `tj-ee5f.1`, needing real transports; `tj-ee5f.5`, waiting on the
  Wazzup provider's callbacks.
- `tj-j62b`, `tj-593w`, `tj-1orh` and `tj-b8px` closed under accepted parent
  `tj-tjgx`; each retains its own measured defect shape and criterion.

## Owner decisions of 2026-08-13

- Referrals wait on the owner's own message; the missing policy is not a defect.
- Rule 11: disposition 3. A discount is a manager's decision or is already in
  the catalog price, so Noor never offers one and the zero is policy; every
  score prints the 28/30 policy cap beside it.
- The client document leads with the Zoho deal export: outcomes are visible for
  192 of 1400 dialogues, so we can say Noor does what the rubric asks, not that
  Noor sells.
- Deploy was authorized for the seven audit fixes and again for the four anchor
  and contract fixes. `/api/v1/health` answers `b5ab693`, redis and database ok.

## Active handoff

- `tj-rcg5` implements the two-stage route: exact local pgvector retrieval, then
  a fail-closed measured consumer. Spec and plan are under
  `docs/superpowers/{specs,plans}/2026-08-13-semantic-catalog-evidence-boundary*`.
- Final protected evidence uses 332 catalog rows, BGE-M3 revision
  `5617a9f61b028005a4858fdac845db406aefb181`, exact pgvector extension `0.8.5`
  and retrieval code `29123d5fb9d3a8bc4dabce9585e333f5e51305e75044b47270d9b51c0c6a3da1`,
  pinned as `PINNED_RETRIEVAL_CONTRACT_SHA`. Golden P@3/R@3/nDCG@3 is
  `0.7222/0.8333/0.8333`, zero hard failures on it and on the twenty. Rows being
  present never creates a duty to quote them; only qrels-confirmed SKUs reach
  generation.
- Use `tj-zewi-evidence-20260813`. Both artifacts were re-produced there on a
  throwaway `pgvector/pgvector:pg16` with no residue, from the same pinned
  snapshot, qrels and revision; each body is byte-identical to its predecessor
  apart from `retrieval.code_sha`, and the golden numbers are unchanged, so
  narrowing the contract changed nothing retrieval does. Preflight passed
  against it end to end. `stale-evidence --root <protected>` names the seven
  superseded artifacts.
- Exact SKU is owned by the direct `get_stock`/catalog route, not semantic
  search: BGE-M3 input carries no SKU, so semantic qrels exclude it.

## Explicit defers

- Seven rules of fifteen cannot be charged by any rig this project has: 14 and
  15 need a tool-filled next step, 6, 10 and 13 a project signal, 11 a two-family
  order, 12 a later turn. The two-turn set is kept.
- The reader gap is a number, `tj-4q79`: mean absolute 2.0 raw points per
  opening, worst 4.0, measured once at $0.1627. A paired delta under 2 points is
  inside reader variance, so no round is defended by its total. The drift re-read
  is still owed. `--second-reader` is off by owner decision.
- `tj-68au` left two candidate rule-2 cases unadopted in
  `docs/root-reading-convention.md`: the round before scored both 2, so adopting
  either moves no delta but needs a re-read. Rule 5's ceiling on the twenty
  stays 1.95: dialog 28 is charged whether or not it now carries a price.
