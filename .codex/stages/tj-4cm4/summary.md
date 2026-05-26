# Stage tj-4cm4 Summary

Status: merged, pushed, deployed, production-smoked, live E2E accepted, and
synthetic conversation cleaned up.

Scope: fix exact quotation SKU clarification resume discovered during Fr3309
production E2E. The broken production path asked for `5 x CH 620`, received
`The exact SKU is CH 620 grey, quantity 5.`, then still asked for item(s) and
quantity and stored `address=quantity 5`.

Current decisions:
- Pending exact quote clarification replies are parsed before terse quote-detail
  extraction, so `quantity 5` is not treated as a delivery address.
- The fix is limited to `source=exact_quote` unresolved selections; existing
  sales-order unresolved follow-up behavior remains on its separate path.
- A single unresolved exact quote item can be resolved from either a full phrase
  like `The exact SKU is CH 620 grey, quantity 5.` or a SKU-like item reply.
- Once resolved, the normal quote resume path either creates the quotation when
  required details are present or stores the resolved item and asks only for
  missing quote details.

Verification:
- RED regression failed before implementation with
  `mock-model|quote-resume-missing-items`.
- Targeted regression passed after implementation.
- Related exact quote / sales-order resume tests passed: `4 passed`.
- `tests/test_llm_engine.py`: `219 passed`.
- `uv run --extra dev ruff check src/ tests/`: passed.
- `uv run --extra dev ruff format --check src/ tests/`: passed.
- `uv run --extra dev mypy src/`: passed.
- Full `pytest tests/ -q` reached the suite end but failed only in
  `tests/test_admin_dashboard_frontend.py` because `frontend/admin/node_modules`
  is absent and Node cannot import `esbuild`.
- `pytest tests/ -q --ignore=tests/test_admin_dashboard_frontend.py` passed:
  `1168 passed, 19 skipped`.
- After temporary `npm ci --prefix frontend/admin`, full stage closeout passed
  with full pytest: `1179 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh --stage tj-4cm4`: passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-4cm4`: passed.
- GitHub Actions CI run `26460815449`: passed, including deploy.
- Production runtime readback: `/opt/noor/.release-sha` =
  `77f96f3a483b201a70c969177b8203585f6b5682`,
  `/opt/noor/.release-run-id` = `26460815449`.
- Production smoke: `uv run python scripts/verify_api.py --base-url
  https://noor.starec.ai` -> `8 passed, 0 failed`.
- Approved production E2E on 2026-05-26:
  - phone suffix:
    `+79262810921#tj-4cm4-live-20260526-193430`.
  - conversation:
    `e895e4ed-6c11-448c-906f-d606d65db614`.
  - first message `Hi, I need a quotation for 5 x CH 620.` returned
    `name-gate`.
  - name reply `Victor` restored the pending exact quote and returned
    `z-ai/glm-5|exact-quote-clarify-item`.
  - clarification `The exact SKU is CH 620 grey, quantity 5.` returned
    `z-ai/glm-5|quote-resume-missing-details`, asking only for company/address/email.
  - synthetic details
    `Victor Test / TJ Test LLC / tj4cm4-live@example.com / Dubai test street 2`
    returned `z-ai/glm-5|quote-resume` and created `Quotation Fr3314`.
  - protected readback showed `quote_customer_details.address =
    Dubai test street 2`, `company = TJ Test LLC`, `email =
    tj4cm4-live@example.com`, and `quotation_quote_number = Fr3314`.
  - cleanup closed the synthetic conversation; exact suffix query returned
    `total=1`, `non_closed_or_escalated=0`.

Delivery status:
- Branch: merged from `codex/tj-4cm4-exact-sku-resume` into `main`.
- Base: `main@57e4bd303494c5d822dcdfc4b8381a62cbf0ead8`.
- Delivery commit: `main@77f96f3a483b201a70c969177b8203585f6b5682`.
- Local feature branch was deleted after merge and successful deploy.
- Live WhatsApp E2E passed after explicit user approval.
- Beads `tj-4cm4` is closed with the production E2E close reason.

Documentation:
- docs-reviewed: updated - stage summary, artifact, and handoff were updated
  with the behavior change and verification evidence.
- project-index: reviewed-no-change - no repository navigation, entrypoint,
  integration boundary, verification command, or ownership boundary changed.
- graph-reviewed: no-change-needed - no knowledge graph is configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual / handoff:
- `tj-8ma2` and `tj-nzob` remain separate follow-up bugs.
