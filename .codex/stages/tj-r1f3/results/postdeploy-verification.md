# tj-r1f3 Post-deploy Verification

**Date:** 2026-07-27  
**Final deployed release:** `b8de75c215d2678eb8d2cff06f91a49e48e0e4a9`  
**Final CI/deploy run:** `30283789902`  
**Disposition:** blocked after the second and final correction cycle

## Stable runtime evidence

- Local release gates passed twice after the relevant corrections:
  Ruff, Ruff format, Mypy over 162 source files, process verification, and
  `1624 passed, 19 skipped`.
- GitHub Actions lint, type-check, test, and deploy jobs passed for
  `b8de75c`.
- `/opt/noor/.release-sha` and `.release-run-id` match the release and run
  above.
- Runtime models remain:
  `OPENROUTER_MODEL_MAIN=z-ai/glm-5.2` and
  `OPENROUTER_MODEL_FAST=deepseek/deepseek-v4-flash`.
- App, worker, nginx, Redis, and PostgreSQL are running. Redis returned
  `PONG`; PostgreSQL accepted connections.
- Public health reported `status=ok`, Redis `ok`, and database `ok`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed `8/8`.
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

Manual review of attempt 3 also found that the missing-stock reply promised
that the team could check and get back later. The current deterministic
evaluator did not flag that delegated future-check wording, so the effective
semantic result is `3/5`, not an accepted `4/5`.

## Blocker and next boundary

Beads `tj-r1f3` remains `in_progress`. The next fix should not add another
wording-only prompt patch inside this exhausted correction loop. It should
replan the product boundary around reliable customer-output enforcement and
expand the deterministic evaluator to cover delegated future-check promises.
The fix must be isolated, verified, deployed, and freshly retested before
mutation-capable E2E acceptance task `tj-ee5f.1` can run.

`docs-reviewed: updated` — this result record preserves release truth and the
remaining execution blocker.

`graph-reviewed: no-change-needed` — Graphify is optional but not configured;
`graphify-out/GRAPH_REPORT.md` is absent, and this verification record changes
no architecture.
