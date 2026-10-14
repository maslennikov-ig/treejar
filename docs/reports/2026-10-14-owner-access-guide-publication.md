# Owner integration guide publication receipt

Date:2026-10-14. Status:PUBLISHED AND READ BACK. Project:treejar.

- Page: https://aidevteam.ru/a/3OtFHjUVt8IjyxImtnWwNF0CMdtFr1Ta
- Slug:2026-10-14-owner-wazzup-zoho-guide; version1; recipient label:собственник.
- Source:docs/reports/2026-10-14-owner-wazzup-zoho-guide.md.
- SHA256:5f0d54827c76b9d0d6649cd67afe851de887148dfa29902be24b520d9e1feaf0.
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

## Verification

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
