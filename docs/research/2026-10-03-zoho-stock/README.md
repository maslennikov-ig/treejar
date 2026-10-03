# Zoho stock provider evidence

Read-only account interface checks, 2026-10-03. Only cached-token Inventory
GETs; Redis GET and catalog DB SELECT. No OAuth refresh, business writes,
configuration changes or messaging. Organization represented by a hash only.

- literal-z.json: list200; sorted delta with literal trailingZ400.2GETs.
- offset-bulk.json: list200; +0000 unsorted empty delta200;
  bulk sizes1,2,4,8 all returned every requested ID and numeric top-level
  stock_on_hand.6GETs.8 is a tested lower bound, not maximum.
- sorted-offset.json: +0000 +sort_column=last_modified_time +sort_order=A
  accepted200, empty delta.1GET.
- mapping.json: current343 active catalog rows,250 stored Zoho IDs,
  306 normalized SKU matches against2557 snapshot entries. No scope narrowing.

Total9HTTP GET attempts:8HTTP200,1HTTP400. These runs preceded candidate
counter installation; count from retained probe receipts, not candidate Redis.
Current script emits sorted-offset requests; first two receipts describe the
recorded earlier variants. Request differences are intentional and explicit.

Official sources checked2026-10-03:

- https://www.zoho.com/inventory/api/v1/items/#list-all-the-items
- https://www.zoho.com/inventory/api/v1/items/#bulk-fetch-item-details
- https://www.zoho.com/inventory/api/v1/pagination/
- https://www.zoho.com/inventory/api/v1/introduction/#api-call-limit

Docs confirm modified-since, list pagination/sorting and itemdetails interface.
They do not prove stock-operation completeness or stable offset pages.
The live account accepts a numeric UTC offset; literalZ was rejected.

Still unproved: nonempty delta for fulfillment, receipt, adjustment, return,
stock-changing warehouse transfer, creation/edit/rename/inactivation; deleted
rows may need daily full comparison. Equal timestamps and moving page sets
also require evidence. A sales order alone is not physical-stock evidence.
Local fixtures only exercise response shapes. Eligibility must remain off.

Candidate protection: overlap120s, cycle-start watermark, no unsupported
upper-bound/secondary sort; repeated IDs across pages abort. Multi-page delta
requires two identical complete projected maps. This detects the deletion
shift fixture but cannot prove arbitrarily mutating provider pagination.
