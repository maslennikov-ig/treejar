# Release Review: tj-j13d

**Date:** 2026-07-27
**Scope:** model switch, grounding contract/capabilities, OpenRouter request
controls, bounded smoke harness, and pre-deploy rollback readiness
**Decision:** `fix`

## Findings

### P1 — A live V4 Flash helper route does not disable reasoning

- **Classification:** must-fix; product/runtime defect
- **Evidence:** `src/llm/fact_extractor.py:223-259` selects
  `settings.openrouter_model_fast`, then builds and passes a local
  `model_settings` containing only `max_tokens` and `timeout`. It never calls
  `model_settings_for_path()`. The new reasoning control is only added by
  `src/llm/safety.py:242-257` and therefore does not reach this request.
  `tests/test_llm_safety.py:84-106` proves the shared helper, but no test
  covers the fact-extractor request settings.
- **Impact:** ambiguous customer-fact extraction runs on the newly selected
  `deepseek/deepseek-v4-flash` without the accepted
  `reasoning.enabled=false` control. The release would not satisfy “every
  default fast/helper route” and may change latency, cost, or structured-output
  behavior on a live sales path.
- **Suggested fix:** route the fact extractor through the shared safety
  settings (prefer a dedicated registered path, or merge the generated
  OpenRouter `extra_body` into its existing limits) and add an invariant test
  that inspects the settings passed to its `OpenAIChatModel`/agent run.
- **Expected value:** makes the provider control complete across all default
  V4 Flash consumers and prevents future helper routes from silently bypassing
  it.
- **Tradeoff:** a small safety-policy registration/merge change and one focused
  test; no new provider call is required for the code fix.
- **Confidence:** high.

### P1 — Grounding smoke can report success for explicitly unsafe answers

- **Classification:** must-fix; harness-only release-verification defect
- **Evidence:** `scripts/verify_model_routes.py:269-347` relies on a few
  required/forbidden substrings. Focused local probes returned
  `{"passed": true}` for all of these:
  - showroom: `You cannot visit our showroom.`
  - samples: `Samples cannot be arranged depending on your project requirements.`
  - stock: `Stock is unconfirmed, but we definitely have AX-E1 ready to ship.`
  - medical: `No medical evidence is available, but this chair is great for back pain.`

  The current tests at `tests/test_scripts_verify_model_routes.py:57-139` do
  not cover negated allowed capabilities or semantically equivalent unsafe
  claims. In addition, `scripts/verify_model_routes.py:517-526` persists only
  pass/fail metadata, not the synthetic decision/reply, and
  `.codex/stages/tj-j13d/results/local-model-route-smoke.json:24-70` therefore
  cannot be independently audited.
- **Impact:** the accepted pre/post-deploy grounding gate can be green while
  the model denies an allowed capability or invents stock/health claims. The
  existing “5/5 passed” evidence does not establish grounding correctness, so
  it is not sufficient release evidence.
- **Suggested fix:** add case-specific rejection coverage for negated allowed
  actions and broader unsafe stock/medical commitments; persist the sanitized
  synthetic `decision` and `reply` (or an equally auditable normalized result)
  in evidence; add regression tests for the four probes above; then rerun the
  bounded provider smoke to replace the current result.
- **Expected value:** converts the smoke from provider-availability evidence
  into a credible grounding gate and makes its result reviewable without
  provider access.
- **Tradeoff:** stricter lexical guards may introduce false negatives for novel
  safe phrasing; keep checks case-bounded and retain the actual synthetic reply
  for human review.
- **Confidence:** high.

### P1 — Exact rollback state has not yet been captured

- **Classification:** must-fix; operational release gate, not a product-code
  defect
- **Evidence:** the only file currently under
  `.codex/stages/tj-j13d/results/` is the local model smoke. The stage artifact
  still records verification and changed files as pending at
  `.codex/stages/tj-j13d/artifacts/tj-j13d.md:74-80`. The handoff identifies
  production release `292d82c...`, but there is no protected evidence of the
  exact current production values of both model variables or of the required
  pre-mutation `.env` backup.
- **Impact:** updating production now would not meet the approved rollback
  contract; restoring the exact prior routing could depend on assumptions
  rather than captured state.
- **Suggested fix:** immediately before any production mutation, capture the
  exact deployed release and both current protected model values, back up the
  protected `.env` with restrictive permissions, and record a redacted
  rollback manifest/path. Do not expose values in Git or logs. After deploy,
  retain both release and environment restore commands/checks.
- **Expected value:** makes rollback deterministic and satisfies the accepted
  stop/restore boundary.
- **Tradeoff:** a small amount of deployment preparation and protected
  operational storage.
- **Confidence:** high for the repository evidence currently available.

## Conformance / Delta Evidence

- **Prompt immutability:** meets the scoped design.
  `src/llm/prompts.py:253-279` fetches DB-overridable base, communication, and
  stage components, then appends the non-DB `EVIDENCE_GROUNDING_POLICY`.
  `tests/test_llm_prompts.py:132-174` proves single inclusion and ordering after
  all three overrides. The same `sales_agent` dynamic system-prompt hook is
  used by core chat and follow-up runs (`src/llm/engine.py:8663-8671`,
  `src/services/followup.py:1039-1046`).
- **Capability semantics:** meet the accepted registry modes in
  `src/llm/communication_policy.py:19-82`: showroom `direct`, samples
  `conditional`, stock/price/quote/order `tool_required`, and
  discount/exceptional terms `manager_required`. The generated prompt preserves
  unknown-versus-unavailable and medical/certification evidence boundaries.
- **Provider request controls:** correct for consumers using
  `model_settings_for_path()` and isolated to the exact OpenRouter V4 Flash
  model (`src/llm/safety.py:242-300`); incomplete because of the fact-extractor
  bypass in Finding 1.
- **Smoke safety:** bounded to one catalog GET plus five completion attempts,
  has no retry loop or business-system integration, checks exact configured
  model IDs, and redacts common credentials. Call bounding and side-effect
  scope meet the design; semantic pass/fail confidence does not (Finding 2).
- **Local checks run by this review:**
  - focused Pytest: `87 passed`;
  - focused Ruff: passed;
  - focused Ruff format check: passed;
  - `git diff --check`: passed.
- **Reused stage evidence supplied to the reviewer:** full Pytest
  `1601 passed, 19 skipped`; Mypy passed; focused canonical lint passed; current
  provider smoke recorded `5/5`. The provider smoke must be regenerated after
  Finding 2 because its current semantic verdict is not auditable.
- Broad `scripts/` lint findings were reported as unrelated pre-existing
  orchestration-script debt and are not classified as product defects here.

## Remaining Follow-ups

- Track `scripts/verify_model_routes.py`,
  `tests/test_scripts_verify_model_routes.py`, and the regenerated sanitized
  result in the exact release commit; they are currently untracked.
- After both code/harness fixes, rerun focused tests and the bounded provider
  smoke, then perform a short delta review.
- Before deployment, satisfy Finding 3. After deployment, perform the accepted
  release/model readback, container/dependency/public-health checks, and bounded
  no-message production smoke; rollback on any blocking result.
- Update the stage artifact/summary/handoff during closeout so they no longer
  state that implementation and verification are pending.

## Documentation Review

- `docs-reviewed: no-change-needed` for README/product documentation: the
  approved design and implementation plan already document the durable model,
  grounding, safety, and rollback contracts, while README contains no model
  identities.
- Stage operational documentation still requires the normal closeout updates
  listed above.
- `graph-reviewed: no-change-needed` — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

## Release Recommendation

**NO-GO for production deployment.** Fix Findings 1 and 2, regenerate the
bounded provider evidence, and complete the protected rollback capture in
Finding 3 before mutating production. With those gates green, the remaining
model defaults, prompt immutability, capability semantics, call bounding, and
redaction controls support a conditional release.

## Resolution Review

**Date:** 2026-07-27
**Scope:** delta review of the three P1 findings
**Decision:** `conditional-go`

### Remaining P0–P2 Findings

- No remaining product-code or smoke-harness P0–P2 finding.
- The operational rollback P1 remains open only as a mandatory pre-mutation
  deployment gate: the snapshot must be created and verified before either
  production model value or the deployed release is changed.

### Finding Disposition

1. **V4 Flash reasoning control — resolved.**
   `src/llm/safety.py:32,114-123` registers `PATH_FACT_EXTRACTION` with the
   unchanged limits: `max_tokens=700`, `timeout=30s`,
   `request_limit=1`, `output_tokens_limit=700`, and
   `total_tokens_limit=3000`. `src/llm/fact_extractor.py:227-258` now obtains
   both model settings and usage limits from that central policy. A fresh local
   probe confirmed `reasoning={"enabled": false}` alongside those exact limits.

2. **Grounding smoke false positives/auditability — resolved.**
   `scripts/verify_model_routes.py:278-399` now rejects negated showroom/sample
   capabilities, unsupported fulfillment commitments, and asserted medical
   benefits while retaining clause-aware safe negations.
   `scripts/verify_model_routes.py:402-426,587-605` stores only the bounded
   synthetic `observed_decision` and sanitized `reply`; it does not retain the
   raw provider response. Fresh local probes rejected all four original
   contradictory examples and accepted safe negated showroom, stock, and
   medical answers.

   The regenerated
   `.codex/stages/tj-j13d/results/local-model-route-smoke.json:24-84` is
   credible for this bounded gate: all five calls passed, the four grounding
   replies and decisions are directly auditable and match their evidence
   boundaries, the structured V4 Flash call records reasoning disabled, and
   the report contains no raw provider payload.

3. **Rollback readiness — still requires protected runtime evidence.**
   Before production mutation, capture and verify:
   - the exact currently deployed release/commit read back from production;
   - the exact current protected values of `OPENROUTER_MODEL_MAIN` and
     `OPENROUTER_MODEL_FAST`, without printing or committing them;
   - a timestamped backup of the protected production `.env`, its validated
     path, restrictive ownership/mode (at least `600`), and a checksum or
     equivalent integrity proof;
   - a redacted rollback manifest tying that release and backup to the restore
     procedure for both the prior release and both prior model values.

### Fresh Delta Verification

- Focused Pytest:
  `tests/test_llm_safety.py tests/test_scripts_verify_model_routes.py tests/test_fact_extractor.py`
  — `73 passed`.
- Focused Ruff — passed.
- Focused Ruff format check — passed.
- Four contradictory-answer probes — all rejected.
- Three safe-negation probes — all accepted.
- No provider or production call was made by this resolution review.

### Updated Release Recommendation

**GO to create and verify the protected rollback snapshot. NO-GO for any
production mutation until the four rollback evidence items above are
confirmed.** Once that gate is recorded, there is no remaining reviewed P0–P2
blocker to proceeding with the authorized canonical deployment and bounded
post-deploy checks.
