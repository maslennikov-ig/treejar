# Orchestrator Handoff

Updated: 2026-08-08
Current branch: `main`
Current stage id: `tj-4e5j`
Status: epic `tj-4e5j` is complete and locally green. Epic `tj-swgu` still has
its release-bound production re-run outstanding, which needs authority that is
not granted.

## Current truth

- **Production is not on Supabase.** Project `vlxgzhbtnwysaqonvlte` is INACTIVE,
  which is why DNS, the pooler, REST and the MCP failed at once and looked like a
  network fault. Production is Postgres in the `noor-db-1` container on
  `noor-server`, reached as `db:5432` over the compose network.
- **No real customer has ever written Russian.** Of 69 real-phone conversations
  **0** carry Cyrillic, 6 Arabic; all 28 Cyrillic messages are our own harness.
  The 95% ceiling is near 4.3%: "no evidence", not "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is load-bearing.**
  7 of 920 SKUs begin with Cyrillic `СН`; 132 names use Cyrillic `х` as the
  dimension separator. The homoglyph maps let a customer typing Latin `CH 135`
  reach SKU `СН 135`; `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so**: `system_configs`,
  `src/core/config.py` and the production `.env`. For three days only the row
  did, while the source said `z-ai/glm-5.2` -- shadowed. `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance is a blind Claude reader
  panel, never a paid model; an external judge belongs only to runtime
  `ai_quality_controls`. Compare within one instrument only.
- **Acceptance on `a830001` was 15.9 against a 14.3 baseline, delta +1.6 +/- 1.9
  -- inside noise once rules 13 and 15 are corrected on both sides.** 52 blind
  scorings, S01-S08 three times each. The panel disagreed with itself by 2.86
  against its own earlier 0.9, probably from 26 packets each (`tj-2m5m.9`);
  generation noise is smaller at 0.84. Gap to 24.0 is 8.1.
  `docs/reports/2026-08-08-the-first-run-that-saw-the-directives.md`.
- **Rules die on their own escape clauses, and four did.** The value proposition
  and the company question appear 0 times in all 26 transcripts of the live run;
  not a deploy gap, not an early return, not the tool layer, all checked.
  **A condition on the world is a guard; a condition on what Noor thinks she
  already did is a leak**, since she is both actor and judge. Removed 2026-08-08:
  "if you have not already said it" (rule 7 -- `opening_guard.py` puts the
  greeting in the same reply); "at most one question ... leave it for the next
  turn" (starved rule 13 forever); "you do not know what their company does" (a
  name is not a line of work); "whose **whole content** is a restatement" (why
  S08 survived). Five tests hold them out; all unmeasured. `tj-2m5m.8`.
- **The model is not over-constrained, measured.** Directives are 2 353 chars
  against a 6 929-char base prompt, and repeated runs of one scenario differ at
  0.34 character similarity; the least repetitive scenario scores highest.
- **The prompt now carries the business's own goal** -- understand the need and
  quote in the shortest time -- plus three named methods (jobs-to-be-done, SNAP,
  four facts before quoting) and a ban on naming any of them to the customer.
  SPIN, Challenger, MEDDIC and Sandler stay out: built for long cycles, highest
  theatre risk. Eight manual turns on the deployed build showed no methodology
  narration at all. This grew the frozen product prompt, on an explicit owner
  decision.
- **`6a14f2f` and `5656c82` tie; per-scenario deltas from one generation a side
  are not evidence.** `docs/reports/2026-08-08-did-the-build-regress.md`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0 -- a bot that always writes the same sentence stops
  selling. The price is k runs per scenario per side.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down when the
  customer signs their opening message; rule 11 needs a two-family order; an
  always-on directive forbids a reply that adds nothing; the consultative opening
  carries rules 9, 10 and a verified package -- never a discount.
  `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **Production runs `0c4dd32`** (2026-08-09, readback matched, health ok).
- **The model reads what the customer said; code owns catalog facts.** Owner
  call after three parser failures in one day. `record_customer_requirements` is
  the first tool that records rather than acts: it writes quantity, budget,
  deadline, sign-off and company activity into typed slots, bounded, with a
  catalog check on the SKU so a mis-extraction cannot become a fact. The kernel
  no longer answers "please confirm the quantity" itself -- it kept beating the
  model to the message -- it keeps state and delegates. Verified live: "10
  chairs. CH 616 NEW black" now reaches a quotation offer with the slot reading
  quantity 10. Prices went the other way: Noor answered "what is a normal
  budget" with invented USD ranges, and now answers it from catalog rows in AED.
  `tj-1osj`, `tj-o29r`.
- **`tj-r1vk` is closed.** The runner resets the shared S09/S10 conversation
  through the product's own service before each; nothing is deleted.
- **No figure published 2026-08-07 was real**: double-normalised, so
  18.0/18.5/18.2 were really 15.8/16.1/16.1. `tj-swgu.13`.
- **The rule.** No movement smaller than its own uncertainty is evidence.
- **The test is partly wrong, and it is not the bot's fault.** Against 74 real
  openings: 34% are a bare greeting, 12% exceed 100 chars; 80% of ours do and
  none is a greeting. Length is fine (real median 2 customer turns). The rubric
  is a manager's scorecard for a full sales call, and S06 answers its customer
  perfectly for 7.35 of 30. Owner decision 2026-08-09: freeze S01-S10 as a
  regression set, build a realistic set, and move the 24.0 target to it; rules
  the customer explicitly forbade become n/a. `tj-2m5m.10`, `.11`.
- **glm-5.2 adopted for the runtime judge on its sd**: 1.3 against
  deepseek-v4-flash's 3.8. Cost argues the other way; the argument is
  independence, since Luna writes the replies. See that report.
- **`ai_quality_controls` names `deepseek/deepseek-v4-flash`**, all three scopes
  `disabled`. Pointing it at glm-5.2 and enabling `bot_qa` is a separate,
  unrequested change.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`; refuses a verdict
  without repeats.

## Local verification

- 2026-08-08 at `bf7b920` plus the escape-clause fixes: Ruff and format over 347
  files, Mypy over 167 sources, Pytest `3341 passed, 19 skipped`,
  `run_process_verification.sh` OK. Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12` and `.14` are
  closed; `.7` and `.8` stay open only for their release-bound acceptance.
  `.13`: future paid isolated core/background comparison, depends on `.7`, `.8`,
  `.12`, `.14`. `.1`: later winner-only release-bound acceptance. `.5`: blocked
  on the provider-confirmed Wazzup status bug.

Accepted design and executable plan, in `docs/superpowers/`:
`specs|plans/2026-08-07-model-written-prose-over-verified-facts*` and
`specs|plans/2026-08-03-noor-e2e-remediation-and-model-comparison*`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- Do not grow the product system prompt; the local change reduced it.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- The local fixes are not production acceptance; the failed S01-S10 evidence
  stays immutable until a new authorized release-bound pass exists.

## Next recommended

Next stage id: `tj-ee5f`

Recommended action: epic `tj-2m5m`. Four escape clauses are removed and
untested. Before the next run, settle `tj-2m5m.10` and `.11` -- the scenarios
and the rubric are both wrong in ways that change what the number means -- then
split the reader load (`tj-2m5m.9`), or a two-point move stays invisible. Read
two transcripts by eye every round: both findings that mattered this week came
from reading, not from the number. `tj-ee5f.1` is the same production pass seen
from the older stage; do not fold the bounded `R-17` defer into it.

## Stage tj-feet

Closed 2026-08-06. Capacity-as-marked-assumption, the `gpt-5.6-luna` switch and
`tj-feet.10` staying off are all in `.codex/stages/tj-feet/summary.md`. One
decision is live policy and is recorded nowhere else:

- **Owner decision 2026-08-06: a spoiled reply is worse than a model error.**
  The claim contract blocks only what a retrieved row *refutes*; what it cannot
  confirm ships and lands in `ContractResult.unverified`, logged every turn.
  This reverses the original `tj-feet.3` criterion, so an invented attribute the
  catalog is silent about reaches the customer. Turns rewritten fell to `4/42`,
  all four the capacity rule.
  `docs/reports/2026-08-06-claim-contract-gaps-closed.md`.

Run `repin_traceability_sources.py` after moving current state.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, the stage summary and manifest, the
accepted remediation artifacts, and Beads `.1`, `.5`, `.7`, `.8`, `.13`,
`.13.9`, `.14`. Preserve frozen `AC-01..AC-30`. A challenger decision does not
authorize a model-config change.

## Approval gates

Push, deploy and one acceptance run were granted on 2026-08-08 and spent; all
are closed again. No authority is currently granted for paid OpenRouter calls,
model configuration changes, push, deploy, production mutation, test-only
business effects, or real-user messaging. An acceptance run is live traffic and
needs its own grant each time.

## Explicit defers

- Rule 11 was settled on 2026-08-08: the owner declined a discount, so the
  directive offers a package of verified rows at their combined total instead,
  and the rubric charges the rule only on a two-family order. No directive
  written since `tj-swgu.14` has met a live conversation; every effect claimed
  for them is a headroom estimate until a deploy and a repeated run.
- `tj-swgu` has no stage scaffold: `.codex/stages/tj-swgu/` does not exist and
  `workspace.current_stage_id` is still `tj-feet`, so `check_stage_ready.py` and
  `run_stage_closeout.py` both refuse the stage. Whoever closes `tj-swgu` has to
  scaffold it first, which means writing another stream's manifest and ledger.
- Correcting the superseded 18.0/18.5/18.2 figures quoted outside this handoff
  is `tj-swgu.13`, with `tj-swgu.12`. Sealed rounds are superseded, never
  rewritten.
- Registering `repin_traceability_sources.py` in the `AGENTS.md` Operational
  State inventory. Tried and reverted: `AGENTS.md` is pinned as `repo-contract`
  in the same frozen registry, so one added line breaks three manifest tests.
- `tj-feet.10` stays off: the owner's condition was the confirming round backing
  the projection, and it measured `12/42` turns rewritten against a projected
  `1/37`. Option (b), a structured main output removing the second call, is
  unbuilt and still the more attractive of the two.
- `codex/tj-feet` and `codex/tj-ee5f-quality-model-battle` both edit this
  handoff; the other stream's edits are uncommitted in its own worktree.
- `tj-ee5f.13.9` / product-runtime `R-17`: validate and centralize model ids,
  reasoning capabilities and cache-control support in `config.py` and
  `safety.py`. Separate from `.14`, which must not be read as implying it.
- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected
  `sent -> delivered -> read` proof.
- S09 and S10 ran once, not three times: repeating them multiplies real business
  effects (a PDF to the test chat, a CRM opportunity) nobody has authorised.
- Existing raw production/model evidence stays protected outside Git, and
  repository-history privacy cleanup is a separate destructive decision.
