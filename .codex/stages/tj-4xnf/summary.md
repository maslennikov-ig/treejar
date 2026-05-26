# Stage tj-4xnf Summary

Status: local implementation ready on branch
`codex/tj-4xnf-zoho-customer-fallback`; not merged, pushed, deployed, or
live-E2E tested.

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
- Delivery, deploy, and live WhatsApp E2E still require explicit owner approval.
- `tj-nzob` remains a separate quote-brief parser bug.
