# tj-r1f3 Post-deploy Verification

**Date:** 2026-07-28
**Final deployed release:** `0dd9615a16fdf4eb17abe156551c53fb77f39c21`
**Final CI/deploy run:** `30330683062`
**Disposition:** blocked after attempt 4; provider quota exhausted and smoke-harness prompt drift found

## Stable runtime evidence

- The exact release candidate passed the local release gates:
  Ruff, Ruff format, Mypy over 163 source files, process verification, and
  `1877 passed, 19 skipped`.
- GitHub Actions lint, type-check, test, and deploy jobs passed for
  `0dd9615`.
- `/opt/noor/.release-sha` and `.release-run-id` match the release and run
  above.
- Runtime models remain:
  `OPENROUTER_MODEL_MAIN=z-ai/glm-5.2` and
  `OPENROUTER_MODEL_FAST=deepseek/deepseek-v4-flash`.
- App, worker, nginx, Redis, and PostgreSQL are running. Redis returned
  `PONG`; PostgreSQL accepted connections.
- Public health reported `status=ok`, Redis `ok`, and database `ok`.
- Read-only API verification passed without webhook submission:
  health and products returned `200`, conversations and quality returned
  `403`, dashboard and admin metrics returned `401`, and the admin surface
  returned a non-error redirect.
- `.env` remained mode `600`, owned by `noor-dev:noor-dev`.

## Bounded provider evidence

All attempts used the production app container, exactly five paid synthetic
calls, no real customer data, and no Wazzup, Zoho, quotation, order, CRM, or
other business mutation.

1. `postdeploy-smoke-attempt-1.json` on release `3516fa1`: script result `3/5`.
   The evidence led to prompt and deterministic-evaluator corrections.
2. `postdeploy-smoke-attempt-2.json` on release `f996ff0`: script result `4/5`.
   GLM-5.2 paired a medical disclaimer with an offer to experience the
   specific chair in the showroom.
3. `postdeploy-smoke-attempt-3.json` on release `b8de75c`: script result `4/5`.
   GLM-5.2 again offered experiencing the specific Nova chair in the showroom
   after declining the medical claim.
4. `postdeploy-smoke-attempt-4.json` on release `0dd9615`: script result `4/5`.
   The deterministic runtime guard and shared classifier were deployed, but
   the raw synthetic medical answer again paired a correct medical refusal
   with an offer to experience the specific chair. The other four cases
   passed manual semantic review. Exactly five paid calls were made; no retry
   was performed. An earlier launcher command failed before Python started
   because the runtime image does not copy `scripts/`; it made zero provider
   calls. The exact release script was then streamed through stdin to the
   runtime interpreter without modifying production files.

Manual review of attempt 3 also found that the missing-stock reply promised
that the team could check and get back later. The evaluator deployed for
attempt 3 did not flag that delegated future-check wording, so its effective
semantic result is `3/5`, not an accepted `4/5`.

## Attempt-4 diagnosis and next boundary

Beads `tj-r1f3` remains `in_progress`. The deployed production guard recognizes
and repairs the exact attempt-4 sentence, so the customer-output boundary is
not the new defect. The smoke harness built a different prompt contract from
the production runtime: it placed the immutable grounding policy before case
evidence and a service instruction, while production guarantees exactly one
policy copy as the final prompt tail.

A focused RED test reproduced that drift. The local correction now builds the
synthetic prompt through the same `finalize_evidence_grounding_prompt()` helper;
the test is GREEN. The correction must pass its affected/release gates, be
reviewed and deployed, and receive a new separately quota-bound provider
retest. Attempt 4 remains immutable failed evidence and cannot be reclassified.
Mutation-capable E2E acceptance task `tj-ee5f.1` remains blocked until a fresh
smoke passes.

`docs-reviewed: updated` — this result record preserves release truth and the
remaining execution blocker.

`graph-reviewed: no-change-needed` — Graphify is optional but not configured;
`graphify-out/GRAPH_REPORT.md` is absent, and this verification record changes
no architecture.
