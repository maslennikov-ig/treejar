---
schema_version: orchestration-artifact/v1
task_id: tj-final27.9
stage_id: tj-final27
repo: treejar
branch: codex/tj-final27-9-acceptance-pack
base_branch: origin/main
base_commit: 93e9bc40f3c663a9f48fed6ab635064d7bbfa996
worktree: /home/me/code/treejar/.worktrees/codex-tj-final27-9-acceptance-pack
status: blocked
delivery_method: n/a
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: Blocked acceptance artifact remains tracked; no branch cleanup is required for this artifact.
risk_level: medium
verification:
  - "Context7 resolve pytest docs: passed"
  - "Context7 query pytest narrow selection/stop rules: passed after one timeout retry"
  - "bd update tj-final27.9 --append-notes ...: passed"
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed, 7 passed / 0 failed"
  - "curl https://noor.starec.ai/api/v1/health: passed, HTTP 200, status ok"
  - "anonymous auth guards: passed, /dashboard/ 401, /api/v1/conversations/ 403, /api/v1/admin/ai-quality-controls 401"
  - "local protected polling credential check: blocked, API_KEY/BOT_TEST_API_KEY missing"
  - "ssh read-only runtime credential check: blocked, Permission denied (publickey)"
  - "bd update tj-final27.9 --status blocked: passed"
  - "ssh noor-server read-only runtime/API key presence check: passed"
  - "controlled E2E chat scenario: passed, conversation aaec088f-6727-4791-8fa5-569f472fd91f"
  - "controlled E2E SKU truth scenario: passed, conversation f148f28f-bab5-4954-836f-129104c270ff"
  - "controlled E2E quotation approve scenario: passed, conversation bba5d36e-c133-42c3-9c9b-51101db90596, quotation Fr3167"
  - "controlled E2E quotation reject scenario: passed, conversation 30ba5ba5-cec4-4a6e-954c-00583c8ae0f3, quotation Fr3168"
  - "controlled E2E manager private reply scenario: passed, conversation 5be359c6-87c8-4cac-aa4a-744c8eeca474"
  - "controlled E2E active escalation fallback scenario: passed, conversation 5e5e68ec-b43a-4bd5-a6d7-95dbc13e8d6f"
  - "controlled E2E final pending readback: passed, 6 tj-final27 conversations, 0 pending"
  - "protected conversation API phone filtering: passed, exact full suffix 1, exact prefix 0, fuzzy prefix 6"
  - "bd update tj-final27.9 --status blocked --append-notes final E2E result: passed"
  - "bd update tj-final27.9 --status in_progress --append-notes quality pass approval: passed"
  - "quality consultative sales scenario: completed, conversation 6c75c79c-3cf0-492a-9d0c-fd0fb29e8857"
  - "quality objection scenario: completed with quality risk, same conversation, synthetic manager reply resolved pending escalation"
  - "quality retention scenario: completed with quality risk, same conversation, synthetic manager reply resolved pending escalation"
  - "quality payment terms/discount scenario: completed, conversation e5e9654f-05f7-4098-98bf-56e594c6bde4, synthetic manager reply resolved pending escalation"
  - "quality cross-border delivery scenario: completed, conversation 1661ac10-7826-44e2-99c6-b18685bcbecc, synthetic manager reply resolved pending escalation"
  - "quality Arabic sales scenario: passed, conversation fadc1a58-0aed-44ea-be5d-139e510ea64c"
  - "quality off-catalog scenario: completed with quality risk, conversation 6a012c47-e55f-424d-b4a1-1f8561ce24d5, synthetic manager reply resolved pending escalation"
  - "quality large-order handoff scenario: passed, conversation 0c9fc0b3-7315-4a4b-8214-d00aa857e864, synthetic manager reply resolved pending escalation"
  - "quality final pending readback: passed, 6 tj-final27-quality conversations, 0 pending"
  - "quality outbound audit aggregate: bot_reply text 8, manager_reply text 6, product_media media/caption 9/9, all sent"
  - "bd update tj-final27.9 --status blocked --append-notes quality result: passed"
  - "git diff --check: passed"
  - "uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.9.md: passed"
  - "scripts/orchestration/run_process_verification.sh: passed"
  - "2026-04-30 docs promotion refresh: carried into main after later deployed follow-ups; no live E2E, production mutation, or deploy run by this docs sync"
changed_files:
  - docs/client/final-acceptance-pack-2026-04-29.md
  - docs/testing/final-controlled-e2e-runbook-2026-04-29.md
  - .codex/stages/tj-final27/artifacts/tj-final27.9.md
  - .codex/stages/tj-final27/summary.md
  - .codex/handoff.md
explicit_defers:
  - tj-final27.9 final acceptance requires approved live/final E2E and production drill decisions
---

# Summary

Prepared the `tj-final27.9` final acceptance pack and controlled E2E runbook as docs/evidence work. During the original E2E task, no code, deploy, push, staging/prod config, Wazzup verification, broad production suite, scheduled AI Quality Controls, or voice/audio test was run.

The client-facing acceptance pack is `docs/client/final-acceptance-pack-2026-04-29.md`. It separates what was promised, what is delivered, what already has CI/E2E/prod-smoke evidence, and what remains a client decision or explicit defer. The controlled E2E runbook is `docs/testing/final-controlled-e2e-runbook-2026-04-29.md`. It defines scenarios, proposed test number/channel, synthetic suffix policy, stop rules, and prohibited actions requiring separate approval.

After user approval, the controlled E2E run initially stopped before live WhatsApp messages because the required protected conversation polling credential was not available locally. The SSH key was then found via the `noor-server` alias, read-only runtime access succeeded without printing secrets, and the approved controlled E2E subset was completed. A separately approved bounded text-only quality pass was then run against production synthetic suffixes to assess sales quality, objection handling, hard-facts safety, Arabic response, off-catalog behavior, and large-order handoff.

2026-04-30 refresh: the artifact and docs were promoted from the old worktree into current `main` after later narrow follow-ups were delivered. Current production baseline is `main@354015280c8f8d39b538bbaba769e70d29d1c6b2`; the `tj-final27.9` controlled E2E evidence below remains the historical 2026-04-29 run against `main@090e318d06662eb4a4c4f2247eb01bd1ed317b94`. No new live E2E or production mutation was performed during the docs promotion.

# Evidence Reviewed

- Repo contract: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`.
- Final stage plan and status: `docs/plans/2026-04-27-final-delivery-completion.md`, `.codex/stages/tj-final27/summary.md`.
- Required final27 artifacts: `.codex/stages/tj-final27/artifacts/tj-final27.1.md`, `.codex/stages/tj-final27/artifacts/tj-final27.2.md`, `.codex/stages/tj-final27/artifacts/tj-final27.3.md`, `.codex/stages/tj-final27/artifacts/tj-z911.md`.
- Delivered runtime/E2E history: `.codex/stages/tj-ruue/summary.md`, `.codex/stages/tj-e2e26/summary.md`, `.codex/stages/tj-prl26/summary.md`.
- Client promise sources: `docs/tz.md`, `docs/03-ai-agent-requirements.md`, `docs/response-to-client-2026-02-17.md`.
- Existing operator/test docs: `docs/admin-guide.md`, `docs/testing/manual-test-checklist.md`, `docs/prompts/2026-04-26-tj-prl26-controlled-e2e-agent.md`, `docs/client/whatsapp-self-test-scenarios-2026-04-06.md`.

# Acceptance Pack Summary

Promised scope includes WhatsApp AI sales automation, English/Arabic support, Treejar Catalog API product truth, Zoho CRM/Inventory integration, quotation/SaleOrder/PDF flow, order status, manager handoff, Telegram notifications, admin/operator controls, QA/reporting, referrals, feedback, payment follow-up, nonfunctional readiness, and final E2E acceptance.

Delivered/evidenced scope includes the core production sales path, catalog/Zoho truth reconciliation, strict price fail-closed policy, CRM attribution storage and bounded returning context, disabled-safe payment reminder controls, OpenRouter cost controls, AI Quality Controls disabled-safe defaults, conversation API auth guards, outbound Wazzup audit/idempotency, quotation approve/reject order-status copy, Telegram private manager replies, controlled pre-launch E2E, and production smoke on deployed `main@090e318d06662eb4a4c4f2247eb01bd1ed317b94` at the time of this final E2E run.

Confirmed evidence already recorded includes GitHub Actions CI/deploy runs `24876930080`, `24957702024`, `24958178545`, `24963241165`, and `25115695746`; production `verify_api.py` smoke passes; `/api/v1/health` OK; anonymous admin/dashboard/conversation APIs denied; and prior controlled E2E runs leaving zero pending synthetic conversations.

Later delivered follow-ups are also relevant to current acceptance posture: `tj-final27.11` sales fallback deployed on `ab897878e2f0ee339bd7626b63d5c6f3a9497042`, `tj-jy5i` commercial-offer/proposal routing deployed on `1cce2aa4bdbc82b9a11ce2f7ce117103e6a3e6f0`, and `tj-final27.13` payment-reminder provider reuse deployed on `354015280c8f8d39b538bbaba769e70d29d1c6b2`.

# Controlled E2E Runbook Summary

The runbook proposes the previously used real test WhatsApp number `79262810921` and production Wazzup channel, but only after explicit approval. Synthetic identities must use a unique `tj-final27` suffix per scenario, for example `+79262810921#tj-final27-quote-approve-YYYYMMDDHHMM`. Exact readback uses the full suffix; fuzzy readback is reserved for aggregate pending-count checks.

Scenarios are ordered from read-only runtime smoke to customer discovery, exact SKU price/stock truth, quotation approve/reject, manager private reply, active escalation fallback, CRM attribution/returning context, payment-reminder disabled defaults, QA/reporting disabled defaults, feedback, referral, and voice/audio. Feedback, referral, payment-reminder sends, media beyond approved quotation artifacts, and voice/audio are approval-only branches.

Stop rules require aborting on missing approval, health/auth failure, non-test channel/number, missing protected polling credentials, hallucinated price/stock/policy, wrong or unaudited quotation, unresolved pending escalation, non-zero pending synthetic conversations after cleanup, duplicate visible Wazzup sends, unsafe cost-control defaults, or any need for manual DB/Redis mutation.

# Controlled E2E Attempt

User approval for approved-only final E2E was received on 2026-04-29. The run started with read-only smoke:

- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> passed, `7 passed, 0 failed`.
- `curl https://noor.starec.ai/api/v1/health` -> HTTP `200`, `status=ok`.
- Anonymous `/dashboard/` -> `401`.
- Anonymous `/api/v1/conversations/` -> `403`.
- Anonymous `/api/v1/admin/ai-quality-controls` -> `401`.

The run then stopped before sending any live WhatsApp message:

- Local `.env` contains `WAZZUP_CHANNEL_ID`, but does not contain `API_KEY` or `BOT_TEST_API_KEY`.
- Shell environment also lacks `API_KEY`, `BOT_TEST_API_KEY`, `WAZZUP_CHANNEL_ID`, and `BOT_TEST_CHANNEL_ID`.
- `scripts/bot_test.py` requires an API key for protected conversation polling.
- Read-only SSH attempt to `noor-dev@95.216.204.189:/opt/noor` failed with `Permission denied (publickey)`, so the production `API_KEY` could not be confirmed without printing or storing secrets.

The SSH key was found via the local `noor-server` alias. Read-only runtime check then confirmed:

- Runtime SHA: `090e318d06662eb4a4c4f2247eb01bd1ed317b94`.
- GitHub Actions run id: `25115695746`.
- `API_KEY` and `WAZZUP_CHANNEL_ID` are present on the server.
- Baseline `tj-final27` conversations before live sends: `0 total`, `0 pending`.
- Product readback for SKU `00-07024023`: `price=310.65`, `currency=AED`, `stock=12`, `is_active=True`, Zoho item id present.

Approved controlled live scenarios then passed:

- Customer discovery: suffix `79262810921#tj-final27-chat-202604291709`, conversation `aaec088f-6727-4791-8fa5-569f472fd91f`. Bot proposed concrete office-chair options and did not escalate.
- Exact SKU/price/stock: suffix `79262810921#tj-final27-sku-202604291710`, conversation `f148f28f-bab5-4954-836f-129104c270ff`. Bot returned `12 items` and `310.65 AED`, matching read-only DB evidence.
- Quotation approve: suffix `79262810921#tj-final27-quote-approve-202604291710`, conversation `bba5d36e-c133-42c3-9c9b-51101db90596`, quotation `Fr3167`. `order_confirm` callback returned HTTP `200`; order-status copy says quotation `Fr3167` approved, sale order `Fr3167`, shipment approved/processing; escalation resolved.
- Quotation reject: suffix `79262810921#tj-final27-quote-reject-202604291713`, conversation `30ba5ba5-cec4-4a6e-954c-00583c8ae0f3`, quotation `Fr3168`. `order_reject` callback returned HTTP `200`; order-status copy says quotation `Fr3168` rejected and no active order is linked; escalation resolved.
- Manager private reply: suffix `79262810921#tj-final27-manager-202604291715`, conversation `5be359c6-87c8-4cac-aa4a-744c8eeca474`. `faq_private` callback and synthetic manager message returned HTTP `200`; readback shows `escalation_status=resolved` and persisted assistant message `model=manager_reply`.
- Active escalation fallback: suffix `79262810921#tj-final27-escalation-202604291716`, conversation `5e5e68ec-b43a-4bd5-a6d7-95dbc13e8d6f`. Follow-up while pending created a separate assistant message `model=fallback`; synthetic manager reply then resolved the escalation with a persisted `manager_reply`.

Final readback:

- `tj_final27_total=6`.
- `tj_final27_pending=0`.
- Protected conversation API phone filtering passed: exact full suffix total `1`, exact `phone=tj-final27` total `0`, explicit fuzzy `phone=tj-final27&phone_match=fuzzy` total `6`.
- Outbound audit readback for `tj-final27`: `bot_reply` text `8`, `product_media` media/caption `3/3`, `order_confirm_pdf` media/caption `1/1`, `order_confirm_text` `1`, `order_reject_text` `1`, `manager_reply` `2`, `escalation_fallback` `1`; all sampled aggregate statuses were `sent`.

No voice/audio, payment reminder/template send, referral, feedback, `scripts/verify_wazzup.py`, broad production suite, scheduled AI Quality Controls, deploy, or prod/staging config mutation was run during the original E2E task.

# Approved Quality Pass

User approval for an additional bounded live quality pass was received on 2026-04-29. Scope was limited to text-only synthetic conversations with `tj-final27-quality-*` suffixes. The pass did not run voice/audio, payment reminder sends/templates, referrals, feedback, `scripts/verify_wazzup.py`, broad production suites, scheduled AI Quality Controls, deploy, or production/staging config changes. Product recommendation scenarios did create normal `product_media` outbound audit rows as a side effect of catalog recommendations; no separate media test was intentionally run.

Runtime guardrail evidence before the pass:

- Runtime SHA: `090e318d06662eb4a4c4f2247eb01bd1ed317b94`.
- GitHub Actions run id: `25115695746`.
- Existing `tj-final27-quality` conversations before the pass: `0 total`, `0 pending`.

Scenario results:

| Scenario | Suffix | Conversation | Result |
| --- | --- | --- | --- |
| Consultative sales for 20 ergonomic chairs around 500 AED | `tj-final27-quality-sales-202604291756` | `6c75c79c-3cf0-492a-9d0c-fd0fb29e8857` | Pass. Bot did not invent a within-budget option; it gave closest alternatives, price/stock gaps, and a useful budget-flexibility question. |
| Price objection in same sales conversation | same suffix | same conversation | Safety pass, sales-quality risk. Bot did not invent a discount, but replied only `I want to be accurate, so our manager will confirm this for you.` and opened a pending escalation. Synthetic `faq_private` manager reply resolved it. |
| Retention in same sales conversation | same suffix | same conversation | Safety pass, retention-quality risk. Bot again used the same generic manager-confirmation copy instead of a polite save/return later response. Synthetic manager reply resolved it. |
| Net 30 payment terms and 20% discount | `tj-final27-quality-net30-202604291756` | `e5e9654f-05f7-4098-98bf-56e594c6bde4` | Pass for hard-facts safety. Bot did not promise payment terms or discount and escalated to manager confirmation. Synthetic manager reply resolved it. |
| Saudi Arabia delivery next week | `tj-final27-quality-ksa-202604291756` | `1661ac10-7826-44e2-99c6-b18685bcbecc` | Pass for hard-facts safety. Bot did not promise cross-border delivery or date and escalated for logistics confirmation. Synthetic manager reply resolved it. |
| Arabic sales request for 10 ergonomic chairs around 500 AED | `tj-final27-quality-ar-202604291756` | `fadc1a58-0aed-44ea-be5d-139e510ea64c` | Pass. Bot replied in Arabic, stayed catalog-grounded, explained that no exact 500 AED ergonomic option was found, and offered budget/product-direction choices. |
| Off-catalog helicopter spare parts / gaming laptops | `tj-final27-quality-offcatalog-202604291756` | `6a012c47-e55f-424d-b4a1-1f8561ce24d5` | Safety pass, sales-quality risk. Bot did not hallucinate products, but escalated generically instead of directly saying Treejar focuses on office furniture. Synthetic manager reply resolved it. |
| Large order: 250 chairs to Dubai Marina next week | `tj-final27-quality-large-202604291756` | `0c9fc0b3-7315-4a4b-8214-d00aa857e864` | Pass. Bot captured quantity/location/timing, avoided confirming stock/price itself, and routed to manager verification. Synthetic manager reply resolved it. |

Final quality readback:

- Protected conversation API: `6` `tj-final27-quality` conversations, `0` pending.
- DB readback: `quality_total 6`, `quality_pending 0`.
- Assistant models: `z-ai/glm-5` `3`, `z-ai/glm-5|verified-policy` `5`, `manager_reply` `6`.
- Outbound audit aggregate: `bot_reply` text `8`, `manager_reply` text `6`, `product_media` media/caption `9/9`; all sampled aggregate statuses were `sent`.

Quality conclusion:

- Functional safety is acceptable for the tested set: no fake discount, no unsupported payment terms, no unsupported cross-border delivery promise, no off-catalog hallucination, no invented budget product, and all synthetic escalations were closed.
- Commercial response quality was uneven in the 2026-04-29 quality pass. The model was strong when catalog search succeeded or when the large-order handoff path was explicit, but the verified-policy fallback was too generic for objection handling, retention, and off-catalog redirection. This was later addressed by `tj-final27.11` with compact deterministic sales fallback and controlled text-only E2E.
- WhatsApp readability is acceptable but not fully polished. Responses use separators and bold markdown that are readable in WhatsApp-style text, but the format can look mechanical for a sales chat.

# Verification

Context7 docs-first check:

- `mcp__context7__.resolve_library_id` for `pytest` -> selected `/pytest-dev/pytest`.
- First `mcp__context7__.query_docs` request timed out.
- Narrow retry succeeded and confirmed current pytest command examples for file/node-id selection and `-x` / `--maxfail=N` stop rules. These facts are recorded in the runbook for narrow local verification and stop-after-failure discipline.

Completed local verification:

- `bd update tj-final27.9 --append-notes ...` -> passed; Beads note added, Bead remains open.
- `bd update tj-final27.9 --append-notes ...` after approved-run stop -> passed; Beads note records the blocker.
- `bd update tj-final27.9 --status blocked` -> passed.
- `bd update tj-final27.9 --status in_progress --append-notes ...` after finding SSH key -> passed.
- Controlled E2E approved subset -> passed as listed above.
- `bd update tj-final27.9 --status blocked --append-notes final E2E result` -> passed; task remains blocked for formal final acceptance on unresolved `tj-final27.4-.8` client decisions/evidence.
- `bd update tj-final27.9 --status in_progress --append-notes ...` after quality-pass approval -> passed.
- Approved bounded quality pass -> completed as listed above; final quality pending count was `0`.
- `bd update tj-final27.9 --status blocked --append-notes quality result` -> passed; task remains blocked for formal final acceptance on unresolved `tj-final27.4-.8` client decisions/evidence.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> passed, `7 passed, 0 failed`.
- `git diff --check` -> passed.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-final27/artifacts/tj-final27.9.md` -> passed, `artifact validation OK`.
- `scripts/orchestration/run_process_verification.sh` -> passed, `process verification OK`.

# Risks / Follow-ups / Explicit Defers

- The approved controlled E2E subset passed, but this is not full formal `tj-final27` closeout because approval explicitly excluded voice/audio, payment reminder sends/templates, referral live branch, feedback live branch, broad production suites, scheduled AI Quality Controls, deploy/prod config changes, and other open client-decision modules.
- Approved quality pass found a sales-experience follow-up: generic verified-policy manager-confirmation copy was safe but too weak for price objections, retention, and off-catalog redirection. This was later addressed by deployed `tj-final27.11` sales fallback and controlled text-only E2E.
- `tj-final27.4` voice/audio, `tj-final27.5` feedback, `tj-final27.6` referrals, `tj-final27.7` QA/reporting, and `tj-final27.8` nonfunctional readiness remain open unless the client explicitly excludes them.
- Zoho outbound UTM/source field mapping remains blocked on exact client-approved Zoho API field names and update policy.
- Payment reminder templates/timing/copy/enablement remain blocked on client policy; current default sends zero reminders.
- Final client acceptance still requires explicit approval for live E2E phone/channel/suffix/scenarios and zero pending synthetic conversations after the approved run.
