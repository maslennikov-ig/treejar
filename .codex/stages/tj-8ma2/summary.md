# Stage tj-8ma2 Summary

Status: closed, delivered to `main`, deployed, production-smoked, and live-E2E
triaged.

Scope: fix the sales-order quote resume bug discovered during Fr3309 production
E2E. The broken path was:

1. customer accepted a product offer and asked to prepare a quotation;
2. bot asked for exact item/quantity;
3. customer replied `5 x CH 620 grey`;
4. bot asked for company/address/email;
5. customer sent quote details `Lilia / LLD / Lfdsf@kfsl.ru / 2 street`;
6. bot reinterpreted those details as unresolved item text
   `5 x Lilia LLD Lfdsf@kfsl.ru 2 street`.

Current decisions:
- When a pending `sales_order_quote` unresolved item is resolved, store the
  resolved items back into `pending_quote_selection` before calling
  `create_quotation`.
- If `create_quotation` cannot create the quotation yet because customer PDF
  details are missing, the next details reply resumes from the resolved item
  selection instead of the old unresolved item.
- If `create_quotation` succeeds, the existing cleanup still clears
  `pending_quote_selection`.
- The same persistence step is applied to both initial fully resolved
  sales-order quote requests and resolved sales-order follow-up requests.

Delivery:
- Fix commit: `80e6f4371da44f163406f76f30f858e94d35da4a`.
- Branch `codex/tj-8ma2-sales-order-brief-resume` was fast-forwarded into
  `main`, pushed to `origin/main`, and deleted locally after merge.
- GitHub Actions run `26462939020` succeeded, including deploy.
- Production runtime readback:
  `/opt/noor/.release-sha=80e6f4371da44f163406f76f30f858e94d35da4a` and
  `/opt/noor/.release-run-id=26462939020`.
- Production smoke passed:
  `/api/v1/health` returned healthy Redis state and
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed with `8 passed, 0 failed`.

Local verification:
- RED regression:
  `uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k sales_order_resolved_followup_then_brief_creates_quote`
  failed before implementation because `pending_quote_selection` still had
  `items=[]` and unresolved `CH 620 grey` after the resolved follow-up.
- GREEN regression:
  the same command passed after implementation.
- Related targeted tests:
  `uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k "sales_order_unresolved or sales_order_resolved_followup_then_brief_creates_quote or customer_details_resume_pending_quote_selection or unlabeled_quote_brief_completes_pdf_details or exact_quote_unresolved_followup_resolves_sku_and_quantity"`
  passed: `7 passed`.
- `uv run --extra dev python -m pytest tests/test_llm_engine.py -q` passed:
  `220 passed`.
- `uv run --extra dev ruff check src/ tests/`: passed.
- `uv run --extra dev ruff format --check src/ tests/`: passed.
- `uv run --extra dev mypy src/`: passed.
- `uv run --extra dev python -m pytest tests/ -q --ignore=tests/test_admin_dashboard_frontend.py`
  passed: `1169 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh --stage tj-8ma2`:
  passed before delivery.
- Final stage closeout after documentation cleanup:
  `scripts/orchestration/run_stage_closeout.py --stage tj-8ma2` passed. The
  first closeout attempt failed only because `frontend/admin/node_modules` was
  absent and Node could not import `esbuild`; after temporary
  `npm ci --prefix frontend/admin`, closeout passed with ruff, format check,
  mypy, full pytest `1180 passed, 19 skipped`, process verification, and stage
  readiness. Local Node emitted the expected engine warning because v24.15.0 is
  outside the project range `>=22.12.0 <23`.

Production E2E:
- Approved test number: `+79262810921`, using synthetic `tj-8ma2-*` suffixes.
- Exact quote route check created `Quotation Fr3315` in conversation
  `d8a82c9a-99fb-4823-aca4-d0ab360c67d0`; this verified the general quote
  path but was not the target sales-order path.
- Target sales-order E2E conversation
  `bdee58ee-8b56-414e-96bc-55de1b659a77` proved the `tj-8ma2` acceptance:
  after `sales order 5 x CH 620` and `5 x CH 620 grey`, the bot stored
  `pending_quote_selection.source=sales_order_quote`,
  `items=[{"sku": "CH 620 grey", "quantity": 5}]`, and
  `unresolved_items=[]`.
- After multiline details `Lilia / LLD / Lfdsf@kfsl.ru / 2 street`,
  production stored `quote_customer_details` with
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, and
  `address=2 street`.
- The bot did not reinterpret the customer brief as an unresolved product item.

Out-of-scope production finding:
- Quotation finalization in the target sales-order path then fell back because
  Zoho Inventory `create_contact` returned HTTP 400 after phone/email lookup did
  not find a customer. The fallback created a manager escalation with the exact
  quote fail-closed message.
- This is separate from the `tj-8ma2` state-preservation bug and is tracked in
  existing Bead `tj-4xnf`, now updated with the new evidence and priority `1`.

Cleanup:
- Four synthetic `tj-8ma2` production conversations were closed.
- Two pending synthetic escalations were marked resolved.
- Cleanup readback: `remaining_active=0`,
  `remaining_pending_escalations=0`.
- Safe merged local branches were deleted:
  `codex/tj-8ma2-sales-order-brief-resume` and
  `codex/tj-final27-artifact-normalization`.
- Temporary local dependencies and caches created for verification were removed
  after closeout: `.venv`, `frontend/admin/node_modules`, `.pytest_cache`,
  `.mypy_cache`, `.ruff_cache`, `tmp`, and `__pycache__` directories.

Beads:
- `tj-8ma2`: closed as delivered and accepted.
- `tj-mmj8`: closed as delivered and accepted; it was previously waiting only
  on explicit owner closure approval.
- `tj-4xnf`: open, priority `1`, with the new Zoho Inventory HTTP 400 evidence.

Documentation:
- docs-reviewed: updated - stage summary, production E2E artifact, local
  implementation artifact, and handoff now reflect merge, push, deploy, live
  E2E, cleanup, Beads closure, and residual follow-up state.
- project-index: reviewed-no-change - no repository navigation, entrypoint,
  integration boundary, verification command, or ownership boundary changed.
- graph-reviewed: no-change-needed - no knowledge graph is configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual / handoff:
- `tj-4xnf`: exact quotation customer resolution can still fail closed when
  Zoho Inventory `create_contact` returns HTTP 400 that duplicate-name fallback
  does not recover from.
- `tj-nzob`: comma-separated ordered quote brief stores name/email/address but
  misses company; slash and multiline formats are already covered.
