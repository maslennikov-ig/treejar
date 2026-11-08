# Owner integration guide publication receipt

Date:2026-10-14. Status:PUBLISHED AND READ BACK. Project:treejar.

- Page: https://aidevteam.ru/a/3OtFHjUVt8IjyxImtnWwNF0CMdtFr1Ta
- Slug:2026-10-14-owner-wazzup-zoho-guide; current version3; recipient label:собственник.
- Source:docs/reports/2026-10-14-owner-wazzup-zoho-guide.md.
- Current source SHA256:d394c20227336b2d7f9af7962b87c70fdb85a3860e6df4e6d8e84afaa1e0f38f.
- Dedicated branch:codex/owner-access-guide-20261014; baseb45da2a.
  The publisher infers source_repo from the worktree leaf name; the isolated
  checkout ends in treejar, so canonical source_repo and source_path are correct.

## Evidence and scope

Owner-provided alerts:14Oct13:37Moscow CRM credentials rejected;14:36Moscow
Wazzup drift recovery. Exact token rejection cause remains unconfirmed.
Live settings read-only:releasea72da15, CRM accounts/API domains EU, credential
fields configured. No secret values read out or included in the artifact.
Current main callback-owner runbook and official Wazzup/Zoho documents were
reviewed; links accompany the corresponding client instructions.

The guide asks the account owner to identify/stop only the obsolete callback
writer, preserve working channels/integrations, renew the existing CRM client's
refresh token, coordinate short-lived code exchange and deliver secrets through
a closed channel. Owner responses capture only action statuses and notes.
Zoho rejection and Wazzup drift are separate; no unproved shared cause is stated.

## Verification of first publication

- artifact lint:0errors/0warnings; preview and dry publish passed.
- Local browser checks:400/800/1440px, light/dark, all6passed; no document
  overflow; min12px; h1mobile34px/desktop44px; submit accent passed.
- Desktoplight/mobile dark screenshots visually inspected.
- Published-page independent browser readback:HTTP200, correct Wazzup/Zoho
  sections/Noor URL/GenerateCode/EU and secret-handling note visible.
- Actual mobile400x900:documentwidth400, exactly1submit,2named radio groups
  and1optional note. No password/token input or preselected answer; live
  response controls remained untouched and submit was not clicked.

No runtime deployment, callback mutation, OAuth grant/token issuance, credential
replacement, organization writes or contact with third parties was performed.
Wazzup writer tasktj-zc6k remains blocked; publication is owner guidance, not
provider repair. Primary dirty work and existing customer artifacts retained.
Sources are retained in this dedicated local documentation branch.

## Owner explanation expansion — versions2 and3

Owner asked for a fuller description of the problem and business consequences.
Added the WhatsApp routing/recovery window, unanswered-client and manual-work
risks, CRM contact/deal recording failure and the separate Inventory/PDF path.
The competing writer and actual financial impact remain unconfirmed; no lost
revenue or number of missed messages is asserted.

Source review confirms CRM and Inventory use separate credential settings and
quotation generation uses Inventory. The alert producer groups invalid_client,
invalid_client_secret, invalid_grant and other credential failures into one
message; its wording alone does not establish a revoked refresh token. Version3
clarifies this uncertainty and asks the owner to check application details too.
No provider credentials/API state were mutated to investigate this distinction.

Republished under the same project/slug/recipient/link, with no new token.
Version2 fuller-layout checks passed all6width/theme combinations; desktop
screenshot inspected. Both2and3 live mobile readbacks passedHTTP200, width400,
new business explanation and preserved form names/one submit. Final version3
lint0errors/0warnings and live OAuth/Inventory distinctions verified.
All source input names, values, IDs and submit control were compared unchanged
against version1. No client answer controls edited or submitted. Original
version1 source SHA2565f0d54827c76b9d0d6649cd67afe851de887148dfa29902be24b520d9e1feaf0
is retained in commitd690839 and portal version history.
