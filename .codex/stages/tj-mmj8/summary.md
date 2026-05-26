# Stage tj-mmj8 Summary

Status: local implementation verified; deploy and live E2E deferred pending explicit authorization.

Scope: fix Fr3309 PDF brief-detail loss where the tester sent
`Lilia / LLD / Lfdsf@kfsl.ru / 2 street`, but the bot failed to treat it as a
complete quote brief and later generated PDF fields from ambiguous follow-up
text.

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

Verification:
- RED tests were added for multiline and slash-separated Fr3309 briefs,
  ambiguous individual/address overwrite protection, low-confidence brief
  confirmation, affirmative confirmation, and PDF context company precedence.
- Targeted Fr3309 tests failed before implementation and now pass:
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

Research:
- The fix follows the researched slot/state-filling pattern from Rasa slots and
  forms, Dialogflow required parameters, and Bot Framework dialog prompts:
  durable state plus validation/confirmation instead of prompt bloat.

Delivery status:
- Local branch: `codex/fr3309-brief-details`.
- Base branch/commit: `origin/main` /
  `5e2917d05866d8ba3f538ec3a33dd3ccfbd2e188`.
- No production deploy, GitHub issue mutation, or live WhatsApp send was
  performed for this stage.

Documentation:
- project-index: reviewed-no-change - no entrypoints, routes, directories,
  integrations, verification commands, or ownership boundaries changed.
- docs-reviewed: no-change-needed - behavior is internal deterministic
  quote-brief parsing and PDF metadata precedence; stable API/operator docs do
  not need changes. Stage artifacts and handoff were updated.
- graph-reviewed: no-change-needed - repo has no configured knowledge graph or
  `graphify-out/GRAPH_REPORT.md` in this worktree.

Residual / handoff:
- Deploy, production smoke, and approved live E2E replay of the Fr3309 pattern
  remain explicitly deferred until the owner authorizes those external actions.
