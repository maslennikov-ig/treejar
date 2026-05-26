# Stage tj-mmj8 Summary

Status: deployed to production and live Fr3309 E2E verified; Beads closure
deferred pending explicit owner approval.

Scope: fix Fr3309 PDF brief-detail loss where the tester sent
`Lilia / LLD / Lfdsf@kfsl.ru / 2 street`, but the bot failed to treat it as a
complete quote brief and later generated PDF fields from ambiguous follow-up
text.

Current production state:
- Runtime SHA: `428f360d7e8a97f936cf0eb2084d4aa6ecaf6801`.
- Runtime run id: `26441317711`.
- GitHub Actions run `26441317711`: succeeded, including deploy.
- Later orchestration-only commits on `main` did not redeploy; production
  readback still points to `428f360d7e8a97f936cf0eb2084d4aa6ecaf6801`.
- Production smoke after runtime readback:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` ->
  `7 passed, 0 failed`.

Current decisions:
- Ordered four-field quote briefs are parsed deterministically while a quote
  selection is pending: name, company or individual marker, email, address.
- High-confidence briefs such as `Lilia / LLD / Lfdsf@kfsl.ru / 2 street`
  directly populate quote metadata and continue the quote flow.
- Low-confidence ordered briefs ask for a compact confirmation instead of
  generating a PDF immediately.
- Affirmative confirmation stores a bounded internal confirmed-address marker
  for that brief so the quote can proceed without prompt expansion.
- `individual` and `individual purchase` are treated as customer type only when
  they occupy the company/customer-type slot.
- A later ambiguous individual/address reply cannot overwrite an already
  explicit company such as `LLD` unless an explicit company correction is
  supplied.
- Customer-facing quotation PDF fields prefer explicit quote metadata; an
  explicit real company beats a stale or ambiguous `customer_type=individual`
  marker.

Local verification before deploy:
- RED tests were added for multiline and slash-separated Fr3309 briefs,
  ambiguous individual/address overwrite protection, low-confidence brief
  confirmation, affirmative confirmation, and PDF context company precedence.
- Targeted Fr3309 tests failed before implementation and then passed:
  `6 passed`.
- `tests/test_llm_engine.py`: passed, `216 passed`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- First full `OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short`
  failed because `frontend/admin` dependencies were not installed in the new
  worktree (`esbuild` missing), not because of the Python change.
- After `npm ci` in `frontend/admin`, final full pytest passed:
  `1149 passed, 16 skipped`.
- `scripts/orchestration/run_process_verification.sh --stage tj-mmj8`: passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-mmj8`: passed.

Production E2E:
- Approved test number: `+79262810921`, using synthetic chat suffixes
  `tj-mmj8-fr3309-*` to isolate conversation memory.
- Slash brief passed: conversation `dac20020-f102-4ee5-8bb8-a3240537571d`,
  quotation `Fr3310`, PDF message `970a566f-9559-49f7-9b7a-28e91c6b7561`.
- Clean multiline brief passed:
  conversation `8947af78-d039-4e1c-bad3-a35a243e5bd6`, quotation `Fr3311`,
  PDF message `5d0d0211-1466-4456-bd36-c6960bf44eb7`.
- Low-confidence brief confirmation passed:
  conversation `a259f7c1-4e08-4a1e-9e10-bba8ba17fbb9`, confirmation shown,
  `yes` created quotation `Fr3312`, PDF message
  `b8aa8f1a-8b83-4a64-a592-8875de91bbdb`.
- Labeled fields passed:
  conversation `b916aee2-df6d-4b32-bd13-1b373a71d779`, quotation `Fr3313`,
  PDF message `4b10ed1a-71f6-471b-a06c-d99e810ebf6e`.
- Post-quote ambiguous `individual / dubay 2 street 7` did not overwrite
  company `LLD` in the successful slash scenario.
- Downloaded PDF text for `Fr3310`, `Fr3311`, and `Fr3313` contains:
  `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`,
  `Address: 2 street`.
- Downloaded PDF text for `Fr3312` contains the same name/company/email and
  `Address: Dubai` after explicit confirmation.
- No manager handoff or escalation was created.

Out-of-scope findings from broader E2E:
- `tj-4cm4`: exact quotation SKU clarification resume loses exact SKU/quantity.
- `tj-8ma2`: sales-order quote resume can reinterpret customer brief as an
  unresolved item.
- `tj-nzob`: comma-separated ordered brief stores name/email/address but misses
  company.

Cleanup:
- Seven synthetic production conversations matching `tj-mmj8-fr3309-*` were
  closed via the conversation API.
- Cleanup readback: `total_synthetic_fr3309=7`, `active_count=0`,
  `escalated_count=0`.

Delivery status:
- Fix commit: `428f360d7e8a97f936cf0eb2084d4aa6ecaf6801`.
- Main currently includes later orchestration-only commits, but production
  runtime remains the fix commit.
- No deploy, merge, push, GitHub mutation, or Beads closure was performed in
  this E2E-only closeout turn.

Documentation:
- project-index: reviewed-no-change - no entrypoints, routes, directories,
  integrations, verification commands, or ownership boundaries changed in this
  E2E-only turn.
- docs-reviewed: updated - stage summary, production E2E artifact, and handoff
  were updated with runtime, smoke, live E2E, cleanup, and follow-up evidence.
- graph-reviewed: no-change-needed - repo has no configured knowledge graph or
  `graphify-out/GRAPH_REPORT.md` in this worktree.

Residual / handoff:
- Core Fr3309 acceptance is verified in production and `tj-mmj8` can be closed
  once the owner explicitly authorizes closure.
- Follow-up bugs `tj-4cm4`, `tj-8ma2`, and `tj-nzob` should be handled in
  separate focused stages.
