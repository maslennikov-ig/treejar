---
task_id: tj-prl26.2
stage_id: tj-prl26
repo: treejar
branch: codex/tj-prl26-prelaunch-readiness
base_branch: origin/main
base_commit: f1136fc2a6d6c8c49535b4460c89f3486b2521c1
worktree: /home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness
status: passed
verification:
  - ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id': passed
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed
  - curl -fsS https://noor.starec.ai/api/v1/health: passed
  - anonymous GET /dashboard/ and /api/v1/conversations/: passed
  - scripts/bot_test.py stock/SKU synthetic message: failed
  - production read-only conversation/API/audit readback: passed
  - Context7 FastAPI docs lookup: passed
  - post-fix production SKU recheck conversation 8ad66895-1caa-45df-9f03-8907cc96f21f: passed
  - controlled E2E rerun 20260426181300 customer chat/product/stock/clarification: passed
  - controlled E2E rerun quotation approve Fr3143 + PDF/text/order-status: passed
  - controlled E2E rerun quotation reject Fr3144 + rejected/no-active-order status: passed
  - controlled E2E rerun Telegram private manager reply persistence: passed
  - controlled E2E rerun active escalation fallback and resolution: passed
  - production DB read-only pending count for rerun conversations: 5 total, 0 pending
  - production outbound audit read-only source counts: passed
changed_files:
  - .codex/stages/tj-prl26/artifacts/tj-prl26.2.md
  - .codex/stages/tj-prl26/summary.md
  - .codex/handoff.md
---

# Summary

Bounded pre-launch E2E for `tj-prl26.2` is now passed after the `tj-prl26.5` SKU masking blocker was fixed and deployed.

The first run stopped on a launch blocker: production public catalog and DB contained SKU `00-07024023`, but the bot said the SKU did not exist. `tj-prl26.5` fixed root cause by preserving labeled product identifiers during PII masking. After deployment of `d93b95480ec4ca53459f3a0bd527b1a27eb73358`, the narrow SKU recheck passed.

The full controlled rerun on 2026-04-26 used real test WhatsApp `79262810921` with unique `tj-prl26-*` suffixes and covered customer discovery/stock/clarification, quotation approve/reject, Telegram private manager reply, active escalation fallback, phone filtering, outbound audit, and final pending-count readback.

# Verification

Runtime/API smoke:

- Deployed SHA: `d93b95480ec4ca53459f3a0bd527b1a27eb73358`.
- GitHub Actions run id: `24963241165`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- `/api/v1/health` -> ok, Redis ok.
- Anonymous `/dashboard/` -> `401`; anonymous `/api/v1/conversations/` -> `403`.
- Alembic -> `2026_04_26_outbound_audit (head)`.

Post-fix narrow SKU recheck:

- Synthetic phone suffix: `79262810921#tj-prl26-sku-recheck-20260426180210`.
- Conversation: `8ad66895-1caa-45df-9f03-8907cc96f21f`.
- Bot reply returned SKU `00-07024023`, stock `12`, and price `685.00 AED`.
- Read-only DB readback: `escalation_status='none'`, pending recheck conversations `0`, messages persisted, outbound audit `f3f63b53-5b98-4c96-9979-569b03544c16` persisted with `status='sent'`.

# Controlled E2E Rerun

Run id: `20260426181300`.

Customer chat/product/stock/clarification:

- Phone suffix: `79262810921#tj-prl26-chat-rerun-20260426181300`.
- Conversation: `b7f6e4c2-92ac-4f47-a508-48bd1c188b83`.
- Discovery reply suggested three IMAGO operative tables and catalog prices `246`, `264`, and `450 AED`.
- Exact SKU reply for `00-07024023` returned stock `12` and price `685.00 AED`.
- Clarification/objection reply did not invent a discount: it stated current rate `685 AED`, total `1,370 AED` for 2 pieces, UAE/Dubai delivery available, and offered quotation or manager discussion.
- Final `escalation_status='none'`.

Quotation approve:

- Phone suffix: `79262810921#tj-prl26-approve-20260426181300`.
- Conversation: `03bcd8b9-334b-4dec-b29b-bb4d7a24861a`.
- Quotation: `Fr3143`.
- Initial bot reply: quotation prepared and sent to manager for review.
- Telegram webhook callback `order_confirm:03bcd8b9-334b-4dec-b29b-bb4d7a24861a` -> HTTP `200`, `{"status":"ok"}`.
- Metadata after callback: `quotation_decision_status='approved'`, `quotation_quote_number='Fr3143'`, `zoho_sale_order_active=true`, `order_active=true`.
- Order-status reply: `Quotation: Fr3143 - Approved`, `Sale Order: Fr3143 - Created`, `Shipment Status: Approved, order is being processed`.
- Final `escalation_status='resolved'`.

Quotation reject:

- Phone suffix: `79262810921#tj-prl26-reject-20260426181300`.
- Conversation: `7c937625-b6d9-4076-95d6-850858d2e8b2`.
- Quotation: `Fr3144`.
- Initial bot reply: quotation created and sent to manager for review.
- Telegram webhook callback `order_reject:7c937625-b6d9-4076-95d6-850858d2e8b2` -> HTTP `200`, `{"status":"ok"}`.
- Metadata after callback: `quotation_decision_status='rejected'`, `quotation_quote_number='Fr3144'`, `zoho_sale_order_active=false`, `order_active=false`.
- Order-status reply: quotation `Fr3144` was rejected and no active order is linked to the conversation.
- Final `escalation_status='resolved'`.

Telegram private manager reply:

- Phone suffix: `79262810921#tj-prl26-manager-20260426181300`.
- Conversation: `c103e283-21a7-45e3-960a-1caee8a7df60`.
- Initial customer message created `escalation_status='pending'`.
- Telegram webhook callback `faq_private:c103e283-21a7-45e3-960a-1caee8a7df60` -> HTTP `200`, `{"status":"ok"}`.
- Synthetic manager Telegram message -> HTTP `200`, `{"status":"ok"}`.
- Conversation readback found one persisted assistant message with `model='manager_reply'`.
- Final `escalation_status='resolved'`.

Active escalation fallback:

- Phone suffix: `79262810921#tj-prl26-escalation-20260426181300`.
- Conversation: `2fb85b1e-83f9-4534-844c-854086bf0852`.
- Initial customer message created `escalation_status='pending'`.
- Follow-up while pending produced assistant message `model='fallback'`: `A manager has been notified and will get back to you shortly`.
- The synthetic escalation was then resolved through `faq_private` manager reply so no pre-launch test remained pending.
- Final `escalation_status='resolved'`.

Phone filtering:

- Exact full suffix query for `79262810921#tj-prl26-chat-rerun-20260426181300` -> total `1`.
- Exact base query for `79262810921` -> total `1`, a separate base-phone conversation; suffix conversation was not included.
- Exact `phone=tj-prl26` -> total `0`.
- Explicit fuzzy `phone=tj-prl26&phone_match=fuzzy` -> total `3` at the moment of that check.

# Readback / Audit Evidence

Production DB read-only readback for run `20260426181300`:

- Conversations total: `5`.
- Pending conversations: `0`.
- Conversation status summary:
  - `b7f6e4c2-92ac-4f47-a508-48bd1c188b83`: chat/product, `none`.
  - `03bcd8b9-334b-4dec-b29b-bb4d7a24861a`: approve, `resolved`, `Fr3143`, `approved`.
  - `7c937625-b6d9-4076-95d6-850858d2e8b2`: reject, `resolved`, `Fr3144`, `rejected`.
  - `c103e283-21a7-45e3-960a-1caee8a7df60`: manager private reply, `resolved`.
  - `2fb85b1e-83f9-4534-844c-854086bf0852`: active escalation fallback, `resolved`.

Outbound audit source counts for the same five conversations:

- `bot_reply`, text, `sent`: `9`.
- `product_media`, media, `sent`: `3`.
- `product_media`, caption, `sent`: `3`.
- `order_confirm_pdf`, media, `sent`: `1`.
- `order_confirm_pdf`, caption, `sent`: `1`.
- `order_confirm_text`, text, `sent`: `1`.
- `order_reject_text`, text, `sent`: `1`.
- `manager_reply`, text, `sent`: `2`.
- `escalation_fallback`, text, `sent`: `1`.

Representative provider/idempotency samples:

- `order_confirm_pdf` caption: provider `1302d4e2-2879-41e5-bab5-a08d3ebd13b3`, CRM `order:03bcd8b9-334b-4dec-b29b-bb4d7a24861a:confirm:caption:Fr3143`.
- `order_confirm_pdf` media: provider `afffa131-3629-40cf-89f7-ae2bad71e397`, CRM `order:03bcd8b9-334b-4dec-b29b-bb4d7a24861a:confirm:pdf:Fr3143`.
- `order_confirm_text`: provider `a2e574ea-f683-4dd2-9512-f8e74dde2a4a`, CRM `order:03bcd8b9-334b-4dec-b29b-bb4d7a24861a:confirm:text:Fr3143`.
- `order_reject_text`: provider `8247abf9-735a-49d5-bab3-48c9c94c026d`, CRM `order:7c937625-b6d9-4076-95d6-850858d2e8b2:reject:text:Fr3144`.
- `manager_reply`: provider `9a85b9c2-8665-4348-becd-ae874e62cb5b`, CRM `manager:c103e283-21a7-45e3-960a-1caee8a7df60:27421:private`.
- `escalation_fallback`: provider `c66a809f-72e3-408a-ab16-f03976edf7a8`, CRM `fallback:2fb85b1e-83f9-4534-844c-854086bf0852:3fc06b31444e7a5a`.
- Escalation-resolution manager reply: provider `480efdb2-3a52-4644-babe-e2e25e577ee3`, CRM `manager:2fb85b1e-83f9-4534-844c-854086bf0852:27489:private`.

# Commands Run

- Required context reads: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-26-prelaunch-readiness.md`, `.codex/stages/tj-prl26/summary.md`.
- `bd show tj-prl26.2`, `bd update tj-prl26.2 --status in_progress`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`.
- `curl -fsS https://noor.starec.ai/api/v1/health`.
- Anonymous `curl` checks for `/dashboard/` and `/api/v1/conversations/`.
- SSH read-only release/Alembic checks from `/opt/noor`.
- Local Python harness using existing `scripts/bot_test.py` helpers to send Wazzup webhook messages and poll protected Conversation API.
- Synthetic Telegram webhook callback/message posts to `/api/v1/webhook/telegram` for created conversation IDs only.
- SSH/psql read-only DB queries for conversations, messages, and outbound audits.

# Skipped Guardrail Actions

Skipped as explicitly forbidden:

- `scripts/verify_wazzup.py`.
- Scheduled AI Quality Controls.
- Broad production suites.
- Unsolicited media tests outside quotation PDF/caption generated by the approved flow.
- Deploys, config changes, secret changes.
- Manual DB/Redis mutation outside normal app writes caused by approved synthetic E2E.
- Synthetic Wazzup status webhook update. Existing outbound audit rows had provider IDs and `sent` statuses; status-update persistence was already covered by delivered `tj-e2e26`.

# Risks / Follow-ups / Explicit Defers

- No launch blocker found in the rerun.
- Product price source difference remains visible: discovery/catalog suggestions show catalog prices such as `264 AED`, while exact SKU stock/price returns Zoho rate `685.00 AED`. This matches current handoff truth that Zoho is exact stock/price truth, but it should be watched as a commercial-content risk.
- All synthetic conversations from rerun `20260426181300` are no longer pending.
