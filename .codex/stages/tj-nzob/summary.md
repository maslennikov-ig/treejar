# Stage tj-nzob Summary

Status: merged, pushed, deployed, production-smoked, locally cleaned, and
closed in Beads. Live WhatsApp E2E was not run.

Scope: fix the follow-up finding from `tj-mmj8` production E2E where a
comma-separated ordered quote brief
`Lilia, LLD, Lfdsf@kfsl.ru, 2 street` stored name/email/address but missed
`company=LLD`, causing the bot to ask again for company or individual status.

Current decision:
- Keep the existing ordered unlabeled quote brief path as the source of truth
  for deterministic four-field briefs.
- Accept comma-only ordered briefs only when splitting on the first three
  commas yields four parts and at least one part contains an email address.
- Reuse the existing ordered mapping: name, company or individual marker,
  email, address.
- Preserve slash, multiline, and labeled behavior; ordinary comma text without
  the high-confidence shape continues to fall through to existing parsing.

Verification:
- RED:
  `uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'unlabeled_quote_brief_completes_pdf_details'`
  failed for `Lilia, LLD, Lfdsf@kfsl.ru, 2 street` with
  `mock-model|quote-resume-missing-details`.
- GREEN:
  the same command passed after implementation: `3 passed, 218 deselected`.
- Direct parser readback:
  `_extract_ordered_unlabeled_quote_brief('Lilia, LLD, Lfdsf@kfsl.ru, 2 street')`
  returns `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`,
  `address=2 street`, `needs_confirmation=False`.
- Relevant quote/customer-detail slice:
  `uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'quote_customer_details or customer_details_resume or exact_quote or sales_order_resolved_followup_then_brief_creates_quote or unlabeled_quote_brief'`
  passed: `49 passed, 172 deselected`.
- `uv run --extra dev python -m pytest tests/test_llm_engine.py -q` passed:
  `221 passed`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- First full
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  failed because `frontend/admin` dependencies were not installed
  (`esbuild` missing), not because of the Python parser change.
- After `npm ci --prefix frontend/admin`, final full pytest passed:
  `1182 passed, 19 skipped`.
- `scripts/orchestration/run_stage_closeout.py --stage tj-nzob`: passed,
  including process verification, artifact validation, project-index review,
  documentation review, debt marker scan, and full code-change gates.
- After user delivery approval, `codex/tj-nzob-comma-brief` was fast-forwarded
  into `main` at `cefea6e6f9f37f3554af1980a68861705f6bc8e6`.
- Merged-result closeout passed on `main`:
  `scripts/orchestration/run_stage_closeout.py --stage tj-nzob` ->
  `1182 passed, 19 skipped` plus process verification.
- `git push origin main` pushed `c6185f2..cefea6e`.
- GitHub Actions run `26502776229` passed `changes`, `lint`, `test`,
  `type-check`, and `deploy`.
- Runtime readback:
  `/opt/noor/.release-sha=cefea6e6f9f37f3554af1980a68861705f6bc8e6`;
  `/opt/noor/.release-run-id=26502776229`.
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` ->
  `8 passed, 0 failed`.

Documentation:
- docs-reviewed: updated - this stage summary, local implementation artifact,
  and handoff record the parser behavior and delivery status.
- project-index: reviewed-no-change - no repository navigation, entrypoint,
  integration boundary, verification command, or ownership boundary changed.
- graph-reviewed: no-change-needed - no knowledge graph is configured and
  `graphify-out/GRAPH_REPORT.md` is absent.

Residual / handoff:
- Local feature branch `codex/tj-nzob-comma-brief` was deleted after successful
  merge, push, deploy, and production smoke.
- Bead `tj-nzob` was closed as delivered and accepted.
- Live WhatsApp E2E was not run.
