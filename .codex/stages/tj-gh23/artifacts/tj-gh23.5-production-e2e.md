---
schema_version: orchestration-artifact/v1
artifact_type: e2e-execution
task_id: tj-gh23.5
stage_id: tj-gh23
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: ec3a7829b1511a4db25ea8aa210d0b3219cf845d
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: old tj-gh22 synthetic escalations were already resolved; new tj-gh23 synthetic conversations were closed and the expected approval handoff escalation was resolved after evidence capture
risk_level: high
runtime_commit: 322bee30d667b245a143813dbd5fccbcf120eecf
github_actions_run: "26279825756"
production_smoke: passed
verification:
  - scripts/orchestration/run_stage_closeout.py --stage tj-gh23: passed before delivery (1127 passed, 19 skipped)
  - git push origin HEAD:main: pushed ffad8fb939323baffe3776f9a95050a172fd05c8 and 322bee30d667b245a143813dbd5fccbcf120eecf to main
  - gh run watch 26279825756 --exit-status: passed
  - ssh noor-server 'cat /opt/noor/.release-sha && cat /opt/noor/.release-run-id': 322bee30d667b245a143813dbd5fccbcf120eecf / 26279825756
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - live bot_test word-quantity exact product path: passed, quotation Fr3294, no unexpected escalation
  - live bot_test numeric exact product path: passed, quotation Fr3295, no unexpected escalation
  - live bot_test ambiguous CH 616 path: passed, exact item clarification, no escalation
  - live bot_test post-quotation approval: passed, expected manager handoff then cleaned
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-gh22/summary.md
  - .codex/stages/tj-gh23/summary.md
  - .codex/stages/tj-gh23/artifacts/tj-gh23.5-production-e2e.md
  - src/dialogue/catalog_refs.py
  - src/llm/engine.py
  - tests/test_dialogue_catalog_refs.py
  - tests/test_llm_engine.py
explicit_defers:
  - GitHub #11 remains open until the full post-quotation follow-up matrix is executed.
  - FU1 live follow-up still needs confirmed EN/AR free-form text configuration.
  - FU2/FU3 live follow-up still needs approved Wazzup WABA EN/AR template ids/codes.
  - Pre-acceptance delivery-question content quality needs follow-up under tj-gh22.1: it avoided escalation but answered with a generic quotation clarification.
---

# Summary

`tj-gh23` was merged, deployed, and live-tested on the user-approved number
`+79262810921`.

The original live blocker is fixed: quote-ready exact product requests now pass
through name gate and create quotations instead of falling into
`exact-quote-fallback` and pending manager escalation.

# Verification

- `scripts/orchestration/run_stage_closeout.py --stage tj-gh23` passed before
  delivery with `1127 passed, 19 skipped`.
- GitHub Actions run `26279825756` completed successfully, including deploy.
- Server readback confirmed runtime
  `322bee30d667b245a143813dbd5fccbcf120eecf`.
- Production smoke passed: `7 passed, 0 failed`.
- Live E2E scenarios for word quantity, numeric quantity, ambiguous CH 616,
  and post-quotation approval are recorded below.

# Delivery Evidence

- Final production runtime: `322bee30d667b245a143813dbd5fccbcf120eecf`.
- GitHub Actions run: `26279825756`.
- Deploy job: success.
- Server readback:
  - `/opt/noor/.release-sha` -> `322bee30d667b245a143813dbd5fccbcf120eecf`
  - `/opt/noor/.release-run-id` -> `26279825756`
- Production smoke:
  - `uv run python scripts/verify_api.py --base-url https://noor.starec.ai`
  - result: `7 passed, 0 failed`

# Live E2E Matrix

Approved number: `+79262810921`.

Production Wazzup channel: `b49b1b9d-757f-4104-b56d-8f43d62cc515`.

| Scenario | Phone suffix | Conversation | Result |
| --- | --- | --- | --- |
| Word quantity exact product | `+79262810921#tj-gh23-word2-20260522a` | `cf9f4ade-b261-4f56-b104-69062f861cdd` | name gate -> `exact-quote-deterministic`; quotation `Fr3294`; no unexpected escalation |
| Numeric exact product | `+79262810921#tj-gh23-num-20260522a` | `e3d30ece-31b5-46a2-a948-dd10096a4bb7` | name gate -> `exact-quote-deterministic`; quotation `Fr3295`; no escalation |
| Ambiguous CH 616 stem | `+79262810921#tj-gh23-ambig2-20260522a` | `c397b396-b63a-4050-87b6-6b41eab72bea` | name gate -> `exact-quote-clarify-item`; asks exact item/SKU; no escalation |
| Post-quotation question | `+79262810921#tj-gh23-word2-20260522a` | `cf9f4ade-b261-4f56-b104-69062f861cdd` | `proposal-clarify`; no escalation, but reply quality is weak |
| Post-quotation approval | `+79262810921#tj-gh23-word2-20260522a` | `cf9f4ade-b261-4f56-b104-69062f861cdd` | `post-quotation-accepted`; quotation approved; follow-up stopped; expected manager handoff created and then resolved during cleanup |

# Production DB Evidence

`cf9f4ade-b261-4f56-b104-69062f861cdd`:

- `quote_customer_details`: `address=Office 1201, Business Bay, Dubai`,
  `customer_type=individual`, `name=Alex`.
- `zoho_sale_order_number`: `Fr3294`.
- `zoho_sale_order_id`: `378603000022164119`.
- `quotation_decision_status`: `approved`.
- `proposal_followup.kp_message_id`: `7e23c6d0-03db-45fd-98d5-b35dfaa03b67`.
- `proposal_followup.chain_stopped`: `true`.
- `proposal_followup.stop_reason`: `quotation_accepted`.
- Text outbound audit rows: 4, all `sent`.

`e3d30ece-31b5-46a2-a948-dd10096a4bb7`:

- `quote_customer_details`: `address=Office 1203, Business Bay, Dubai`,
  `customer_type=individual`, `name=Alex`.
- `zoho_sale_order_number`: `Fr3295`.
- `zoho_sale_order_id`: `378603000022160881`.
- `quotation_decision_status`: `pending`.
- `proposal_followup.kp_message_id`: `5090b7fd-5102-4f38-ab6c-2c3f31930535`.
- Text outbound audit rows: 2, all `sent`.

`c397b396-b63a-4050-87b6-6b41eab72bea`:

- `quote_customer_details`: `address=Office 1202, Business Bay, Dubai`,
  `customer_type=individual`, `name=Alex`.
- `pending_quote_selection.source`: `exact_quote`.
- `pending_quote_selection.unresolved_items`: `sku=CH-616`, `quantity=1`,
  `item_candidate=CH 616 chair`.
- Escalations: 0.

PDF/media send evidence is captured by `proposal_followup.kp_message_id`.
The current quotation code path sends the PDF through the messaging provider
directly and does not create a separate `outbound_message_audits` row for that
PDF; text bot replies do have outbound audit rows.

# Cleanup

- Old `tj-gh22-*` synthetic conversations:
  - `79262810921#tj-gh22-product-20260521165301`
  - `79262810921#tj-gh22-quote-20260521165301`
  - `79262810921#tj-gh22-quote-num-20260521165301`
  - all are `closed`, `resolved`, and have zero pending/in-progress escalations.
- New `tj-gh23-*` synthetic conversations:
  - `+79262810921#tj-gh23-ambig2-20260522a`
  - `+79262810921#tj-gh23-ambiguous-20260522a`
  - `+79262810921#tj-gh23-num-20260522a`
  - `+79262810921#tj-gh23-word-20260522a`
  - `+79262810921#tj-gh23-word2-20260522a`
  - all are `closed`; pending/in-progress escalations are zero.

# Risks / Follow-ups

The quotation creation blocker is fixed. GitHub #11 is not complete yet:
the full follow-up E2E still needs confirmed FU1 EN/AR free-form text config
and approved Wazzup WABA FU2/FU3 template ids/codes.

The live pre-acceptance question did not escalate, but the answer was generic
and asked for item/quantity again. Treat that as a `tj-gh22.1` follow-up before
closing GitHub #11.
