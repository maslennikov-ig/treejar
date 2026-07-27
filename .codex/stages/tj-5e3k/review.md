# Correctness Review: `tj-5e3k`

**Disposition:** `fix`

## Findings

### P1 — The report and deterministic sales gate misread explicit negation as an availability claim

- **Finding:** The forbidden-phrase scorer uses plain substring matching, so
  “can't guarantee 20 units are available” is classified as asserting that 20
  units are available.
- **Evidence:** `scripts/model_battle.py:531-533` checks whether each forbidden
  phrase is absent from normalized text, without considering negation.
  Both `z-ai/glm-5.2` `sales-11` rows in
  `.codex/stages/tj-5e3k/results/sales_scored_results.jsonl` explicitly say
  stock is unconfirmed and that the model cannot guarantee availability, yet
  `forbidden_phrases["20 units are available"]` is false and
  `hard_gate_passed` is false. The report consequently claims at
  `docs/reports/model-battle-glm52-v4pro-2026-07-27.md:50-53` that GLM-5.2
  “twice asserted that 20 units were available,” which the raw answers
  contradict.
- **Implication:** GLM-5.2's deterministic correctness, weighted score, and one
  hard gate are understated, and the durable report contains a false factual
  claim. The sales winner remains GLM-5 because GLM-5.2 independently has a
  blinded critical failure, but the accepted evidence must not preserve this
  misclassification.
- **Confidence:** High.
- **Next action:** Make forbidden claims negation-aware (or use case-specific
  affirmative unsafe patterns), add a regression test using the two actual
  sentence forms, rescore the existing raw sales rows, and update the report
  and derived decisions without new inference.
- **Promotion target:** Blocking fix before `tj-5e3k` stage acceptance.

### P1 — The claimed reasoning-disabled system profile was not honored for Nex

- **Finding:** The harness requested `reasoning.enabled=false`, but every Nex
  system response contains reasoning tokens; the report states without
  qualification that system reasoning was disabled for all candidates.
- **Evidence:** `scripts/model_battle.py:691-707` builds the common control and
  the system runner passes `reasoning_enabled=False`. In
  `.codex/stages/tj-5e3k/results/system_results.jsonl`, all 48
  `nex-agi/nex-n2-mini` rows report positive
  `usage.completion_tokens_details.reasoning_tokens` (14,709 total), while the
  other three candidates report zero. Nine Nex responses finished with
  `finish_reason="length"` and several consumed the entire 900-token allowance
  as reasoning without a usable answer. This conflicts with the method claim
  at `docs/reports/model-battle-glm52-v4pro-2026-07-27.md:26-30`.
- **Implication:** The common request was sent, but the effective execution
  profile was asymmetric. Nex's schema, semantic, and latency results are still
  useful as end-to-end evidence that the requested production control was not
  respected; they must not be described as results with reasoning actually
  disabled. The current recommendation against Nex remains directionally
  supported, but its failure mode is misattributed.
- **Confidence:** High.
- **Next action:** Update the report to distinguish “reasoning disable
  requested” from “reasoning disable honored,” quantify the Nex reasoning and
  length outcomes, and treat control noncompliance as provider/model behavior.
  Add an evidence-validation test or scoring diagnostic that detects reasoning
  tokens when the profile requests none.
- **Promotion target:** Blocking report/method correction before stage
  acceptance; rerun only if the owner requires a genuinely
  reasoning-disabled Nex comparison.

### P2 — Separate-suite manifest merging can certify incompatible earlier evidence

- **Finding:** `merge_run_manifest()` validates seed, repetitions, profile, and
  safety flags, but does not validate the existing manifest's `models` mapping
  or the existing suite result matrix before replacing metadata with the
  canonical profile.
- **Evidence:** `scripts/model_battle.py:315-365` never inspects
  `existing["models"]`. The new reverse-order test in
  `tests/test_scripts_model_battle.py:84-124` deliberately supplies
  `"models": {"system": []}` and expects the merge to succeed.
- **Implication:** A partial run with missing or wrong candidates could later be
  presented as a complete canonical profile after the second suite merges its
  manifest. The current `tj-5e3k` evidence itself is complete (96 sales and 192
  system rows with the expected four candidates), so this is a workflow bug,
  not evidence that the present manifest is false.
- **Confidence:** High.
- **Next action:** Require exact canonical model metadata for every previously
  recorded suite and validate existing JSONL case/model/repetition coverage
  before merging. Change the reverse-order test to reject the empty model list.
- **Promotion target:** Harness fix before promoting separate-suite execution
  as reusable evidence infrastructure.

### P2 — A punctuation-only tool-summary difference is treated as a critical tool error

- **Finding:** Every tool-field mismatch makes
  `no_critical_tool_argument_error` fail, even when the mismatch is not
  operationally critical.
- **Evidence:** `scripts/model_battle.py:1409-1428` defines the hard gate as
  `tool_quality == 1.0`. DeepSeek V4 Pro's only failing tool case is
  `system-tool-03` in both repetitions: the expected summary is
  `Customer requests 15% discount`, while the actual value only adds a trailing
  period. `route_decisions.json` therefore marks
  `no_critical_tool_argument_error=false`.
- **Implication:** The hard-gate name and decision semantics overstate harmless
  formatting differences as critical argument failures. V4 Pro still fails the
  semantic and consistent-case gates, so the system disposition does not
  change, but the hard-gate evidence is misleading.
- **Confidence:** High.
- **Next action:** Mark critical tool fields explicitly (tool name, SKU,
  quantity, reason code, company) or normalize inconsequential punctuation in
  free-text summaries; keep exact mismatch in the quality score without
  automatically elevating it to a critical gate.
- **Promotion target:** Scoring/report correction before accepting the hard-gate
  interpretation.

### P2 — A/B/C/D assignment is anonymous but not counterbalanced

- **Finding:** Per-group random shuffling produces materially uneven label
  exposure across the 24 review groups.
- **Evidence:** `scripts/model_battle.py:368-389` independently shuffles each
  group. In the stored reveal key, per-model label counts range from 3 to 9:
  V4 Flash is A/B/C/D = 9/7/5/3, V4 Pro = 6/4/8/6, GLM-5 =
  4/9/5/6, and GLM-5.2 = 5/4/6/9.
- **Implication:** Model identity is hidden correctly, but position/order bias
  is not controlled. This is especially relevant because critical failures are
  hard gates. The cited critical reasons are grounded in raw answers, so there
  is no evidence that the winner changed, but the method is weaker than a
  balanced multi-label design.
- **Confidence:** Medium.
- **Next action:** Use a deterministic Latin-square/cyclic assignment across
  groups, and test near-equal label counts for each candidate.
- **Promotion target:** Follow-up benchmark-method improvement; document as a
  limitation if the existing blind review is retained.

## Delta Evidence

- The extended profile is correct in `scripts/model_battle.py:30-49`: four
  sales candidates and four system candidates, with the intended route-specific
  baselines.
- Raw evidence coverage is complete:
  - sales: 96 rows, 12 cases, two repetitions, 24 rows per candidate;
  - system: 192 rows, 24 cases, two repetitions, 48 rows per candidate.
- Multi-label blinding is structurally complete: 24 unique case/repetition
  groups, each with A/B/C/D answers, scores, and reveal entries. All four sales
  models appear once in every group.
- The weighted formulas and hard-gate-first winner logic are connected through
  `score_battle()` (`scripts/model_battle.py:1185-1228`) and
  `candidate_metrics_from_evidence()` (`:1331-1461`). `select_winner()` correctly
  ignores unsafe candidates and supports more than two candidates.
- `route_decisions.json`, both aggregate files, and the report tables agree on
  weighted scores, objective/semantic rates, reliability, p50/p95 values,
  category rates, and the strict decisions, except for the GLM-5.2 negation
  interpretation described above.
- The current merged manifest correctly records seed `27072026`, two
  repetitions, both suites, the extended profile, canonical candidate lists,
  synthetic-only evidence, and no production change.
- Provider evidence redaction is effective for the stored data: seven
  sensitive-key occurrences (`user_id`) were found and every value is
  `[REDACTED]`; no unredacted `api_key`, `authorization`, or `user_id` value was
  found. Generation IDs and provider names remain as intended diagnostic
  evidence.
- Focused verification:
  - `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_scripts_model_battle.py -q -p no:cacheprovider`
    — 47 passed.
  - `uv run ruff check scripts/model_battle.py tests/test_scripts_model_battle.py`
    — passed.
  - `uv run ruff format --check scripts/model_battle.py tests/test_scripts_model_battle.py`
    — passed.

## Follow-ups

1. Fix and rescore the negated sales claim; correct the durable report.
2. Correct the report's reasoning-profile statement and expose control
   noncompliance in derived evidence.
3. Harden manifest provenance validation for separately run suites.
4. Separate critical tool arguments from noncritical textual normalization.
5. Counterbalance labels in the next blind review.

## Documentation and Graph Review

- `docs-reviewed: change-needed` — the durable report contains the false
  GLM-5.2 availability claim and overstates effective reasoning disablement.
- `graph-reviewed: no-change-needed` — this stage changes an isolated benchmark,
  tests, and evidence; Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.
