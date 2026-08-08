# Orchestrator Handoff

Updated: 2026-08-08
Current branch: `main`
Current stage id: `tj-4e5j`
Status: epic `tj-4e5j` is complete and locally green. Epic `tj-swgu` still has
its release-bound production re-run outstanding, which needs authority that is
not granted.

## Current truth

- **Production is not on Supabase.** The project `vlxgzhbtnwysaqonvlte` is
  INACTIVE, which is why DNS, the pooler, REST and the MCP failed at once and
  looked like a network fault. Production is Postgres in the `noor-db-1`
  container on `noor-server` (ssh config entry), reached as `db:5432` over the
  compose network, so no laptop-reachable URL exists. `.env.noor` and the dead
  `supabase` MCP server were removed 2026-08-08.
- **No real customer has ever written Russian.** Counted 2026-08-08 over the
  production database: 435 conversations, 2099 customer messages. Split by
  whether the conversation carries a real phone or a synthetic test id --
  real customers 69 conversations, **0** with Cyrillic, 6 with Arabic; test
  traffic 366 conversations, 15 with Cyrillic. All 28 Cyrillic messages are our
  own harness. Honest bound: 0 of 69 puts the 95% ceiling near 4.3%, so the claim
  is "no evidence", not "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is load-bearing.**
  7 of 920 SKUs begin with Cyrillic `СН`; 132 names use Cyrillic `х` as the
  dimension separator. The homoglyph maps in `src/llm/engine.py` and
  `src/dialogue/catalog_refs.py` are what let a customer typing Latin `CH 135`
  reach SKU `СН 135`. Removed during this epic on the reasoning above, restored
  once the catalogue was measured; `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so.** `system_configs`,
  `src/core/config.py` and the production `.env` all name `openai/gpt-5.6-luna`
  as of 2026-08-08. For three days only the database row did, while the source
  said `z-ai/glm-5.2` -- shadowed, so nothing misbehaved and every reader was
  misled. `tj-uidf`.
- **glm-5.2 adopted as judge, on its sd.** k=5 on the ten stored `5656c82`
  transcripts, 2026-08-08: pooled sd **1.3**, mean **11.2/30 +/- 0.4**. Incumbent
  deepseek-v4-flash 3.8; five blind Claude readers 0.9. Cost argues the other way
  and is not the reason. Against the panel, both repeating: 12.3 -> 11.2, delta
  -1.1 +/- 0.5 -- judges differing, not builds. See
  `docs/reports/2026-08-08-glm52-as-judge-at-k5.md`.
- **The acceptance mean is 11.2/30 +/- 0.4**, so the gap to the 24.0 threshold is
  12.8 points -- not 7.9, nor the 5.8 the double-normalised reports claimed.
- **`ai_quality_controls` names `deepseek/deepseek-v4-flash`** in production, all
  three scopes `disabled`, moved off the delisted `xiaomi/mimo-v2-flash` on
  2026-08-08. Pointing the row at glm-5.2 and enabling `bot_qa` is a separate,
  unrequested change.
- **Cost is not the argument for glm-5.2.** Per evaluation at the
  `PATH_QUALITY_FINAL` ceiling: deepseek-v4-flash $0.0045, Luna $0.0064,
  glm-5.2 $0.0114, Opus $0.2800. glm-5.2 is dearer than the model it would judge.
  The argument is independence: Luna writes the customer-facing replies, and a
  judge sharing a model with the thing it grades is measuring itself.
- **Every mean published on 2026-08-07 was normalised twice.** `808b07d` moved
  the /30 normalisation into `calculate_weighted_score` on 2026-08-03 and the
  reports kept the old manual 30/24 on top. The real figures are `c977b07` 15.8,
  `6a14f2f` 16.1, `5656c82` **16.1** -- not 18.0, 18.5, 18.2. The gap to the 24.0
  threshold is 7.9 points, not 5.8. `tj-swgu.13` (P1).- **Standing figure: 12.3 +/- 0.3** at 95%, from five independent blind readers
  over the same ten transcripts, same criteria and applicability map, product's
  own weighting: 50 scorings, df 40, pooled sd 0.9, per-reader means 13.2, 12.0,
  12.2, 11.8, 12.3. The deployed judge reads the same transcripts at 16.1 with
  sd 3.8, so its mean would carry +/- 3.3 -- the panel is about four times
  quieter. That is precision, not accuracy: the five share a model family and a
  prompt, so a shared bias is invisible and the -3.8 gap says nothing about who
  is right. The fifteen criteria remain the customer's.
  `docs/reports/2026-08-07-repeated-scoring-and-the-second-reader.md`.- **The rule.** No movement smaller than its own uncertainty is evidence about
  code, and the bound is the instrument's: +/- 3.3 for the deployed judge at one
  pass, +/- 0.3 for the panel. Two judges do not share a noise estimate, so
  neither lends its repeats to the other.- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`, 22 tests. Reads
  either score-file shape onto one /30 axis, states the interval its repeats
  justify, compares two runs paired, and refuses a verdict without repeats.
## Local verification

- `tj-swgu.9`, 2026-08-07: Ruff and format over 411 files, Mypy over 167
  sources, Pytest `3259 passed, 19 skipped`, and
  `scripts/orchestration/run_process_verification.sh` OK. Earlier per-stage and
  per-child figures are superseded by this one.

## Active work

- Review children `R-01..R-16`, `R-19`, and `R-20` are closed. `tj-ee5f.12`
  and `.14` are closed; parent `.7` and `.8` remain open only because their
  acceptance also requires a separately authorized release-bound production
  retest.
- `tj-ee5f.13`: future paid isolated core/background comparison; depends on
  `.7`, `.8`, `.12`, and `.14`.
- `tj-ee5f.1`: later winner-only release-bound production acceptance.
- `tj-ee5f.5`: blocked on the provider-confirmed Wazzup terminal-status bug.

Accepted design and executable plan:

- `docs/superpowers/specs/2026-08-07-model-written-prose-over-verified-facts-design.md`
- `docs/superpowers/plans/2026-08-07-model-written-prose-over-verified-facts.md`
- `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`
- `docs/superpowers/plans/2026-08-03-noor-e2e-remediation-and-model-comparison.md`

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- Do not grow the product system prompt; the local change reduced it.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- The local fixes are not production acceptance; the failed S01-S10 evidence
  stays immutable until a new authorized release-bound pass exists.

## Next recommended

Next stage id: `tj-ee5f`

The paid comparison has since run under `tj-feet.8` and the main model was
switched, so the battle this section used to point at is done.

Recommended action: `tj-swgu.11` and `tj-r1vk`, independent of each other and of
the repeat run, then `tj-swgu.10`. `.11` is confirmed by two independent readers
agreeing on the same S06 zeros, which is an applicability defect rather than a
judge one. `.10` has a free lever recorded on it: `PATH_QUALITY_FINAL` passes no
temperature at all, so the judge runs at the provider default while the
harness's own bounded judge refuses anything but 0.

`tj-ee5f.1` is the same production pass seen from the older stage. Do not fold
the bounded product-runtime `R-17` defer into either. Fix `tj-r1vk` before the
next run or S09 and S10 will be scored on a polluted conversation again.

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

Run `scripts/orchestration/repin_traceability_sources.py` after moving current
state.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, the stage summary and manifest, the
accepted remediation artifacts, the model-comparison specification, and Beads
`.1`, `.5`, `.7`, `.8`, `.13`, `.13.9`, and `.14`. Preserve frozen
`AC-01..AC-30`. Ask separately before any paid OpenRouter call, model-config
change, push, deploy, production readback, external side effect, or live
message.

A later task may run the free exact-provider metadata preflight. It must request
exact current authority before the bounded paid battle. A challenger decision
does not authorize a model-config change. Push, deploy, production readback,
Zoho/PDF/Wazzup actions, and live messages remain separate authority gates.

## Approval gates

No authority is currently granted for paid OpenRouter calls, model
configuration changes, push, deploy, staging/production mutation or readback,
test-only business effects, or real-user messaging.

## Explicit defers

- `tj-swgu.14` is one slice of four. Rules 6, 7 and 13 have a directive; rule
  11 does not and is still zero in ten of ten. An incentive is a commercial
  commitment nobody has authorised and the sibling comparison directive forbids
  one outright, so the honest form of rule 11 is a verified bundle rather than
  a discount. That is an owner decision, not a prompt change.
- The `tj-swgu.14` directive has never met a live conversation. Its effect is a
  headroom estimate, not a measurement, until a run produces new transcripts.
- `tj-swgu` has no stage scaffold: `.codex/stages/tj-swgu/` does not exist and
  `workspace.current_stage_id` is still `tj-feet`, so `check_stage_ready.py` and
  `run_stage_closeout.py` both refuse the stage. Pre-existing, and left alone
  here: creating it means writing another stream's manifest and ledger. Whoever
  closes `tj-swgu` has to scaffold it first.
- Correcting the superseded 18.0/18.5/18.2 figures where they are quoted
  outside this handoff is `tj-swgu.13`, and belongs with `tj-swgu.12`. Sealed
  rounds are superseded, never rewritten.
- Registering `repin_traceability_sources.py` in the `AGENTS.md` Operational
  State inventory. Tried and reverted: `AGENTS.md` is pinned as `repo-contract`
  in the same frozen registry, so a one-line addition breaks three manifest
  tests and needs a deliberate re-pin of another stream's provenance. Owned by
  `tj-ee5f`, with the design question behind it.
- `tj-feet.10` stays off. The owner approved enabling it conditional on the
  confirming round backing the projection; the round measured `12/42` turns
  still rewritten against a projected `1/37`, so the condition was not met and
  the switch was not touched. Option (b), a structured main output removing the
  second call, was not built and is still the more attractive of the two.
- `codex/tj-feet` and `codex/tj-ee5f-quality-model-battle` both edit
  `.codex/handoff.md`; the other stream's edits are uncommitted in its own
  worktree and will need reconciling at merge.
- `tj-ee5f.13.9` / product-runtime `R-17`: validate and centralize model ids,
  reasoning capabilities, and cache-control support in `src/core/config.py` and
  `src/llm/safety.py`. Harness capability evidence is complete; product-runtime
  cleanup is separate and must not be implied by `.14`.
- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected
  `sent -> delivered -> read` proof.
- Paid comparison, model configuration, push, deploy, production readback, and
  winner-only S01-S10 acceptance are future authority boundaries.
- Existing raw production/model evidence remains protected outside Git.
- Repository-history privacy cleanup remains a separate destructive decision.
