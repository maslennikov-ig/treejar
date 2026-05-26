# Stage tj-8ma2 Summary

Status: local implementation ready on branch
`codex/tj-8ma2-sales-order-brief-resume`; not merged, pushed, deployed, or
live-E2E tested.

Scope: fix sales-order quote resume discovered during Fr3309 production E2E.
The broken path was:

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

Verification:
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
  passed after adding stage summary/artifact.

Delivery status:
- Branch: `codex/tj-8ma2-sales-order-brief-resume`.
- Base: `main@bc03a8fdb5db71744c5ce6ad18d963a3ebc24063`.
- Delivery: pending owner approval for merge/push/deploy/live E2E.

Documentation:
- docs-reviewed: updated - stage summary, artifact, and handoff record the
  behavior change and verification evidence.
- project-index: reviewed-no-change - no repository navigation, entrypoint,
  integration boundary, verification command, or ownership boundary changed.
- graph-reviewed: no-change-needed - no knowledge graph is configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual / handoff:
- Full pytest including `tests/test_admin_dashboard_frontend.py` was not run
  to avoid reinstalling `frontend/admin/node_modules` during disk cleanup work.
- `tj-nzob` remains a separate follow-up bug.
