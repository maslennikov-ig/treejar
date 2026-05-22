---
schema_version: orchestration-artifact/v1
artifact_type: e2e-execution
task_id: tj-gh22.1
stage_id: tj-gh22
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: ec3a7829b1511a4db25ea8aa210d0b3219cf845d
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: blocked
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: live synthetic sends were executed after user approval; three synthetic conversations now show pending exact-quote escalation and should be cleaned or resolved during tj-gh23/tj-gh22.1 continuation
risk_level: high
runtime_commit: 3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6
current_main_commit: ec3a7829b1511a4db25ea8aa210d0b3219cf845d
github_actions_run: "26233690578"
production_smoke: passed
verification:
  - git status --short --branch: primary checkout dirty on unrelated codex/tj-gh12-name-gate-hotfix; isolated worktree clean
  - gh run view 26233690578 --json databaseId,headSha,headBranch,event,status,conclusion,jobs: passed; deploy job succeeded
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - OPENROUTER_API_KEY=dummy uv run pytest <targeted follow-up/regression pack> -v --tb=short: passed (53 passed)
  - production DB read-only conversation query: passed via ssh noor-server/docker compose after user confirmed access
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md
  - .codex/stages/tj-gh22/summary.md
  - .codex/handoff.md
explicit_defers:
  - GitHub #11 must remain open while live E2E and WABA/template blockers remain
  - Live WhatsApp E2E now requires tj-gh23 exact-quotation hardening before post-quotation follow-up can be validated
  - FU1 live send requires confirmed EN/AR free-form text configuration
  - FU2/FU3 live sends require approved Wazzup WABA EN/AR template ids/codes and confirmed template transport
---

# Summary

Controlled production E2E execution was started for `tj-gh22.1` on 2026-05-21.
S0 production smoke passed against `https://noor.starec.ai`.

After the user confirmed permissions and the approved test number
`+79262810921`, live synthetic sends were executed. The run did not reach the
post-quotation follow-up scenarios because exact quotation creation failed first:
quote-ready customer requests ended in `exact-quote-fallback` and pending
manager escalation.

The product/SKU name-gate sanity path passed. The blocker is now tracked as
new Beads stage `tj-gh23`.

# Verification

- `gh run view 26233690578 --json databaseId,headSha,headBranch,event,status,conclusion,jobs`
  confirmed successful CI/deploy for runtime commit
  `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  passed with `7 passed, 0 failed`.
- The targeted local follow-up/regression pack passed with `53 passed`.
- Production DB readback passed via `ssh noor-server` and `docker compose exec`
  inside `/opt/noor`.
- `uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh22/artifacts/tj-gh22.1-e2e-execution.md`
  passed with `artifact validation OK`.
- `scripts/orchestration/run_process_verification.sh` passed with
  `process verification OK`.

# Runtime And Deployment Evidence

- Current isolated worktree: `/home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge`.
- Worktree branch: `codex/tj-gh22-fu1-service-window`.
- Worktree `HEAD` / `origin/main`: `ec3a7829b1511a4db25ea8aa210d0b3219cf845d`.
- Runtime commit under test: `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`.
- `ec3a7829b1511a4db25ea8aa210d0b3219cf845d` is a docs/evidence-only commit on top of the deployed runtime commit.
- GitHub Actions run `26233690578`:
  - event: `workflow_dispatch`
  - branch: `main`
  - head SHA: `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6`
  - conclusion: `success`
  - deploy job: `success`
- Fresh production smoke:
  - command: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  - result: `7 passed, 0 failed`
  - health: `/api/v1/health -> 200`
  - products: `/api/v1/products/ -> 200`
  - conversations auth guard: `/api/v1/conversations/ -> 403`
  - quality auth guard: `/api/v1/quality/reviews/ -> 403`
  - webhook reachable: `/api/v1/webhook/wazzup -> 200`
  - admin panel reachable: `/admin/ -> 200`
  - metrics auth guard: `/api/v1/admin/metrics/ -> 401`

# Approval And Access State

- Approved phone from the task prompt: `+79262810921`.
- Required synthetic suffix pattern from the task prompt: `79262810921#tj-gh22-<scenario>-<timestamp>`.
- Exact production Wazzup channel id used by `scripts/bot_test.py`: `b49b1b9d-757f-4104-b56d-8f43d62cc515`.
- Approved production test window: user confirmed permissions in the current task before live sends.
- Worktree environment:
  - `WAZZUP_TEST_CHANNEL_ID`: missing
  - `BOT_TEST_API_KEY`: missing
  - `API_KEY`: missing
  - `DATABASE_URL`: missing
  - `SUPABASE_DB_URL`: missing
- Primary checkout `.env` exists and contains `WAZZUP_CHANNEL_ID`, `WAZZUP_API_KEY`,
  `DATABASE_URL`, and `DATABASE_URL_DIRECT`, but no `API_KEY` or
  `BOT_TEST_API_KEY` was present. The channel value was not printed or used for
  live sends because the current task did not confirm the exact channel id.

# Scenario Matrix

| Scenario | Status | Evidence |
| --- | --- | --- |
| S0 production smoke | executed, passed | `verify_api.py` returned `7 passed, 0 failed`; GitHub Actions run `26233690578` deploy succeeded |
| S1 quotation send prompt | executed, failed before quotation creation | exact quote requests ended in `exact-quote-fallback` with pending escalation; tracked as `tj-gh23` |
| S2 pre-acceptance question | blocked by S1 | cannot test post-quotation behavior until quotation creation succeeds |
| S3 acceptance handoff | blocked live; locally covered | live blocked; local regression `test_process_message_post_quotation_acceptance_hands_off_to_manager` passed |
| S4 rejection/objection | blocked live; locally covered | live blocked; local proposal follow-up rejection tests passed |
| S5 any customer reply stops follow-up | blocked live; locally covered | live blocked; local `meaningful_customer_reply`, `short_customer_reply`, and webhook read-status tests passed |
| S6 FU1 inside service window | blocked live; locally covered | live blocked; local FU1 free-form in-window test passed; production FU1 EN/AR free-form config could not be read back |
| S7 FU1 outside window with fallback template | blocked by WABA setup/readback | no approved FU1 fallback template id/code supplied; DB config readback unavailable |
| S8 FU1 outside window without fallback | blocked by readback | code path locally covered by missing-template tests; production config/count readback unavailable |
| S9 FU2/FU3 templates | blocked by WABA setup | no approved FU2/FU3 Wazzup WABA EN/AR template ids/codes supplied; no free-form send attempted |
| S10 Arabic follow-up | blocked by config/template setup | Arabic local language normalization tests passed; production Arabic FU config/template readback unavailable |
| S11 no response final status | blocked live; locally covered | live time-based/template path blocked; local final no-response test passed |
| S12 regression pack | locally executed; production quote replay failed | targeted local pack passed `53 passed`; production replay found missing exact-quote coverage |

# Scenario Identifiers And Data Rows

- Live synthetic suffixes used:
  - `79262810921#tj-gh22-quote-20260521165301`
  - `79262810921#tj-gh22-quote-num-20260521165301`
  - `79262810921#tj-gh22-product-20260521165301`
- Conversation ids created/read for this run:
  - `baa857a8-cc87-4d4f-85c3-aa5a746fcbc1`
  - `d6fa2284-0029-4019-b304-285e9d352e6f`
  - `c11ac597-9452-4e79-8dd9-50261dbcd768`
- Quotation ids/numbers created/read for this run: none; exact quote flow failed before quotation creation.
- Outbound audit rows for text replies were created by normal production send flow; no quotation PDF/template send was reached.
- `proposal_followup` metadata before/after: not available from production; local tests covered metadata initialization, stopping, FU send planning, template blocking, FU1 free-form send, and final no-response marking.
- Provider message ids / `crmMessageId`: none created live; local tests verified deterministic proposal-followup `crmMessageId` and provider id recording.
- Manager handoff/escalation rows: pending exact-quote escalations were created for the three synthetic conversations. This is the live blocker and should be cleaned or resolved in the `tj-gh23` continuation.
- Cleanup: not performed during root-cause investigation; do not claim `tj-gh22.1` complete until synthetic pending state is cleaned or explicitly documented after the fix.

# Supporting Local Regression Pack

Command:

```bash
OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py tests/test_webhook.py::test_wazzup_webhook_read_status_records_proposal_read_without_reschedule tests/test_response_adapter.py tests/test_outbound_audit.py::test_send_wazzup_media_with_audit_can_audit_caption_without_sending_it tests/test_outbound_audit.py::test_send_wazzup_media_with_audit_detailed_provider_suppresses_caption_send tests/test_messaging_wazzup.py::test_send_template_strips_smoke_profile_suffix_from_chat_id tests/test_llm_engine.py::test_process_message_post_quotation_acceptance_hands_off_to_manager tests/test_llm_engine.py::test_post_quotation_generic_ok_after_non_approval_answer_does_not_handoff tests/test_llm_engine.py::test_post_quotation_acceptance_runs_before_dialogue_kernel_enforce tests/test_llm_engine.py::test_process_message_first_turn_unknown_name_blocks_exact_sku_side_effects tests/test_llm_engine.py::test_process_message_name_only_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_bare_name_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_extract_purchase_selection_accepts_generic_sku_spacing_variants tests/test_llm_engine.py::test_process_message_ch616_selection_confirms_without_manager_handoff tests/test_llm_engine.py::test_process_message_novo_model_number_does_not_become_chair_quantity tests/test_llm_engine.py::test_process_message_customer_details_resume_pending_quote_selection tests/test_llm_engine.py::test_process_message_terse_details_preserves_pending_quote_context tests/test_llm_engine.py::test_process_message_confirms_selection_from_prior_product_media_captions tests/test_llm_engine.py::test_process_message_exact_quote_missing_details_returns_gate_without_escalation tests/test_llm_engine.py::test_process_message_brand_quantity_selection_stays_on_product_path tests/test_llm_engine.py::test_process_message_short_yes_after_assembly_question_escalates_without_generic_fallback -v --tb=short
```

Result: `53 passed`.

Coverage included:

- post-quotation approval handoff and generic `ok` non-approval guard;
- follow-up metadata scheduling, read status handling, reply/rejection stop rules,
  FU1 free-form in-window behavior, template-only/blocked out-of-window paths,
  and final no-response marking;
- English/Arabic language normalization with no Russian follow-up output;
- #36 name-gate request resume;
- #37 product quantity no over-escalation;
- #39 SKU variants and selection after product options;
- #40 quote context and NOVO model-number quantity guard;
- #35 product media hidden caption audit without customer-visible duplicate caption;
- long-dialog memory/context cases represented by quote-context and product-selection
  regression tests.

# Risks / Follow-ups

## Blockers

1. Exact quotation creation is blocked by `tj-gh23` root causes: quote intent is
   not converted into a durable frame, CH 616 catalog suffix SKUs do not resolve
   reliably in the exact-quote path, natural delivered-to addresses are not
   stored, and resolver uncertainty escalates to manager instead of asking a
   narrow customer clarification.
2. FU1 EN/AR free-form text configuration was not supplied in the task and still
   needs explicit production confirmation before FU1 live send validation.
3. FU2/FU3 approved Wazzup WABA EN/AR template ids/codes were not supplied.
   FU2/FU3 were not and must not be sent as free-form messages.
4. Synthetic pending exact-quote escalations from this investigation must be
   cleaned or resolved before claiming live E2E completion.

# Conclusion

S0 passed. The full production E2E is not passed. It is blocked because exact
quotation creation fails before the post-quotation state can be exercised.
GitHub #11 should not be closed until `tj-gh23` is fixed and the post-quotation
E2E matrix passes.
