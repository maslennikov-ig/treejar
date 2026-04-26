---
task_id: tj-prl26.4
stage_id: tj-prl26
repo: treejar
branch: codex/tj-prl26-prelaunch-readiness
base_branch: origin/main
base_commit: f1136fc2a6d6c8c49535b4460c89f3486b2521c1
worktree: /home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness
status: launch-ready-with-explicit-defer
verification:
  - reviewed tj-prl26.1 checklist/runbook artifact: passed
  - reviewed tj-prl26.2 controlled E2E artifact and rerun evidence: passed
  - reviewed tj-prl26.3 admin/operator/cost-control readiness artifact: passed
  - reviewed tj-prl26.5 SKU blocker deploy/recheck artifact: passed
  - production E2E rerun 20260426181300 pending count: 5 total, 0 pending
  - production outbound audit readback for rerun conversations: passed
  - PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-prl26: passed
changed_files:
  - .codex/stages/tj-prl26/artifacts/tj-prl26.4.md
  - .codex/stages/tj-prl26/artifacts/tj-prl26.2.md
  - .codex/stages/tj-prl26/summary.md
  - .codex/handoff.md
---

# Summary

Pre-launch readiness is launch-ready with one explicit commercial-content defer.

No open launch blocker remains after the `tj-prl26.5` SKU masking fix and the controlled `tj-prl26.2` rerun. Runtime health, auth guards, admin/operator defaults, AI Quality Controls safe defaults, customer chat, stock, quotation approval/reject, Telegram private manager reply, active escalation fallback, outbound audit visibility, and final pending-count readback all have fresh production evidence.

Launch recommendation: proceed with a controlled soft launch / owner-monitored start, keeping scheduled AI Quality Controls disabled and watching catalog-vs-Zoho price copy.

# Verification

Reviewed evidence:

- `tj-prl26.1`: checklist/runbook and controlled E2E prompt created and validated.
- `tj-prl26.3`: read-only admin/operator/cost-control readiness passed; anonymous admin/dashboard/conversation access denied; `ai_quality_controls` missing means disabled defaults; `llm_attempts` and outbound audit tables exist.
- `tj-prl26.5`: root cause fixed, deployed as `d93b95480ec4ca53459f3a0bd527b1a27eb73358`, GitHub Actions run `24963241165` passed, narrow SKU recheck returned SKU `00-07024023`, stock `12`, price `685.00 AED`.
- `tj-prl26.2`: controlled rerun `20260426181300` passed customer chat, stock, quotation approve/reject, private manager reply, active escalation fallback, phone filters, audit readback, and pending count.

Production rerun facts:

- Runtime: `https://noor.starec.ai`.
- Release SHA: `d93b95480ec4ca53459f3a0bd527b1a27eb73358`.
- Health/API: `verify_api.py` 7/0; `/api/v1/health` ok; `/dashboard/` anonymous `401`; `/api/v1/conversations/` anonymous `403`; Alembic `2026_04_26_outbound_audit (head)`.
- Conversations: `b7f6e4c2-92ac-4f47-a508-48bd1c188b83`, `03bcd8b9-334b-4dec-b29b-bb4d7a24861a`, `7c937625-b6d9-4076-95d6-850858d2e8b2`, `c103e283-21a7-45e3-960a-1caee8a7df60`, `2fb85b1e-83f9-4534-844c-854086bf0852`.
- Quotation approve: `Fr3143`, approved/processing order-status, PDF media/caption and text audit rows.
- Quotation reject: `Fr3144`, rejected/no-active-order status, rejection audit row.
- Pending count for rerun conversations: `5` total, `0` pending.
- Outbound audit source counts: `bot_reply=9`, `product_media media/caption=3/3`, `order_confirm_pdf media/caption=1/1`, `order_confirm_text=1`, `order_reject_text=1`, `manager_reply=2`, `escalation_fallback=1`, all sampled rows `sent` with provider ids and deterministic `crm_message_id`.
- Stage closeout: first local run failed because the fresh worktree lacked `frontend/admin/node_modules/esbuild`; after `npm ci` in `frontend/admin`, `PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-prl26` passed with `ruff`, `format --check`, `mypy`, full local pytest `774 passed, 19 skipped`, process verification, artifact validation, and `check_stage_ready`.

# Risks / Follow-ups

- Explicit defer: catalog discovery can show catalog price `264 AED` for SKU `00-07024023`, while exact stock/price uses Zoho rate `685.00 AED`. Current project truth says Zoho is exact stock/price source, so this is not a launch blocker, but it can confuse customers and should be watched or reconciled before broader marketing traffic.
- Keep scheduled AI Quality Controls disabled at launch. Manual/daily-sample QA can be enabled later with low budgets.
- No production observation window was run because the project has no real customer traffic yet.
- Guardrails respected: no `scripts/verify_wazzup.py`, no scheduled AI Quality Controls, no broad production suites, no unsolicited media tests, no deploy/config/secret changes during the rerun, and no manual DB/Redis mutation outside normal approved synthetic E2E writes.
