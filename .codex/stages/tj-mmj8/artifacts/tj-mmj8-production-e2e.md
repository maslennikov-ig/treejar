---
schema_version: orchestration-artifact/v1
artifact_type: e2e-execution
task_id: tj-mmj8
stage_id: tj-mmj8
repo: treejar
branch: main
base_branch: origin/main
base_commit: 7d528b832acac800168669081007188b2cf0f458
worktree: /home/me/code/treejar
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: seven tj-mmj8-fr3309 synthetic conversations closed; active=0 and escalated=0 after cleanup
risk_level: high
runtime_commit: 428f360d7e8a97f936cf0eb2084d4aa6ecaf6801
github_actions_run: "26441317711"
production_smoke: passed
verification:
  - gh run view 26441317711: success
  - ssh noor-server runtime readback: 428f360d7e8a97f936cf0eb2084d4aa6ecaf6801 / 26441317711
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
  - live bot_test slash brief: passed, quotation Fr3310
  - live bot_test clean multiline brief: passed, quotation Fr3311
  - live bot_test low-confidence confirmation: passed, quotation Fr3312 after yes
  - live bot_test labeled fields: passed, quotation Fr3313
  - PDF text extraction for Fr3310, Fr3311, Fr3312, Fr3313: passed for explicit customer fields
  - synthetic cleanup query for phone fuzzy tj-mmj8-fr3309: total 7, active 0, escalated 0
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-mmj8/summary.md
  - .codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md
explicit_defers:
  - tj-mmj8 Beads closure deferred pending explicit owner approval
  - ancillary findings tracked separately as tj-4cm4, tj-8ma2, tj-nzob
---

# Summary

`tj-mmj8` was already merged, pushed, and deployed before this turn. This turn
reconfirmed the deployed runtime, ran controlled production E2E on the
owner-approved number `+79262810921`, verified the sent PDF contents, cleaned
test conversations, and recorded follow-up bugs for out-of-scope findings.

# Runtime Evidence

- GitHub Actions run `26441317711`: success, deploy included.
- Production runtime readback:
  - `/opt/noor/.release-sha`:
    `428f360d7e8a97f936cf0eb2084d4aa6ecaf6801`
  - `/opt/noor/.release-run-id`: `26441317711`
- Production smoke:
  `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` ->
  `7 passed, 0 failed`.

# Verification

The production verification covered runtime readback, API smoke, live WhatsApp
conversation replay across common quote-brief input styles, metadata readback,
Zoho draft quotation readback, downloaded PDF text extraction, visual PDF
rendering for the main slash scenario, and cleanup readback for synthetic
conversations.

# Scenario Matrix

Approved number: `+79262810921`.

Production Wazzup channel: `b49b1b9d-757f-4104-b56d-8f43d62cc515`.

| Scenario | Phone suffix | Conversation | Result |
| --- | --- | --- | --- |
| A: exact SKU clarification | `+79262810921#tj-mmj8-fr3309-a-20260526` | `af5b44cf-00d8-45bf-ab3a-39c0651c1c66` | Failed out-of-scope: after exact SKU clarification, bot still asked for item/quantity; tracked as `tj-4cm4` |
| B: original slash brief plus later ambiguous individual/address | `+79262810921#tj-mmj8-fr3309-b-20260526` | `dac20020-f102-4ee5-8bb8-a3240537571d` | Passed: `Lilia / LLD / Lfdsf@kfsl.ru / 2 street` created `Fr3310`; later `individual / dubay 2 street 7` did not overwrite `LLD` |
| C: sales-order resume then multiline brief | `+79262810921#tj-mmj8-fr3309-c-20260526` | `dc7328a0-809e-4f57-87ba-b5556dfe98d5` | Failed out-of-scope: stored brief details but reinterpreted them as unresolved item text; tracked as `tj-8ma2` |
| D: low-confidence address confirmation | `+79262810921#tj-mmj8-fr3309-d-20260526` | `a259f7c1-4e08-4a1e-9e10-bba8ba17fbb9` | Passed: asked confirmation for `Address: Dubai`; `yes` created `Fr3312` |
| E: comma-separated ordered brief | `+79262810921#tj-mmj8-fr3309-e-20260526` | `70bb56fe-a97b-432b-b085-f0fa3e36f730` | Failed coverage gap: stored name/email/address but missed company `LLD`; tracked as `tj-nzob` |
| F: labeled fields | `+79262810921#tj-mmj8-fr3309-f-20260526` | `b916aee2-df6d-4b32-bd13-1b373a71d779` | Passed: labeled details created `Fr3313` |
| G: clean multiline ordered brief | `+79262810921#tj-mmj8-fr3309-g-20260526` | `8947af78-d039-4e1c-bad3-a35a243e5bd6` | Passed: multiline details created `Fr3311` |

# Core Production Evidence

`dac20020-f102-4ee5-8bb8-a3240537571d`:

- Model: `z-ai/glm-5|quote-resume`.
- Assistant result:
  `Quotation Fr3310 has been prepared and sent to you.`
- `quote_customer_details` after later ambiguous individual/address reply:
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, `address=2 street`.
- `zoho_sale_order_number`: `Fr3310`.
- `zoho_sale_order_id`: `378603000022208017`.
- `proposal_followup.kp_message_id`: `970a566f-9559-49f7-9b7a-28e91c6b7561`.
- Manager handoff/escalation: none.

`8947af78-d039-4e1c-bad3-a35a243e5bd6`:

- Model: `z-ai/glm-5|quote-resume`.
- Assistant result:
  `Quotation Fr3311 has been prepared and sent to you.`
- `quote_customer_details`:
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, `address=2 street`.
- `zoho_sale_order_number`: `Fr3311`.
- `zoho_sale_order_id`: `378603000022205019`.
- `proposal_followup.kp_message_id`: `5d0d0211-1466-4456-bd36-c6960bf44eb7`.
- Manager handoff/escalation: none.

`a259f7c1-4e08-4a1e-9e10-bba8ba17fbb9`:

- Low-confidence brief model: `z-ai/glm-5|quote-brief-confirm`.
- Confirmation text listed:
  `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`, `Address: Dubai`.
- `yes` model: `z-ai/glm-5|quote-resume`.
- Assistant result:
  `Quotation Fr3312 has been prepared and sent to you.`
- `quote_customer_details`:
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, `address=Dubai`.
- `zoho_sale_order_number`: `Fr3312`.
- `zoho_sale_order_id`: `378603000022208066`.
- `proposal_followup.kp_message_id`: `b8aa8f1a-8b83-4a64-a592-8875de91bbdb`.
- Manager handoff/escalation: none.

`b916aee2-df6d-4b32-bd13-1b373a71d779`:

- Model: `z-ai/glm-5|exact-quote-deterministic`.
- Assistant result:
  `Quotation Fr3313 has been prepared and sent to you.`
- `quote_customer_details`:
  `name=Lilia`, `company=LLD`, `email=Lfdsf@kfsl.ru`, `address=2 street`.
- `zoho_sale_order_number`: `Fr3313`.
- `zoho_sale_order_id`: `378603000022205046`.
- `proposal_followup.kp_message_id`: `4b10ed1a-71f6-471b-a06c-d99e810ebf6e`.
- Manager handoff/escalation: none.

# PDF Evidence

Wazzup document webhooks provided downloadable PDF `contentUri` values for
`Fr3310`, `Fr3311`, `Fr3312`, and `Fr3313`. The PDFs were downloaded to
`tmp/pdfs/`, rendered with `pdftoppm`, visually inspected, and text-extracted
with `pdftotext`.

`pdftotext` evidence:

- `Fr3310`: `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`,
  `Address: 2 street`, `CH 620 grey`.
- `Fr3311`: `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`,
  `Address: 2 street`, `CH 620 grey`.
- `Fr3312`: `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`,
  `Address: Dubai`, `CH 620 grey`.
- `Fr3313`: `Name: Lilia`, `Company: LLD`, `Email: Lfdsf@kfsl.ru`,
  `Address: 2 street`, `CH 620 grey`.

Visual inspection of `Fr3310` showed the `Quotation To` block rendered with the
explicit fields and no overlap/clipping. The phone line includes the synthetic
test suffix because the conversation was isolated with a repo-owned smoke
suffix; real traffic does not use that suffix.

# Risks / Follow-ups

Created focused Beads tasks:

- `tj-4cm4`: Exact quotation SKU clarification resume must preserve exact SKU
  and quantity.
- `tj-8ma2`: Sales-order quote resume must not treat customer brief as
  unresolved item.
- `tj-nzob`: Comma-separated quote brief should preserve company field.

# Cleanup

All seven production synthetic conversations matching phone fuzzy
`tj-mmj8-fr3309` were closed via the protected conversation API.

Cleanup readback:

- `total_synthetic_fr3309=7`
- `active_count=0`
- `escalated_count=0`

# Closeout Decision

Core Fr3309 acceptance is verified in production. `tj-mmj8` can be closed after
explicit owner approval. It remains `in_progress` because this turn was not
authorized to close Beads/GitHub tasks.
