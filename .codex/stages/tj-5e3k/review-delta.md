# Correctness Delta Review: `tj-5e3k`

**Disposition:** `merge`

## Findings

No remaining P0, P1, or P2 findings were identified. The first review's five
findings are fixed for the current evidence and final route conclusions.

### P3 — Negation detection remains a clause-level heuristic

- **Finding:** `_contains_asserted_phrase()` treats any configured negation token
  before the forbidden phrase in the same detected clause as negating that
  phrase.
- **Evidence:** `scripts/model_battle.py:843-862` searches the whole prefix since
  the last limited boundary set. A future sentence such as “stock is not
  unconfirmed, and 20 units are available” would contain `not` in the prefix and
  could be treated as safe even though the final claim is affirmative. The
  current `sales-11` answers are genuine negations and are rescored correctly.
- **Implication:** This does not affect `tj-5e3k`, but novel benchmark wording
  could create a false negative.
- **Confidence:** High.
- **Next action:** Prefer case-specific affirmative unsafe patterns, or narrow
  negation scope to the governing verb/phrase; add a contradictory-clause
  regression test.
- **Promotion target:** Non-blocking scorer hardening before expanding the sales
  corpus.

### P3 — Existing-matrix validation does not verify each row's suite tag

- **Finding:** The separate-suite validator confirms the exact
  case/repetition/model matrix but does not require `row["suite"] == suite`.
- **Evidence:** `scripts/model_battle.py:608-642` builds `actual` only from
  `case_id`, `repetition`, and `model`. A correctly sized file whose rows carry
  the wrong suite metadata could pass this pre-merge check. The current sales
  and system evidence has correct suite tags and complete matrices.
- **Implication:** Current manifest provenance is valid, but a malformed future
  partial run could pass the new guard and later select the wrong aggregate
  branch at `scripts/model_battle.py:1484`.
- **Confidence:** High.
- **Next action:** Validate the suite tag while reading the matrix and add a
  wrong-suite regression test.
- **Promotion target:** Non-blocking harness hardening for future
  separate-suite runs.

## Delta Evidence

### Negated sales claims

- Both GLM-5.2 `sales-11` rows now have
  `forbidden_phrases["20 units are available"] = true`,
  `checks_passed = 7/7`, and `hard_gate_passed = true` in
  `sales_scored_results.jsonl`.
- The rescored GLM-5.2 objective is `87.6637%`, up from the incorrect prior
  value. Its remaining failed sales gate comes only from the fresh blind review
  showroom-trial finding.
- The report now accurately says null stock was described as unconfirmed.

### Reasoning-control evidence

- Every system row records `reasoning_requested=false` and an observed-control
  diagnostic.
- `system_scored_aggregate.json` and `route_decisions.json` report
  `reasoning_disable_honored=100%` for GLM-5.2 and both DeepSeek candidates,
  and `0%` for Nex-N2-Mini.
- The report explicitly distinguishes the disable request from observed
  compliance and states that Nex returned reasoning tokens in all 48 runs.

### Separate-suite manifest and matrix validation

- `merge_run_manifest()` now rejects noncanonical existing model lists.
- `assert_existing_run_evidence()` rejects missing files, missing matrix
  entries, extra entries, and duplicates before metadata is merged.
- The stored manifest has both suites, canonical four-candidate lists, seed
  `27072026`, two repetitions, synthetic-only evidence, and no production
  change.
- Current raw coverage remains exact: 96 sales rows and 192 system rows.

### Tool punctuation normalization

- Terminal punctuation is normalized before semantic comparison.
- Both DeepSeek V4 Pro `system-tool-03` rows now score `3/3` with no mismatch.
- V4 Pro's tool quality and
  `no_critical_tool_argument_error` gate are now `100%`/true. Its system
  semantic accuracy is `72.8155%`; it still fails the semantic and
  consistently-failing-case release gates.

### Counterbalanced fresh blind review

- The reveal key contains 24 unique case/repetition groups with A/B/C/D once
  per group.
- Each of the four sales candidates occupies each label exactly six times.
- The fresh score file contains all 24 groups, all four labels per group, all
  required rubric dimensions, and valid critical-failure reasons.
- Fresh critical counts match the report: GLM-5 zero, GLM-5.2 one, V4 Flash
  one, and V4 Pro four.

### Final route conclusions

- Recomputing rescoring, blind aggregation, candidate metrics, hard gates, and
  `select_winner()` from current raw evidence reproduced
  `route_decisions.json` exactly.
- Sales: GLM-5 is the only hard-gate-safe candidate and remains the strict
  winner at `93.975`.
- System: no candidate is a safe replacement. V4 Pro is correctly presented as
  the comparative hardening leader (`85.353`), not as an authorized production
  switch; V4 Flash remains the semantic reference (`73.7864%` versus
  `72.8155%`).
- The durable report's tables, critical counts, latency claims, control
  compliance, strict decisions, and qualified operational recommendations
  match the derived artifacts.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_scripts_model_battle.py -q -p no:cacheprovider`
  — 54 passed.
- `uv run ruff check scripts/model_battle.py tests/test_scripts_model_battle.py`
  — passed.
- `uv run ruff format --check scripts/model_battle.py tests/test_scripts_model_battle.py`
  — passed.

## Follow-ups

1. Harden forbidden-claim negation scope before adding more varied prose cases.
2. Include suite metadata in separate-run matrix validation.

Neither follow-up changes the present scores, hard gates, or route conclusions.

## Documentation and Graph Review

- `docs-reviewed: no-change-needed` — the durable report now matches the
  rescored evidence and clearly qualifies the system recommendation.
- `graph-reviewed: no-change-needed` — this is isolated benchmark and evidence
  work; Graphify is not configured and `graphify-out/GRAPH_REPORT.md` is absent.

## Resolution Review

**Disposition:** `merge`

### Findings

No remaining P0-P3 findings were identified in this narrow hardening delta.
Both P3 follow-ups from this review are resolved.

### Resolution Evidence

- **Wrong suite tags are rejected:** `assert_existing_run_evidence()` now checks
  every stored row's `suite` value before validating the
  case/repetition/model matrix (`scripts/model_battle.py:628-630`).
  `test_existing_suite_evidence_rejects_wrong_suite_tag` builds a complete
  sales-shaped matrix tagged as `system` and confirms rejection.
- **Negation scope is narrowed:** comma is now a clause boundary in
  `_contains_asserted_phrase()` (`scripts/model_battle.py:853-860`).
  The original safe sentence remains accepted by
  `test_sales_scoring_does_not_treat_negated_claim_as_asserted`, while
  `test_sales_scoring_detects_assertion_after_negated_prior_clause` confirms
  that “Stock is not unconfirmed, and 20 units are available” is rejected as an
  affirmative forbidden claim.
- **Focused coverage passes:** 56 tests passed with
  `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_scripts_model_battle.py -q -p no:cacheprovider`.
  Ruff check and format check also passed for the harness and focused test file.
- **Route conclusions are unchanged:** sales remains `winner` with
  `z-ai/glm-5` at `93.975`; system remains `no_safe_replacement`. All stored
  candidate weighted scores match the prior delta review:
  sales `86.265 / 90.276 / 93.975 / 88.539` and system
  `84.133 / 85.353 / 80.603 / 78.786` in artifact order.

### Follow-ups

None for this narrow delta.

- `docs-reviewed: no-change-needed` — no route conclusion or durable-report
  claim changed.
- `graph-reviewed: no-change-needed` — the changes remain isolated validation
  and scoring hardening.
