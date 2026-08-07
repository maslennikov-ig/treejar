# Orchestrator Handoff

Updated: 2026-08-07
Current branch: `main`
Current stage id: `tj-swgu`
Status: epic `tj-swgu` implemented and locally green; only the release-bound
production re-run remains, and it needs authority that is not granted

## Current truth

- **Epic `tj-swgu` is implemented and its acceptance did not pass.** The
  release-bound re-run on `6a14f2f` scored **18.5/30 comparable against a 24.0
  threshold**, superseding the morning's 18.0. Report:
  `docs/reports/2026-08-07-production-acceptance-6a14f2f.md`.
- **Functional failures went from two to zero.** `tj-g51h` and `tj-v41l` are
  fixed and verified in production output.
- The thesis held where it was tested directly: S04 moved 14.6 to 22.8 on the
  per-turn consultative directive alone, and S08 moved 8.3 to 14.6 once its
  templates were retired. S03 moved 25.4 to 28.9.
- It did not hold on the action routes. The verified-prose wrap fires and the
  guard then refuses the result almost every time -- the model drops the unit
  price, the live stock or the quotation number. S06 and S10, the two scenarios
  still carrying `selection-confirmation`, did not move. Open as `tj-swgu.8`,
  and the choice it needs is a product one.
- Judge variance on this set is worth about a point per scenario either way;
  S10 lost 8.6 on unchanged behaviour. Read single-scenario deltas with that in
  mind.
- Turn provenance is now a number: 3 of 10 scenarios model-written throughout
  and 13 of 29 turns deterministic, against 2 and 15 in the morning.
  `uv run python -m scripts.e2e_acceptance.route_provenance <captures>`.
- Test data cleaned up: four draft sale orders voided with readback, the test
  contact deactivated, the CRM deal retained for audit.
- `tj-r1vk`: S09 and S10 share one conversation by design and nothing resets it
  between rounds. Both had to be re-run on reset conversations before scoring.
- Frozen scope remains `AC-01..AC-30`, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- The local remediation for reviewed findings `R-01` through `R-16`, `R-19`,
  and `R-20` is accepted after focused proof and an independent bounded
  re-review. `R-17` is the only code defer and is bounded below.
- Owner decision for `R-01`: code default
  `dialogue_kernel_mode=enforce`; keep `dialogue_kernel_enforced_flows` empty.
  Typed reconciliation/write-back now runs on the default path while replies
  stay model-owned. No stored runtime configuration was changed.
- Explicit quote refusal persists `declined` and never renders “on hold”. Quote
  detail collection requires canonical `granted` consent; malformed canonical
  state fails closed, while narrowly trusted legacy exact/sales-order quote
  state is canonicalized before adapters.
- Verified catalog facts no longer replace the answer wholesale. They drive a
  model-owned repair pass with separate text provenance. Within one turn a SKU
  exposes one Zoho-confirmed stock number or `unconfirmed`; partial plans retain
  solved families and state an exact uncovered quantity.
- Low evaluator coverage is blocking and cannot publish a normal excellent
  `/30` result. Owner reports show coverage, normalized denominators, and `н/д`
  for inapplicable blocks.
- The isolated harness can return a non-incumbent `winner`: a complete unique
  model/case/repetition matrix is required; sealed judge scores and critical
  gates are applied before durable writes; actual provider cost reconciles a
  full-payload conservative reservation; carry-forward cannot consume an
  unfinished candidate's allowance; non-finite accounting fails closed;
  `TRUNCATED` and `UNSUPPORTED` are machine-readable. Blind permutations use
  cryptographic entropy and keep the `0600` reveal outside the reviewer bundle.
- Product-runtime model-id/reasoning/cache capability cleanup from `R-17` is not
  implemented and must remain a bounded Beads/handoff defer. The harness part
  of `R-17` is implemented.
- No paid or metadata provider request, model configuration mutation, push,
  deploy, production readback, Zoho/PDF/Wazzup effect, or live message occurred
  in this round.

## Local verification

- `tj-swgu` at close, 2026-08-07: Ruff and format over 409 files, Mypy over 167
  sources, Pytest `3235 passed, 19 skipped`, and
  `scripts/orchestration/run_process_verification.sh` OK. Every child ran the
  full suite before its own commit.
- `tj-ee5f` children at their own close: `.7` 823 passed, `.8` 803, `.12` 99,
  `.14` 113, targeted Ruff/format/Mypy each; independent correction re-review
  APPROVE. That round's combined tree was `2776 passed, 19 skipped, 3 failed`,
  the three being traceability digest drift, green after the refresh. All
  superseded by the stage-close numbers below.

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

Recommended action: `tj-swgu.8`, then one more release-bound acceptance. The
remaining gap is concentrated in two routes that refuse their own rewrite, and
closing it needs an owner decision about what a customer must always be told.
`tj-ee5f.1` is the same production pass seen from the older stage. Do not fold
the bounded product-runtime `R-17` defer into either. Fix `tj-r1vk` before the
next run or S09 and S10 will be scored on a polluted conversation again.

## Stage tj-feet

Closed 2026-08-06. Grounding, tool obedience and evaluation repair; all ten
children and four follow-ups closed. Full detail in
`.codex/stages/tj-feet/summary.md` and the reports it names. What is still
live policy rather than history:

- **Owner decision 2026-08-06: a spoiled reply is worse than a model error.**
  The claim contract blocks only what a retrieved row *refutes*; what it cannot
  confirm ships and lands in `ContractResult.unverified`, logged every turn.
  This reverses the original `tj-feet.3` criterion, so an invented attribute the
  catalog is silent about reaches the customer. Turns rewritten fell to `4/42`,
  all four the capacity rule.
  `docs/reports/2026-08-06-claim-contract-gaps-closed.md`.
- Seating capacity is answerable only as a marked assumption carrying a
  confirming question; the catalog has no capacity field on any of 344 active
  SKUs and no Arabic text at all.
- The main model was switched to `openai/gpt-5.6-luna` on 2026-08-05 under
  explicit owner authority, as one `system_configs` row.
- `tj-feet.10` stays off; see the defer below.
- Run `scripts/orchestration/repin_traceability_sources.py` after moving
  current state.

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
