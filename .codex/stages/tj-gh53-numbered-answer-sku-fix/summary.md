# Stage tj-gh53-numbered-answer-sku-fix Summary

Status: delivered to `main`, deployed to production, live E2E verified, and
synthetic test conversations cleaned.

Scope: fix GitHub #53 so numbered qualifying answers such as
`3. No` / `4. For commercial office space` are not parsed as fake product
references like `NO-4`.

Current decisions:
- Alpha SKU parsing is limited to the current Treejar dialogue grammar prefixes
  `CH`, `CP`, and `SK`.
- Alpha SKU matches crossing a line break are rejected before normalization.
- `NO`, `YES`, and `LOW` remain in the denylist as an additional guard, but
  correctness does not depend on enumerating every answer word.
- Dialogue product-selection routing uses only non-empty parser refs that do not
  cross line breaks, so a future parser regression is less likely to immediately
  produce `clarify_product_selection`.
- Valid existing forms are preserved: `CH 616`, `CH-616`, `CH616`,
  `SK 45 White`, `CP-2.1S`, `00-07024023`, and `SKYLAND NOVO 2400`.

Verification before delivery:
- RED tests reproduced `NO-4`, `YES-5`, `LOW-3`, and the #53 answer-list
  product-reference prompt.
- Targeted after final rebase:
  `uv run pytest tests/test_dialogue_catalog_refs.py tests/test_dialogue_runner.py tests/test_dialogue_order_runtime.py tests/test_llm_engine.py -q`
  passed: `383 passed`.
- `uv run ruff check src/ tests/` passed.
- `uv run ruff format --check src/ tests/` passed.
- Earlier full local gates passed before the docs-only base rebase:
  `uv run mypy src/` passed, and
  `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  passed: `1425 passed, 19 skipped`.
- `scripts/orchestration/run_process_verification.sh` passed.

Delivery:
- Feature branch pushed:
  `origin/codex/tj-gh53-numbered-answer-sku-fix`.
- `main` was fast-forwarded to runtime commit
  `f1b7f0c5360fedbba7c9e8dd9ab983ef784a3cf1`.
- GitHub Actions CI/deploy run `27633383386` passed:
  `changes`, `lint`, `test`, `type-check`, and `deploy`.
- Production marker readback:
  `/opt/noor/.release-sha` =
  `f1b7f0c5360fedbba7c9e8dd9ab983ef784a3cf1`;
  `/opt/noor/.release-run-id` = `27633383386`.
- Production API smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed: `8 passed, 0 failed`.

Live E2E:
- Approved base number: `+79262810921`.
- Isolated clean chatId:
  `+79262810921#tj-gh53-live-clean-20260616164900`.
- Conversation `a73e7b96-26e9-4104-9f52-56463316f36e` passed:
  after the numbered answer list, production replied with table alternatives,
  not `I have the product reference...`.
- Readback assertions passed:
  `pending_product_refs=None`, `NO-4` absent from conversation payload, and the
  bad product-reference reply absent.
- First race-check conversation
  `0d63fbe4-1d91-4dbb-838e-504bd2624b6c` also had no bad product-reference
  reply and no `NO-4`.
- Synthetic cleanup closed both conversations matching `tj-gh53-live`;
  post-cleanup `non_closed=0`.

Documentation:
- `docs/specs/dialogue-state-kernel.md` updated with numbered-answer
  false-positive behavior and the explicit alpha prefix contract.
- docs-reviewed: updated.
- graph-reviewed: no-change-needed - Graphify is not configured and no
  `graphify-out/GRAPH_REPORT.md` exists.

Residual / handoff:
- Beads `tj-6r78` is closed with implementation and verification evidence.
- No in-scope code defers remain.
