# Stage tj-4xnf Summary

Status: merged, pushed, deployed, production-smoked, live-E2E verified,
cleaned, and closed in Beads.

Scope: finish the exact quotation Inventory customer fallback gap. A previous
partial fix in commit `e97bbb4` added duplicate-name recovery, but fresh
`tj-8ma2` production E2E showed a remaining failure: sales-order quote resume
reached `create_quotation(items=[CH 620 grey x5])`, then
`resolve_inventory_customer_id` failed after Zoho Inventory `create_contact`
returned HTTP 400.

Root cause:
- The live synthetic conversation phone was
  `+79262810921#tj-8ma2-salesorder-mixed-20260526-200552`.
- Inventory lookup used all digits from the suffix, producing queries such as
  `+792628109218220260526200552` and `phone_contains=0526200552`.
- Contact creation also received the synthetic suffix in the phone/mobile
  payload, which can make Zoho reject the request before duplicate-name
  fallback helps.
- Wazzup outbound delivery already strips synthetic suffixes; Inventory contact
  resolution needed the same boundary behavior.

Current decision:
- Strip the repo-owned synthetic `#...` suffix only at the external Zoho
  Inventory contact boundary.
- Keep the full suffixed phone inside app conversation storage so live E2E
  isolation still works.
- Preserve exact quote fail-closed behavior when customer resolution still
  cannot find or create a valid Inventory contact.

Verification:
- RED:
  `uv run --extra dev python -m pytest tests/test_llm_quotation.py -q -k 'synthetic_suffix_for_zoho or duplicate_name_conflict'`
  failed because `find_customer_by_phone` received the full suffixed phone.
- GREEN:
  the same command passed after implementation: `2 passed`.
- `uv run --extra dev python -m pytest tests/test_llm_quotation.py tests/integrations/test_zoho_inventory.py -q`
  passed: `20 passed`.
- `uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'quote_customer_details or customer_details_resume or exact_quote or sales_order_resolved_followup_then_brief_creates_quote'`
  passed: `46 passed, 174 deselected`.
- `uv run --extra dev ruff check src/ tests/`: passed.
- `uv run --extra dev ruff format --check src/ tests/`: initially failed on
  the new test; after `uv run --extra dev ruff format tests/test_llm_quotation.py`,
  format check passed.
- `uv run --extra dev mypy src/`: passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-4xnf`: passed
  with full suite `1181 passed, 19 skipped`, process verification, artifact
  validation, project-index review, documentation review, and debt marker scan.
- GitHub Actions run `26497377622`: passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`.
- Runtime readback: `/opt/noor/.release-sha` =
  `fba5df0a7c79e334b39ec4bd2dafa0cf4d6a2308`; `/opt/noor/.release-run-id` =
  `26497377622`.
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` ->
  `8 passed, 0 failed`.
- Live E2E on approved test number `+79262810921` with suffix
  `tj-4xnf-clean-20260527-073550` passed:
  - first-turn name gate asked for name and accepted `Lilia`;
  - `sales order 5 x CH 620` asked to confirm exact catalog item;
  - `5 x CH 620 grey` preserved `CH 620 grey x5` and asked for customer details;
  - `Lilia / LLD / Lfdsf@kfsl.ru / 2 street` created quotation `Fr3316` and
    Zoho sale order `378603000022228007`;
  - readback showed `quote_customer_details.company=LLD`,
    `quotation_decision_status=pending`, and `pending_escalations=0`.
- Wazzup echo showed PDF caption `Your Treejar quotation: Fr3316` delivered to
  base chat `79262810921`, confirming the synthetic suffix was stripped at the
  outbound provider boundary too.

Prior-work check:
- `tj-4xnf`: not already fully solved. Commit `e97bbb4` is present in `main`
  and covers duplicate-name fallback, but the current live failure was a
  synthetic phone suffix leak into Zoho contact lookup/create.
- `tj-nzob`: not solved. Runtime check showed
  `_extract_ordered_unlabeled_quote_brief('Lilia, LLD, Lfdsf@kfsl.ru, 2 street')`
  returns `None`, while terse parsing stores only
  `name/email/address` and misses `company=LLD`.

Documentation:
- docs-reviewed: updated - stage summary, artifact, and handoff record the
  remaining root cause, local fix, verification, and separate `tj-nzob` defer.
- project-index: reviewed-no-change - no repository navigation, entrypoint,
  integration boundary, verification command, or ownership boundary changed.
- graph-reviewed: no-change-needed - no knowledge graph is configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual / handoff:
- Two synthetic `tj-4xnf` production conversations from this run were closed:
  acceptance conversation `4c2156c6-1763-435e-aa3d-7965631a96f3` and polluted
  smoke-marker attempt `9d8d700f-682a-4db4-9d9d-742455907935`. Cleanup readback:
  `not_closed=0`, `pending_escalations=0`.
- Local feature branch `codex/tj-4xnf-zoho-customer-fallback` was deleted after
  successful merge, deploy, and live E2E.
- `tj-4xnf` is closed in Beads as delivered and accepted.
- `tj-nzob` remains a separate quote-brief parser bug.
