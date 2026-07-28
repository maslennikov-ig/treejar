# Stage tj-r1f3 Summary

Updated: 2026-07-28
Status: accepted; Beads `tj-r1f3` closed
Runtime release: `0dd9615a16fdf4eb17abe156551c53fb77f39c21`
Runtime CI/deploy: `30330683062`
Final harness commit: `ac552023a647656777734f2109e0a93b8fa453d8`
Final harness CI: `30331481790`

## Boundary

The stage closes Noor's bounded factual-grounding gaps for unsupported
specific-product showroom trials, unverified stock confirmation, and direct or
delegated future stock checks. The production customer-output path now
classifies and repairs or fails closed before frame/media capture and customer
delivery. The synthetic model-route evaluator shares the production
classifiers and uses the same immutable final prompt-tail assembly.

No broad factual-claim engine, prompt redesign, extra model retry, customer
message, Wazzup/Zoho/CRM action, quotation, order, payment, or database
mutation was added.

## Evidence and defect chain

- Attempts 1–4 remain immutable failed evidence under
  `.codex/stages/tj-r1f3/results/`.
- Attempt 4 ran against exact runtime release `0dd9615` after healthy
  release/model/service/API readback. It consumed exactly five paid synthetic
  OpenRouter calls with zero retries and returned 4/5.
- The exact failed medical reply was recognized and safely repaired by the
  deployed production guard. Diagnosis isolated a smoke-harness mismatch: case
  evidence and a tool instruction followed the immutable grounding policy,
  unlike the production final-tail invariant.
- TDD aligned the harness with
  `finalize_evidence_grounding_prompt()`. Independent delta re-review returned
  `APPROVE` with no remaining P0-P3 findings.
- Harness-only commit `ac55202` passed CI; deploy was correctly skipped because
  runtime product sources and configuration were unchanged.
- A new separately quota-bound attempt 5 streamed the exact committed harness
  through stdin to the existing runtime interpreter. It consumed exactly five
  paid synthetic calls, made zero retries, performed no business mutation, and
  passed deterministic plus manual semantic review 5/5.

Exact evidence:

- `.codex/stages/tj-r1f3/results/postdeploy-smoke-attempt-4.json`
- `.codex/stages/tj-r1f3/results/postdeploy-smoke-attempt-5.json`
- `.codex/stages/tj-r1f3/results/postdeploy-verification.md`
- `.codex/stages/tj-r1f3/artifacts/tj-r1f3-implementation.md`
- `.superpowers/sdd/tj-r1f3-implementation-report.md`

## Verification

- Prompt-tail RED failed because the synthetic prompt did not end with the
  immutable grounding policy; GREEN passed after using the runtime finalizer.
- Exact attempt-4 production-path characterization classified
  `specific_product_showroom_trial`, repaired the response, and reclassified it
  with no violation.
- Focused prompt/grounding slice: `185 passed`.
- Full local gate: `1878 passed, 19 skipped`.
- Ruff passed; Ruff format passed with 306 files; Mypy passed over 163 source
  files; process verification passed.
- GitHub Actions run `30331481790`: lint, type-check, and tests passed.
- Final readback: app, worker, nginx, Redis, and PostgreSQL running; Redis
  `PONG`; PostgreSQL accepting connections; health/Redis/database `ok`; API
  guards returned their expected status codes; `.env` mode `600`.
- Final routes: `z-ai/glm-5.2` and `deepseek/deepseek-v4-flash`.
- Canonical stage closeout passed: 102 targeted tests, 133 integration tests,
  38 E2E tests, process verification, artifact validation, stage readiness,
  documentation checks, project-index review, and debt scan.

## Closeout

- Beads `tj-r1f3` is closed with the exact runtime, harness, quota, and
  attempt-5 acceptance evidence.
- `tj-ee5f.1` is no longer blocked by `tj-r1f3`.
- docs-reviewed: updated — stage summary, implementation artifact, SDD report,
  and postdeploy evidence record the full failed/fixed/retested chain.
- project-index: reviewed-no-change — no stable runtime entrypoint, route,
  integration boundary, or ownership boundary changed.
- graph-reviewed: no-change-needed — Graphify is not configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual risk is limited to unseen paraphrases and mixed-language variants
outside this bounded grammar. The fail-closed production boundary limits the
customer-visible impact of recognized forms.
