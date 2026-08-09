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
  network fault. It is Postgres in the `noor-db-1` container on `noor-server`,
  reached as `db:5432` over the compose network.
- **No real customer has ever written Russian.** Of 69 real-phone conversations
  **0** carry Cyrillic, 6 Arabic; all 28 Cyrillic messages are our own harness.
  The 95% ceiling is near 4.3%: "no evidence", not "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is load-bearing.**
  7 of 920 SKUs begin with Cyrillic `СН`; 132 names use Cyrillic `х` as the
  dimension separator. `tests/test_catalog_homoglyphs.py` guards the maps that
  let Latin `CH 135` reach SKU `СН 135`.
- **The main model is Luna, and all three layers now say so**: `system_configs`,
  `src/core/config.py` and the production `.env`. For three days only the row
  did, while the source said `z-ai/glm-5.2` -- shadowed. `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance is a blind Claude reader
  panel, never a paid model; an external judge belongs only to runtime
  `ai_quality_controls`. Compare within one instrument only.
- **The acceptance figure is two figures, and 24.0 is retired.** At `ac36265`,
  two reads per packet across six readers: **project 19.95 +/- 0.93 over 11.0
  applicable rules, transactional 20.77 +/- 4.41 over 7.6**. The fork made rules
  6, 10 and 13 inapplicable to an ordinary order and the arithmetic normalises
  what remains back to /30, so two conversations scored a perfect 30 over the
  eight easy rules alone. `score_by_shape.py` refuses to print one number.
  Reader disagreement fell 2.86 -> **1.96** at 13 packets each. **The rubric is
  frozen**: five changes in one week, all raising the number, the last with no
  build change at all -- nothing before 2026-08-09 is comparable. `tj-07bs`.
- **Rules die on their own escape clauses, and four did.** **A condition on the
  world is a guard; a condition on what Noor thinks she already did is a leak**,
  since she is both actor and judge. Four removed 2026-08-08, five tests hold
  them out. `tj-2m5m.8`.
- **The model is not over-constrained, measured.** Directives are a quarter of
  the prompt and repeated runs differ at 0.34 character similarity.
- **The prompt carries the business's own goal** -- understand the need and
  quote in the shortest time -- plus jobs-to-be-done, SNAP and four facts before
  quoting, with a ban on naming any method to the customer. SPIN, Challenger,
  MEDDIC and Sandler stay out. Grew the frozen prompt on an explicit owner
  decision. Two research reports in `docs/Research/`.
- **`6a14f2f` and `5656c82` tie; per-scenario deltas from one generation a side
  are not evidence.** `docs/reports/2026-08-08-did-the-build-regress.md`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0. The price is k runs per scenario per side;
  measured within-scenario sd is about 1.7.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down when the
  customer signs their opening message; rule 11 needs a two-family order; an
  always-on directive forbids a reply that adds nothing; the consultative opening
  carries rules 9, 10 and a verified package -- never a discount.
  `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **Production runs `0c4dd32`** (2026-08-09, readback matched, health ok).
- **The model reads what the customer said; code owns catalog facts.** Owner
  call after three parser failures in one day. `record_customer_requirements`
  writes quantity, budget, deadline, sign-off and company activity into typed
  slots, bounded, with a catalog check on the SKU so a mis-extraction cannot
  become a fact. The kernel keeps state and delegates the question rather than
  answering it first. Prices went the other way: invented USD ranges are gone
  and budget questions are answered from catalog rows in AED. `tj-1osj`,
  `tj-o29r`.
- **`tj-r1vk` is closed**: the runner resets the shared S09/S10 conversation
  through the product's own service before each.
- **No figure published 2026-08-07 was real**: double-normalised. `tj-swgu.13`.
- **The rule.** No movement smaller than its own uncertainty is evidence.
- **The test was partly wrong, and not the bot's fault.** Against 74 real
  openings: 34% are a bare greeting where none of ours is, median 53 chars
  against our 126, real median 2 customer turns. Owner decision 2026-08-09:
  S01-S10 frozen as a regression set with no threshold, a realistic set
  (`R01`-`R05`) built to the measured shape, and the target moves to it. That
  set found two defects on its first run. `tj-2m5m.10`, `tj-6f4z`.
- **glm-5.2 adopted for the runtime judge on its sd**: 1.3 against
  deepseek-v4-flash's 3.8. The argument is independence.
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

Ordered plan and rules of engagement:
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`.
Earlier accepted artifacts remain under `docs/superpowers/`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- The product system prompt grew on 2026-08-09 by explicit owner decision; it
  does not grow again without one.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.

## Next recommended

Next stage id: `tj-ee5f`

The ordered plan lives in
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`.
Recommended action: `tj-ja1v` is the spine -- deterministic template routes
score far below model-written turns, and every finding of 2026-08-09 was an
instance of it. Start with `tj-jxv7`, which is small and carries a named
hypothesis to check first.

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
`.codex/orchestrator.toml`, this handoff, and then
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`,
which carries the ordered plan, the two baselines and seven rules of engagement.

The spine is `tj-ja1v`: deterministic template routes score far below
model-written turns, and the name-gate fix showed the shape of the answer --
keep the guarantee, let it carry what a salesperson carries.

Two things must not happen. Do not ship a rubric change and a build change in
the same measured round; five rubric changes in one week moved the number
without the bot moving, and nothing before 2026-08-09 is comparable now. Do not
compare one conversation shape with another or with a pre-fork figure --
`scripts/e2e_acceptance/score_by_shape.py` refuses to print a single number for
that reason.

Read two transcripts by eye every round: every finding that mattered came from
reading, not from a score. Preserve frozen `AC-01..AC-30`.

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
