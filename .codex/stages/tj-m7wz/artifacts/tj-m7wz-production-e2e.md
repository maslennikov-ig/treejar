---
schema_version: orchestration-artifact/v1
artifact_type: e2e-execution
task_id: tj-m7wz-e2e
stage_id: tj-m7wz
repo: treejar
branch: codex/tj-gh42-quote-context-provenance
base_branch: origin/main
base_commit: 29d16ec8d13ef8c7fb367289a27bf49c72026bea
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh42-quote-context-provenance
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: all 15 tj-m7wz synthetic production conversations were closed and have escalation_status=none
risk_level: high
runtime_commit: 6d91fde34f85936bb018d9ac0a778a918c05c066
github_actions_run: "26404203850"
production_smoke: passed
verification:
  - gh run watch 26404203850 --exit-status: passed
  - ssh noor-server runtime readback: 6d91fde34f85936bb018d9ac0a778a918c05c066 / 26404203850
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - live bot_test quote resume path: passed, quotation Fr3306
  - live bot_test bare quantity path: passed, CH 140 quantity 5 selection confirmation
  - live bot_test reviewfix path: passed, mixed correction selected CH 140 quantity 5 and quotation Fr3307
  - synthetic cleanup query for phone fuzzy tj-m7wz: total 15, non_closed_or_escalated 0
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-m7wz/summary.md
  - .codex/stages/tj-m7wz/artifacts/tj-m7wz-local-implementation.md
  - .codex/stages/tj-m7wz/artifacts/tj-m7wz-production-e2e.md
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - none
---

# Summary

`tj-m7wz` was deployed and tested live on the user-approved number
`+79262810921`. The final production runtime is
`6d91fde34f85936bb018d9ac0a778a918c05c066`.

# Delivery Evidence

- GitHub Actions run: `26404203850`, success, including deploy.
- Runtime readback:
  - `/opt/noor/.release-sha`:
    `6d91fde34f85936bb018d9ac0a778a918c05c066`
  - `/opt/noor/.release-run-id`: `26404203850`
- Production smoke: `7 passed, 0 failed`.

# Verification

The production verification covered runtime readback, API smoke, live WhatsApp
conversation replay for quote resume, bare quantity, and the reviewer-found
mixed correction-plus-details path, production metadata readback, and cleanup
readback for synthetic conversations.

# Live E2E Matrix

Approved number: `+79262810921`.

Production Wazzup channel: `b49b1b9d-757f-4104-b56d-8f43d62cc515`.

| Scenario | Phone suffix | Conversation | Result |
| --- | --- | --- | --- |
| GH #43/#46 quote resume, GH #44/#45 field provenance | `+79262810921#tj-m7wz-resume11-20260525a` | `28bb2ce2-fc48-48e3-9e15-a67125bbd2bc` | Details reply and `Ok I can buy` both resumed 4 x CH 140 context and asked only for explicit email; explicit email created quotation `Fr3306`; no stale company/email |
| GH #41/#42 bare quantity | `+79262810921#tj-m7wz-qty-final-20260525a` | `378db845-bebf-4e14-b50c-cfdf29edeea4` | After product quantity clarification, bare `5` produced `selection-confirmation` with `Quantity: 5` for CH 140; no generic opener |
| Review-fix mixed item correction plus details | `+79262810921#tj-m7wz-reviewfix-20260525a` | `be351e49-0ea2-4769-b6d1-ccef94be0d4a` | After a prior 4 x CH 140 offer, `5 CH 140 / Lil / individual purchase / 2 street / lil.reviewfix.20260525@example.com` produced `selection-confirmation` with `Quantity: 5`; `Yes prepare the quotation` created `Fr3307`; no stale company/email |

# Production Evidence

`28bb2ce2-fc48-48e3-9e15-a67125bbd2bc`:

- Details reply model:
  `z-ai/glm-5|quote-resume-missing-details`.
- `Ok I can buy` model:
  `z-ai/glm-5|quote-resume-missing-details`.
- Email reply model: `z-ai/glm-5|quote-resume`.
- Assistant result: `Quotation Fr3306 has been prepared and sent to you.`
- `quote_customer_details`:
  `name=Lil`, `email=lil.tj.m7wz.20260525@example.com`,
  `address=2 street`, `customer_type=individual`.
- `zoho_sale_order_number`: `Fr3306`.
- `zoho_sale_order_id`: `378603000022180034`.
- `proposal_followup.kp_message_id`:
  `9a9e4243-f6f1-4431-915c-68480e85614a`.
- Metadata readback: `Test LLC` absent, `test@test.com` absent, explicit email
  present.

`378db845-bebf-4e14-b50c-cfdf29edeea4`:

- Quantity reply model: `z-ai/glm-5|selection-confirmation`.
- Assistant result included:
  `Skyland Executive office chair CH 140 black`, `Quantity: 5`,
  `Availability: 12 available`, `Unit price: 450.00 AED`.
- `pending_quote_selection.items[0]`:
  `sku=CH 140 black`, `quantity=5`,
  `display_name=Skyland Executive office chair CH 140 black`,
  `unit_price=450.0`, `currency=AED`.

`be351e49-0ea2-4769-b6d1-ccef94be0d4a`:

- Mixed correction reply model: `z-ai/glm-5|selection-confirmation`.
- Assistant result included:
  `Skyland Executive office chair CH 140 black`, `Quantity: 5`,
  `Availability: 12 available`, `Unit price: 450.00 AED`.
- `quote_customer_details` after the mixed reply:
  `name=Lil`, `email=lil.reviewfix.20260525@example.com`,
  `address=2 street`, `customer_type=individual`.
- Quotation confirmation model: `z-ai/glm-5|quote-resume`.
- Assistant result: `Quotation Fr3307 has been prepared and sent to you.`
- `zoho_sale_order_number`: `Fr3307`.
- `zoho_sale_order_id`: `378603000022179399`.
- `proposal_followup.kp_message_id`:
  `2633f0d1-1baf-484f-8c17-39a77c253b54`.
- Metadata readback: `Test LLC` absent, `test@test.com` absent, explicit email
  and `2 street` present.

# Cleanup

All 15 production synthetic conversations matching phone fuzzy `tj-m7wz` were
closed via the conversation API. Follow-up readback after cleanup:
`total=15`, `non_closed_or_escalated=0`.

# Risks / Follow-ups

No in-scope production blocker remains. The live run created a real Zoho draft
quotation `Fr3306` and final review-fix draft quotation `Fr3307` as part of
authorized E2E evidence; they were not deleted.
