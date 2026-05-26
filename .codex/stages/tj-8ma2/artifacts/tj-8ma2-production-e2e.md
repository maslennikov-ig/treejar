---
schema_version: orchestration-artifact/v1
artifact_type: e2e-execution
task_id: tj-8ma2
stage_id: tj-8ma2
repo: treejar
branch: main
base_branch: origin/main
base_commit: bc03a8fdb5db71744c5ce6ad18d963a3ebc24063
worktree: /home/me/code/treejar
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: four tj-8ma2 synthetic conversations closed; two pending synthetic escalations resolved; active=0 and pending escalations=0 after cleanup
risk_level: high
runtime_commit: 80e6f4371da44f163406f76f30f858e94d35da4a
github_actions_run: "26462939020"
production_smoke: passed
verification:
  - gh run view 26462939020: success, deploy included
  - ssh noor-server runtime readback: 80e6f4371da44f163406f76f30f858e94d35da4a / 26462939020
  - curl https://noor.starec.ai/api/v1/health: passed
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed, 8 passed / 0 failed
  - live exact quote control conversation d8a82c9a-99fb-4823-aca4-d0ab360c67d0: quotation Fr3315 created
  - live sales-order target conversation bdee58ee-8b56-414e-96bc-55de1b659a77: pending sales-order selection preserved through customer brief; details stored; no unresolved item reinterpretation
  - production log readback: create_quotation called with CH 620 grey x5 before separate Zoho Inventory create_contact HTTP 400 fallback
  - synthetic cleanup query for phone fuzzy tj-8ma2: total 4, active 0, pending escalations 0
  - scripts/orchestration/run_stage_closeout.py --stage tj-8ma2: passed after temporary npm ci restored frontend/admin esbuild; full pytest 1180 passed / 19 skipped
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-8ma2/summary.md
  - .codex/stages/tj-8ma2/artifacts/tj-8ma2-local-implementation.md
  - .codex/stages/tj-8ma2/artifacts/tj-8ma2-production-e2e.md
explicit_defers:
  - tj-4xnf remains open for Zoho Inventory create_contact HTTP 400 customer-resolution fallback
  - tj-nzob remains open for comma-separated ordered brief company parsing
---

# Summary

`tj-8ma2` was merged into `main`, pushed, deployed, smoke-tested on
production, and live-E2E checked with synthetic WhatsApp profiles on the
approved owner number. The target state-machine bug is fixed in production:
after the customer clarified `5 x CH 620 grey`, the following customer brief was
stored as customer details and did not overwrite the item selection.

# Verification

- GitHub Actions run `26462939020`: success, deploy included.
- Production runtime readback:
  - `/opt/noor/.release-sha`:
    `80e6f4371da44f163406f76f30f858e94d35da4a`
  - `/opt/noor/.release-run-id`: `26462939020`
- Production smoke:
  - `/api/v1/health`: healthy.
  - `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`:
    `8 passed, 0 failed`.
- Later closeout commit `49670bbea9cfb54bc4c1fe6f51b2f90c8934a411` changed
  only `.codex` orchestration files. The push was path-ignored by CI and did
  not redeploy; production remains on code commit `80e6f43`.

# Live E2E Evidence

Approved number: `+79262810921`.

Synthetic profiles:

| Scenario | Conversation | Result |
| --- | --- | --- |
| Exact quote control | `d8a82c9a-99fb-4823-aca4-d0ab360c67d0` | Created `Quotation Fr3315`; this was a control for the general exact quote path, not the target sales-order path |
| Smoke-marker sales-order parser guard | `c96dbcea-5c17-464d-84a3-5eca51e08608` | Polluted by the smoke marker and closed during cleanup; no product acceptance evidence |
| No-marker sales-order attempt | `ad70253f-767d-45bd-86fa-7af3fb2e129c` | Polluted/escalated after a name-gate persistence issue and closed during cleanup; no product acceptance evidence |
| Target mixed sales-order path | `bdee58ee-8b56-414e-96bc-55de1b659a77` | Passed the `tj-8ma2` acceptance; then hit separate Zoho Inventory customer-resolution fallback tracked as `tj-4xnf` |

Target conversation `bdee58ee-8b56-414e-96bc-55de1b659a77`:

- After `sales order 5 x CH 620`, bot asked to confirm the exact catalog item.
- After `5 x CH 620 grey`, bot asked only for customer quotation details.
- Production metadata preserved:
  `pending_quote_selection.source=sales_order_quote`,
  `items=[{"sku": "CH 620 grey", "quantity": 5}]`, and
  `unresolved_items=[]`.
- After multiline details `Lilia / LLD / Lfdsf@kfsl.ru / 2 street`,
  production metadata stored:
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, `address=2 street`.
- The customer brief was not converted into a new unresolved item such as
  `5 x Lilia ...`.

# Risks / Follow-ups

The target conversation then reached
`create_quotation(items=[QuotationItem(sku='CH 620 grey', quantity=5)])`, but
Zoho Inventory customer resolution failed:

- phone lookup returned no existing customer;
- email lookup returned no existing customer;
- `POST /contacts` returned HTTP 400;
- duplicate-name fallback did not recover;
- the bot fail-closed and created a manager escalation.

This is a separate exact quotation customer-resolution bug and is tracked under
`tj-4xnf`.

# Cleanup

Four production synthetic conversations matching phone fuzzy `tj-8ma2` were
closed and two pending synthetic escalations were marked resolved.

Cleanup readback:

- `closed_conversations=4`
- `resolved_escalations=2`
- `remaining_active=0`
- `remaining_pending_escalations=0`

Temporary local dependencies and caches created for closeout were removed after
verification, including `.venv`, `frontend/admin/node_modules`, pytest/mypy/ruff
caches, `tmp`, and `__pycache__` directories.

# Closeout Decision

Core `tj-8ma2` acceptance is verified in production and the Bead is closed.
Full quote finalization for the sales-order path remains blocked by `tj-4xnf`,
not by the `tj-8ma2` state-preservation fix.
