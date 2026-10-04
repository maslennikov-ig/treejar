# Existing Self Client access, tj-uvld

Date:2026-10-04. Working organization only; warehouse mutations forbidden.
This is read-only access proof, not provider completeness or stock-delta proof.

## Prior Viktor instruction and current result

The28Sep client instruction, docs/client-answers/zoho-inventory-code-2026-09.html,
uses the existing EU Self Client and Generate Code. Its scope list omitted
inventoryadjustments/purchasereceives/salesreturns/transferorders/packages READ.
The general docs/client/zoho-token-renewal-victor.html is older recovery material
and uses the global console URL; use the actual EU region for this organization.
The earlier CRM/Inventory refresh-token incident is not the present diagnostic
access requirement. No owner code, new client or permanent token renewal needed.

Zoho documents a Self Client client_credentials exchange with scoped access
tokens lasting one hour and no refresh token. Existing owner client credentials
and organization context were used only inside app memory; token never saved
or installed into production. Generic docs alone did not establish Inventory
support. Actual Inventory responses now establish support in this organization.
[Primary contract](https://www.zoho.com/developer/oauth/self-client/client-credentials-flow.html).

Three live sessions totaled3OAuthPOST200 and17InventoryGET200. No retries,
refresh-token exchanges, Redis/config/warehouse writes or user messaging.
Production cached token compared equal before/after each session. Requested
and provider-reported scope sets equal six exact READ scopes; lifetime3600s.

The10:59 preliminary feasibility receipt establishes transport only. The11:03
session additionally verifies code0 and adjustment-list JSON shape; history
samples cover adjustments, purchase receives, returns and transfers. Packages
HTTP200 had an unexpected list shape; no empty/complete inference. Delta query
sample is bounded at3pages/9distinct rows and remains incomplete. Its response
timestamps precede the supplied24h boundary; no missing-operation claim.
Executed11:03 source was reconstructed and byte-hash matched before retaining
self-client-history.executed-source.txt; no mismatching current-source binding.

The11:19 observation verifies one adjustment/detail/current-item identity:
quantity statusadjusted, created04Oct06:12:25UTC,28lines, selected line+10;
current item stock24, item timestamp16Sep12:46:30UTC. No observed old quantity
or complete delta membership. Other stock operations may exist; do not infer
the old quantity by subtraction. Identifiers/customer details remain in memory.

## Filter contract review and limits

Independent primary-source review by filter_docs_review accepted at root:
GET/items says modified after the supplied datetime; boundary equality and
stable secondary sort are unspecified. It lists last_modified_time sorting,
orderA/D, default page1/per_page200; no maximum page size is established.
The separate itemmasters inclusive wording is not the items contract. Response
timestamp examples do not guarantee advancement after stock-only changes.
[Items API v1](https://www.zoho.com/inventory/api/v1/items/).

Inventory-adjustment documentation defines a separate resource, without an
item-timestamp update guarantee.
[Adjustment API v1](https://www.zoho.com/inventory/api/v1/inventoryadjustments/).
General pagination documents page_context/has_more_page; the items example
omits that field. Never infer completeness from an omitted context.
[Pagination](https://www.zoho.com/inventory/api/v1/pagination/).

Documented datetime format versus live parser behavior remains inconsistent:
literalZ failed in the03Oct probe, numeric+0000 succeeded. Downloadable OpenAPI
schema was not verified; documentation-viewer download failed. docs-resolve
stopped before L1 because Zoho is not a locked package; official v1 docs used.

Remaining AC02 data: causal observed before/after quantities, full matching
delta membership for stock/lifecycle types, equal-time/paging stability.
Natural owner operations may supply observations; no warehouse tests allowed.
History access itself does not prove those properties. DeltaOFF and tj-uvld
in_progress until coverage, permitted activation and real optimized24h proof.

21offline transport/Redis cases verify exact scope/host/context guards, grant
shape, no credential output, identity/error/cooldown stops and exclusive modes.
They are synthetic. Root final acceptance also rechecks prior17manual-grant
and6cached-audit cases plus pure launcher compilation; no live calls in tests.
Runtime source/release footprint unchanged; earlier4458/20 release proof reused.
