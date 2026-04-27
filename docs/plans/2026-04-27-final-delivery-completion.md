# Final Delivery Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining gap between the accepted Treejar/Noor technical scope and a final client-acceptance state.

**Architecture:** Keep the current production sales bot stable and close only evidence-backed deltas from `docs/tz.md`, `docs/response-to-client-2026-02-17.md`, and the 2026-04-26 pre-launch E2E. Treat ambiguous business rules as explicit client inputs, not hidden engineering assumptions. Use stage-based delivery with Beads, isolated worktrees, focused tests, and controlled production E2E only after explicit approval.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy/Alembic, PostgreSQL/Supabase + pgvector, Redis/ARQ, PydanticAI/OpenRouter, Wazzup, Zoho CRM/Inventory, Telegram, SQLAdmin, React/Vite admin dashboard, pytest, ruff, mypy.

---

## Source Documents

- Current technical specification: `docs/tz.md`
- Commercial confirmation / offer evidence: `docs/response-to-client-2026-02-17.md`
- Historical UNION statement of work: `docs/03-ai-agent-requirements.md`
- Current launch-readiness evidence: `.codex/stages/tj-prl26/summary.md`
- Production E2E hardening evidence: `.codex/stages/tj-e2e26/summary.md`
- OpenRouter cost-control evidence: `.codex/stages/tj-ruue/summary.md`

## Final Acceptance Definition

The project reaches final-acceptance readiness when all of the following are true:

- customer-facing sales path is stable on `https://noor.starec.ai`;
- catalog discovery, exact stock/price, quotation, and order-status copy are commercially consistent;
- CRM contact/deal creation, UTM/source attribution, and returning-customer context are demonstrably connected;
- payment reminders, post-delivery feedback, voice messages, referrals, QA/reporting, and admin controls are either implemented and accepted or explicitly excluded by the client in writing;
- load/security/backup/SLA checks have fresh evidence;
- final controlled E2E covers the agreed acceptance scenarios and leaves no pending synthetic conversations;
- client handoff includes demo script, operator/admin guide links, known limits, and support window.

## Required Client Decisions Before Full Closure

These are not code blockers for planning, but they are blockers for formal final acceptance:

1. **Price truth wording:** how to present catalog price when Zoho exact price differs. Current example: catalog `264 AED`, Zoho exact `685 AED` for SKU `00-07024023`.
2. **UTM/source mapping:** which inbound fields map to Zoho CRM fields, and how repeated contacts update or preserve attribution.
3. **Payment reminder policy:** trigger event, timing, tone, stop conditions, manager handoff rules, and approved WhatsApp templates outside the 24-hour window.
4. **Referral business rules:** discounts, eligibility, expiry, abuse rules, admin/reporting expectations, and whether referrals are required for final acceptance.
5. **Production E2E permission:** exact phone/channel, allowed synthetic suffixes, and which media/voice/payment/referral scenarios can be tested live.

## Beads Mapping

Epic: `tj-final27`

| Bead | Workstream | Owner shape | Blocks final closeout |
|---|---|---|---|
| `tj-final27.1` | Commercial catalog/Zoho truth reconciliation | product + LLM + notification | yes |
| `tj-final27.2` | CRM completeness: UTM, deal stage, returning-customer context | CRM + LLM context | yes |
| `tj-final27.3` | Payment reminder and follow-up policy | follow-up + Wazzup templates | yes |
| `tj-final27.4` | Voice/audio production hardening and E2E | voice + webhook/chat | yes |
| `tj-final27.5` | Post-delivery feedback acceptance | feedback + dashboard + reports | yes |
| `tj-final27.6` | Referral business launch or explicit exclusion | referral + admin/reporting | yes, unless explicitly excluded |
| `tj-final27.7` | QA/reporting final acceptance | quality + reports + admin controls | yes |
| `tj-final27.8` | Nonfunctional readiness: load, security, backups, SLA | infra/test/docs | yes |
| `tj-final27.9` | Final acceptance pack and controlled E2E | orchestration/docs/E2E | final closeout |

## Execution Rules

- Use a dedicated branch/worktree per implementation workstream.
- Before implementation involving framework/API behavior, use Context7/docs-first and record facts in the task artifact.
- Do not deploy, mutate production config, run broad production suites, run `scripts/verify_wazzup.py`, enable scheduled AI Quality Controls, or send unsolicited media/voice tests without explicit approval.
- Use production only for approved controlled E2E. Otherwise use local tests, mocked integrations, and read-only production checks.
- Every worker must return `.codex/stages/tj-final27/artifacts/<task_id>.md` with changed files, verification, risks, and explicit defers.

---

## Task 1: Commercial Catalog/Zoho Truth Reconciliation

**Bead:** `tj-final27.1`

**Goal:** Remove the current commercial ambiguity where discovery can show catalog price but exact stock/price uses Zoho, and make mismatch behavior explicit, audited, and testable.

**Files:**

- Modify: `src/llm/engine.py`
- Modify: `src/integrations/catalog/treejar_catalog.py`
- Modify: `src/rag/pipeline.py`
- Modify: `src/services/notifications.py`
- Modify: `src/integrations/notifications/telegram.py`
- Modify: `src/templates/quotation/template.html`
- Test: `tests/test_llm_engine.py`
- Test: `tests/test_treejar_catalog.py`
- Test: `tests/test_order_review_flow.py`
- Test: `tests/test_product_images.py`
- Docs: `docs/07-knowledge-base-spec.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.1.md`

**Steps:**

1. Write failing tests for catalog/Zoho price mismatch:
   - catalog search returns product price `264`;
   - Zoho exact `get_stock` returns rate `685`;
   - bot must not present `264` as final exact price after exact stock confirmation;
   - reply must identify Zoho-confirmed final price according to the agreed copy.
2. Write failing tests for catalog item missing in Zoho:
   - product can be shown as a catalog option;
   - quotation is blocked;
   - manager escalation is created;
   - Telegram operational alert is emitted.
3. Add a small service/helper for product truth decisions if it reduces duplication. Keep it narrow; do not invent a new product subsystem.
4. Update `search_products`, `get_stock`, and `create_quotation` contracts so the LLM receives unambiguous instructions:
   - catalog price is discovery/marketing data unless explicitly confirmed;
   - Zoho exact price/stock is used before exact promises and quotation;
   - mismatch requires clear copy and, when appropriate, manager handoff.
5. Update quotation template/caption if needed so PDFs use only Zoho-confirmed rates.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_llm_engine.py tests/test_treejar_catalog.py tests/test_order_review_flow.py tests/test_product_images.py -q`
7. Run quality gates:
   - `uv run ruff check src/ tests/`
   - `uv run ruff format --check src/ tests/`
   - `uv run mypy src/`
   - `git diff --check`

**Acceptance:**

- SKU `00-07024023` style mismatch has deterministic copy.
- Quotation never uses catalog-only or stale price as final exact price.
- Catalog-only products do not generate SaleOrder automatically.

---

## Task 2: CRM Completeness

**Bead:** `tj-final27.2`

**Goal:** Close CRM gaps from the TЗ: UTM/source mapping, deal-stage consistency, and returning-customer context.

**Files:**

- Modify: `src/integrations/crm/zoho_crm.py`
- Modify: `src/services/customer_identity.py`
- Modify: `src/llm/context.py`
- Modify: `src/llm/engine.py`
- Modify: `src/api/v1/crm.py`
- Modify: `src/models/conversation.py` if extra durable fields are required
- Migration: `migrations/versions/<date>_add_crm_context_fields.py` only if durable fields are required
- Test: `tests/test_zoho_crm.py`
- Test: `tests/test_customer_identity.py`
- Test: `tests/test_llm_context.py`
- Test: `tests/test_llm_engine.py`
- Test: `tests/test_api_crm.py`
- Docs: `docs/admin-guide.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.2.md`

**Steps:**

1. Confirm with client the UTM/source field mapping before implementation. If not confirmed, implement only safe storage and mark outbound Zoho mapping blocked.
2. Write failing tests for contact creation with source/UTM fields.
3. Write failing tests for returning customer context:
   - contact found by phone;
   - segment/name are injected into owner/admin context;
   - LLM prompt/history receives concise purchase/deal context when available.
4. Extend CRM client methods only where current Zoho API calls already support it. Avoid broad Zoho SDK adoption.
5. Add bounded CRM context summarization to avoid large prompt growth.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_zoho_crm.py tests/test_customer_identity.py tests/test_llm_context.py tests/test_llm_engine.py tests/test_api_crm.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- New contact/deal data includes agreed source attribution.
- Returning-customer context is present but bounded.
- Existing customers do not lose original attribution unless policy says so.

---

## Task 3: Payment Reminder And Follow-Up Policy

**Bead:** `tj-final27.3`

**Goal:** Turn the existing follow-up machinery into an accepted payment-reminder flow that respects WhatsApp 24-hour rules and client-approved templates.

**Files:**

- Modify: `src/services/followup.py`
- Modify: `src/integrations/messaging/wazzup.py`
- Modify: `src/core/config.py`
- Modify: `src/api/v1/admin.py`
- Modify: `frontend/admin/src/components/OperatorCenter.tsx`
- Test: `tests/test_services_followup.py`
- Test: `tests/test_services_followup_details.py`
- Test: `tests/test_messaging_wazzup.py`
- Test: `tests/test_api_admin.py`
- Docs: `docs/admin-guide.md`
- Docs: `docs/04-sales-dialogue-guidelines.md` if copy is agreed
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.3.md`

**Dependencies:** depends on `tj-final27.2` for reliable deal/order state.

**Steps:**

1. Record client-approved payment reminder policy in the artifact before coding.
2. Write failing tests for:
   - unpaid/approved order candidate selection;
   - stop conditions after payment/rejection/manual takeover;
   - template-only behavior outside 24-hour window;
   - no reminder when policy is disabled.
3. Add SystemConfig/admin settings for reminder mode, limits, templates, and daily caps.
4. Ensure Wazzup template sends include deterministic `crmMessageId`.
5. Add outbound audit rows for reminder text/template sends.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_services_followup.py tests/test_services_followup_details.py tests/test_messaging_wazzup.py tests/test_api_admin.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- Disabled mode sends zero reminders.
- Manual/daily scheduled modes are explicit and capped.
- Out-of-window messages use approved template IDs only.

---

## Task 4: Voice/Audio Production Hardening

**Bead:** `tj-final27.4`

**Goal:** Move voice/audio from code-complete to acceptance-ready with cost limits, fallback copy, audit visibility, and controlled E2E.

**Files:**

- Modify: `src/integrations/voice/voxtral.py`
- Modify: `src/services/chat.py`
- Modify: `src/llm/safety.py`
- Modify: `src/models/message.py` only if audit fields are insufficient
- Test: `tests/test_voxtral.py`
- Test: `tests/test_webhook_audio.py`
- Test: `tests/test_services_chat.py`
- Test: `tests/test_llm_safety.py`
- Docs: `docs/testing/manual-test-checklist.md`
- Prompt: `docs/prompts/2026-04-27-final-voice-e2e-agent.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.4.md`

**Steps:**

1. Use Context7/OpenRouter/OpenAI-compatible docs if request payload behavior or model settings are touched.
2. Write failing tests for provider-side max tokens, timeout, max audio size, and safe fallback.
3. Ensure transcription path uses a non-core model route and logs usage/cost when available.
4. Persist audio URL/transcription and show it in admin where messages are inspected.
5. Prepare a controlled voice E2E prompt, but do not run live voice tests without explicit approval.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_voxtral.py tests/test_webhook_audio.py tests/test_services_chat.py tests/test_llm_safety.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- English/Arabic voice unit coverage passes.
- Oversized/unreadable audio fails gracefully and does not trigger runaway cost.
- Live voice E2E is either passed or explicitly deferred by client approval status.

---

## Task 5: Post-Delivery Feedback Acceptance

**Bead:** `tj-final27.5`

**Goal:** Make post-delivery feedback demonstrable end-to-end, not only model/service-complete.

**Files:**

- Modify: `src/services/followup.py`
- Modify: `src/llm/engine.py`
- Modify: `src/api/admin/views.py`
- Modify: `src/services/dashboard_metrics.py`
- Modify: `frontend/admin/src/components/OperatorCenter.tsx`
- Test: `tests/test_feedback_model.py`
- Test: `tests/test_feedback_integration.py`
- Test: `tests/test_dashboard_manager.py`
- Test: `tests/test_services_followup.py`
- Docs: `docs/admin-guide.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.5.md`

**Steps:**

1. Write failing tests for feedback request candidate selection from delivered deals.
2. Write failing tests for duplicate protection and dashboard visibility.
3. Ensure feedback request sends are audited with deterministic `crmMessageId`.
4. Ensure `save_feedback` is only available in the correct conversation stage or explicit feedback context.
5. Add admin/operator readout for feedback count, recommendation rate, and recent feedback rows if missing.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_feedback_model.py tests/test_feedback_integration.py tests/test_dashboard_manager.py tests/test_services_followup.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- Delivered deal can trigger one feedback request.
- Customer feedback can be saved once and shown in admin metrics.
- No feedback request is sent for rejected/inactive/no-order conversations.

---

## Task 6: Referral Business Launch Or Explicit Exclusion

**Bead:** `tj-final27.6`

**Goal:** Either make referrals business-ready according to approved rules or formally exclude/refile them from final acceptance.

**Files:**

- Modify: `src/services/referrals.py`
- Modify: `src/api/v1/referrals.py`
- Modify: `src/llm/engine.py`
- Modify: `src/api/admin/views.py`
- Modify: `frontend/admin/src/components/OperatorCenter.tsx`
- Test: `tests/test_referrals.py`
- Test: `tests/test_api_admin.py`
- Test: `tests/test_llm_engine.py`
- Docs: `docs/admin-guide.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.6.md`

**Steps:**

1. Ask for or record referral policy: discount, expiry, eligibility, abuse checks, reporting, launch status.
2. If policy is not approved, update docs/artifact to mark referrals as an explicit client-deferred business module and do not expand code.
3. If approved, write failing tests for the policy.
4. Add admin visibility/actions only to the extent required by the approved policy.
5. Ensure LLM tool cannot apply referrals silently without customer-visible confirmation.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_referrals.py tests/test_api_admin.py tests/test_llm_engine.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- Referral behavior matches approved business rules, or the module is explicitly excluded from final acceptance.

---

## Task 7: QA/Reporting Final Acceptance

**Bead:** `tj-final27.7`

**Goal:** Prove quality review, manager review, owner reports, and AI Quality Controls work in an acceptance-safe configuration.

**Files:**

- Modify: `src/quality/job.py`
- Modify: `src/quality/manager_job.py`
- Modify: `src/services/reports.py`
- Modify: `src/services/daily_summary.py`
- Modify: `src/api/v1/admin.py`
- Modify: `frontend/admin/src/components/AIQualityControlsPanel.tsx`
- Test: `tests/test_quality_job.py`
- Test: `tests/test_manager_job.py`
- Test: `tests/test_reports.py`
- Test: `tests/test_reports_manager.py`
- Test: `tests/test_api_admin.py`
- Docs: `docs/admin-guide.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.7.md`

**Steps:**

1. Keep scheduled AI Quality Controls disabled by default.
2. Write failing tests for manual/daily sample acceptance mode:
   - budget respected;
   - summary transcript mode used;
   - no full transcript unless explicit override;
   - usage fields persisted.
3. Add a tiny manual acceptance runbook for bot QA, manager QA, and report generation.
4. Run mocked integration tests for reports and Telegram documents.
5. If live manual QA sample is desired, request explicit approval before running.
6. Run targeted tests:
   - `uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_reports.py tests/test_reports_manager.py tests/test_api_admin.py -q`
7. Run ruff/format/mypy/diff checks.

**Acceptance:**

- Owner can run manual QA/report checks safely.
- Scheduled QA remains off unless explicitly enabled.
- Reports include bot, manager, conversion/refusal, feedback, and cost-control fields.

---

## Task 8: Nonfunctional Readiness

**Bead:** `tj-final27.8`

**Goal:** Produce evidence for the nonfunctional promises: response time, availability posture, concurrency, backups, and security.

**Files:**

- Modify or create: `scripts/load_test_conversations.py` if no suitable harness exists
- Modify: `scripts/verify_api.py`
- Modify: `tests/test_security_extended.py`
- Modify: `tests/test_infra_contract.py`
- Modify: `.github/workflows/ci.yml` only if CI coverage is missing
- Docs: `docs/admin-guide.md`
- Docs: `docs/dev-guide.md`
- Docs: `docs/client/final-readiness-nonfunctional.md`
- Artifact: `.codex/stages/tj-final27/artifacts/tj-final27.8.md`

**Steps:**

1. Define measurable thresholds:
   - API health and admin auth guards;
   - webhook ack path;
   - queue/backpressure behavior;
   - backup evidence;
   - no tracked secrets;
   - known local pytest capture workaround.
2. Add or update local load harness for mocked inbound batches. Do not send broad live traffic.
3. Add tests for security regressions:
   - admin/dashboard/conversations auth;
   - product sync protected;
   - Wazzup channel/IP guard where configured;
   - no API-key bypass in admin tests.
4. Collect read-only production evidence for release SHA, Alembic head, health, and auth guards.
5. Run:
   - `uv run --extra dev python -m pytest -s tests/test_security.py tests/test_security_extended.py tests/test_infra_contract.py tests/test_scripts_verify_api.py -q`
   - `uv run ruff check src/ tests/ scripts/`
   - `uv run ruff format --check src/ tests/ scripts/`
   - `uv run mypy src/`
6. Record backup/SLA evidence or explicit hosting limitation.

**Acceptance:**

- Security and auth boundaries have fresh tests.
- Load/concurrency claim is either proven with a bounded harness or restated with measured limits.
- Backup and monitoring expectations are documented with evidence.

---

## Task 9: Final Acceptance Pack And Controlled E2E

**Bead:** `tj-final27.9`

**Goal:** Close the project with a client-ready acceptance package, final E2E evidence, and a clean handoff.

**Files:**

- Create: `docs/client/final-acceptance-report-2026-04-27.md`
- Create: `docs/prompts/2026-04-27-final-acceptance-e2e-agent.md`
- Modify: `.codex/handoff.md`
- Modify: `.codex/stages/tj-final27/summary.md`
- Create artifacts for final run under: `.codex/stages/tj-final27/artifacts/`
- Test/verify: repo-local closeout commands

**Dependencies:** blocked by `tj-final27.1` through `tj-final27.8`, except any module explicitly excluded by client decision and recorded in Beads/handoff.

**Steps:**

1. Confirm all upstream Beads are closed or explicitly excluded.
2. Prepare final E2E prompt covering:
   - customer discovery and product recommendation;
   - exact stock/price and catalog/Zoho mismatch copy;
   - quotation approve/reject;
   - order status;
   - manager handoff/private reply;
   - voice message if approved;
   - feedback if a delivered-state test fixture is approved;
   - referral if approved;
   - admin read-only checks and cost-control defaults.
3. Ask for explicit approval before live production E2E.
4. Run local full verification:
   - `PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-final27`
   - `scripts/orchestration/run_process_verification.sh`
   - `git diff --check`
5. Prepare final client-facing report:
   - what was promised;
   - what was delivered;
   - evidence links;
   - accepted exclusions;
   - support period and operating guide.
6. Update `.codex/handoff.md` with final status and remaining support window.

**Acceptance:**

- Final acceptance report is client-readable.
- Final E2E leaves zero pending synthetic conversations.
- No silent defers remain.

---

## Suggested Parallelization

Start with `tj-final27.1` and `tj-final27.2`; they remove the most important acceptance ambiguity. After `tj-final27.2`, run `tj-final27.3`. In parallel, `tj-final27.4`, `tj-final27.5`, `tj-final27.6`, `tj-final27.7`, and `tj-final27.8` can proceed in separate worktrees because their write zones are mostly distinct. `tj-final27.9` is final closeout only.

## Verification Baseline

Every implementation task should run its targeted tests plus:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
git diff --check
```

Before final closeout:

```bash
PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-final27
scripts/orchestration/run_process_verification.sh
```
