# Zoho Inventory credentials rejected

Admin alert 2026-09-28: `LLM final failure, core_chat, ZohoOAuthError (invalid_credentials)`.

## Cause

Zoho answers the Inventory refresh with `invalid_code`: the refresh token no
longer exists. Per Zoho docs this happens when a token is revoked (Connected
Apps, password reset) or a 21st refresh token is issued for the same user and
client, which deletes the oldest. Inventory and CRM share one client id; the
CRM token still works but has CRM scopes only (Inventory answers 401), so it
cannot stand in. Which of the two causes applied is not visible from our side.
The stock snapshot cron had been failing every five minutes with only a
warning in the log.

Impact: at 09:40 UTC the tester sent address and email for a quotation; the
turn failed and she got the generic "temporary issue" reply. No quotation was
created. Stock answers use the last snapshot until it ages out (1 h).

## Repair

- Rejected credentials now count as "not now" (`is_transient_inventory_error`):
  the quotation is deferred with reason `inventory_credentials_rejected`, the
  customer is told it is being prepared, managers are alerted, and the
  background retry completes it once a valid token is in place.
- The first rejection per hour sends an admin alert naming the env variable
  to replace (Inventory and CRM clients).
- Remaining owner action: issue a new Inventory refresh token for the same
  client and set `ZOHO_INVENTORY_REFRESH_TOKEN`.

## Evidence

New tests fail without the change and pass with it; full suite 4,389 passed,
20 skipped; Ruff, format, Mypy passed.
