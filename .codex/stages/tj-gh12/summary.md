# Stage tj-gh12: GitHub Issues Stabilization

Updated: 2026-05-13
Status: second post-deploy E2E found name-only capture blocker; hotfix verified locally
Branch: `codex/tj-gh12-name-gate-hotfix-clean`
Base: `main@91e61fca5390f857b5902f8476b5ee54a87dbf24`

## Goal

Stabilize the new GitHub issue batch #21, #22, #24-#33 through Local Beads without mutating GitHub issues, production config, or live WhatsApp state.

## Scope

- Reconcile orchestration baseline from `balanced-v2.5` drift to `balanced-v2.7`.
- Rename customer-facing runtime identity to Noor and enforce the first-turn unknown-name gate.
- Harden quotation-ready parsing for Cyrillic homoglyph SKUs, compact/spaced/hyphen SKU forms, and pending sales-order quote resume.
- Add min/max price filters to `search_products` and deterministic Treejar showroom Maps replies.
- Block quotation creation until required customer details, specific address, and item quantities are present.
- Compact quotation PDF layout for small quotes.
- Add messaging typing provider surface and a best-effort batch refresh loop, with Wazzup typing blocked rather than faked.
- Add disabled-by-default proposal follow-up metadata, FU1-FU4 scheduling, read/reply/rejection/autoreply handling, and bounded executor with template/freeform send safety gates.

## Current State

Implemented in `codex/tj-gh12-new-issues`. Local Beads were created for `tj-gh12.1` through `tj-gh12.6`; existing `tj-b4n` was reused for GitHub #24 with parent `tj-gh12`.

A code review report was written to `docs/reports/code-reviews/2026-05/CR-2026-05-12-tj-gh12-review.md`. Review follow-up Beads `tj-gh12.7` through `tj-gh12.11` were created and closed after fixing the exact-quote missing-data fallback, stage script `tomllib` bootstrap, quotation item gate, proposal follow-up executor/read-status integration, Wazzup typing loop churn, and Maps URL cleanup.

A follow-up code review report was written to `docs/reports/code-reviews/2026-05/CR-2026-05-13-tj-gh12-follow-up-review.md`. Follow-up Beads `tj-gh12.12` through `tj-gh12.14` were created and closed after fixing price phrase SKU false positives, restoring artifact-required closeout enforcement, and blocking proposal template-mode sends until the Wazzup template transport shape is explicitly confirmed.

`tj-b4n` remains blocked because the public Wazzup sending-message documentation does not expose a supported typing endpoint. The code deliberately logs/no-ops for Wazzup typing instead of guessing an undocumented API shape.

Proposal follow-up sending remains disabled by default. The runtime now records proposal follow-up state after quotation PDF send, stops/pauses the chain on customer reply, rejection, autoreply, or Wazzup read status, and includes a bounded ARQ executor. Outbound FU sends still require explicit enablement and configured templates/freeform copy; outside-24h template mode also requires `template_transport_confirmed` after the real Wazzup payload shape is confirmed.

Post-deploy controlled E2E task `tj-gh12.15` was started on production `main@cc3fcf5a5f3e3dd13249aaf7091a1b0d975a180a` using the approved WhatsApp test number. Scenario A found a blocker: the first visible reply correctly used Noor and asked for the customer's name, but the exact-quote/product-media path still created a pending escalation and sent product media captions before the name was known. The synthetic conversation was later resolved through the normal `faq_private` manager-resolution path; final `tj-gh12-e2e` pending count was `0`.

Hotfix Beads `tj-gh12.16` and `tj-gh12.17` were added. `tj-gh12.16` short-circuits first-turn unknown-name requests before any product/quotation/escalation/media side effects. `tj-gh12.17` prevents the private manager reply adapter from introducing risky unsupported price, stock, or immediate-delivery claims absent from the manager draft.

Hotfix `91e61fca5390f857b5902f8476b5ee54a87dbf24` was deployed by GitHub Actions run `25789632904`. Post-hotfix scenario A passed in production: first-turn unknown-name SKU request returned `name-gate`, kept escalation `none`, and sent no product media. Scenario B then found `tj-gh12.18`: after the name gate, a name-only reply was not captured and escalated to manager confirmation. The synthetic B conversation was resolved through the application-level Telegram `faq_private` manager-reply handler; no direct DB/Redis cleanup update was used.

`tj-gh12.18` is fixed locally. Natural-language names such as `My name is E2E Tester.` are extracted into quote customer details and `conversation.customer_name`; name-only replies after the name gate now return a local `name-capture` acknowledgement without LLM or manager escalation.

project-index: reviewed-no-change - existing index already covers `src/services/` follow-up responsibilities, messaging integrations, orchestration scripts, and verification entrypoints; no stable navigation entrypoint changed.

## Verification

- Code-review RED/GREEN regressions: failed before fixes (`6 failed`) and passed after fixes (`6 passed`).
- Follow-up code-review RED/GREEN regressions: failed before fixes (`6 failed`) and passed after fixes (`13 passed` including adjacent SKU/template happy paths).
- Targeted central LLM/quotation behavior suite: passed (`23 passed`).
- Expanded impacted suite: passed (`265 passed`).
- PDF template suite: passed (`3 passed`).
- Typing provider/chat suite: passed (`30 passed` in worker verification; targeted additions passed locally).
- Proposal follow-up and webhook suite: passed (`22 passed` after executor/read-status integration).
- Follow-up impacted suite: passed (`39 passed`).
- Frontend regression dependency restored with `npm ci` in `frontend/admin`; `tests/test_admin_dashboard_frontend.py` passed (`11 passed`).
- Full local pytest passed: `1002 passed, 19 skipped`.
- Hotfix RED/GREEN for `tj-gh12.16` and `tj-gh12.17`: failed before fixes and passed after fixes.
- Hotfix impacted suite passed: `201 passed`.
- Hotfix full local pytest passed: `1004 passed, 19 skipped`.
- Post-hotfix production E2E A passed on `91e61fc`; B blocked on `tj-gh12.18` and was cleaned through `faq_private`.
- `tj-gh12.18` RED/GREEN regression failed before fix and passed after fix.
- `tj-gh12.18` impacted suite passed: `202 passed`.
- `tj-gh12.18` full local pytest passed: `1005 passed, 19 skipped`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- `scripts/orchestration/run_process_verification.sh`: passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-gh12`: passed.

## Risks / Follow-ups

- Wazzup typing cannot be delivered without official provider support or documentation for a typing endpoint.
- Follow-up message sending must stay disabled until approved WhatsApp templates/config are supplied; template-mode sends additionally require confirmed Wazzup template transport schema.
- Live B-H E2E remains paused until `tj-gh12.18` is deployed and name-only capture is rechecked.
