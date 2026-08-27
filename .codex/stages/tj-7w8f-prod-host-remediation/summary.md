# Stage tj-7w8f-prod-host-remediation

Status: blocked on external ownership.

## Goal

Restore production-host maintenance health across Noor log rotation and memory,
relay TLS renewal, neighboring Polska scheduled jobs, and the Wazzup channel
boundary without weakening customer-data controls or causing uncontrolled live
activity.

## Production premortem

Verdict: GO WITH CONDITIONS.

- Every host edit must have a mode-`0600` rollback copy and a focused validation
  before the corresponding service is reloaded or reset.
- Shared-host mutations are sequential. Noor public health is checked before and
  after each stream.
- Swap is changed only after proving enough available RAM and zero current swap
  pressure; rollback is the existing `/swapfile` and `/etc/fstab` contract.
- Relay renewal is repaired only after proving that this host owns the live DNS
  and certificate challenge path. Stale ownership is retired instead of forcing
  issuance.
- Polska validation must not trigger uncontrolled scraping, paid calls, customer
  messaging, or broad data mutation.
- Wazzup filtering remains fail closed. No channel is added from warning traffic
  alone, and no real message is sent for verification.

## Streams

- `tj-7w8f.1`: Noor host log rotation and swap health.
- `tj-7w8f.2`: `relay.starec.ai` certificate renewal ownership.
- `tj-7w8f.3`: failed Polska scheduled jobs.
- `tj-7w8f.4`: production Wazzup channel filtering.
- `tj-7w8f.5`: staged Wazzup `crmKey` sender authentication.

## Wazzup sender-authentication result

Verdict: BLOCKED ON WAuth CONNECTION OWNERSHIP after the production observe
probe corrected the earlier provider-contract assumption.

The two diagnostic webhook PATCHes preserved the existing callback and all four
subscription flags. Any future provider-side authentication rotation must use a
confirmed WAuth reconnect or support-assisted path with its connection-owned
values; webhook PATCH must not be used for `crmKey`.

- Authentication code was independently security-reviewed, merged and deployed
  at `43d6430`. Production now runs in non-blocking `observe` with a fresh
  high-entropy secret; Noor health, the GLM 5.3 Flash model route, restart count
  and OOM state remain green.
- Exact provider registration and `.env` snapshots are protected with mode
  `0600`. Two same-key `PATCH /v3/webhooks` requests returned 200 and preserved
  the callback and all subscription flags, but their test POSTs had no matching
  Bearer.
- Official contract re-check established that webhook PATCH accepts only
  `webhooksUri` and `subscriptions`. `crmKey` is stored only by WAuth
  `POST /v3/connect`; the unknown PATCH field was ignored.
- A bounded synthetic POST through the current audit relay preserved the same
  Authorization header and produced `match`, so the relay and Noor auth code are
  working. Provider-side WAuth binding is the remaining boundary.
- No further webhook PATCH is allowed and `enforce` remains blocked until the
  owner supplies the existing WAuth connection context or Wazzup confirms a
  supported callback-authentication path.

## Completed production repairs

- Removed the duplicate Noor nginx logrotate owner and restored a green
  `logrotate.service` plus timer. The exact prior file has a protected backup.
- Retired the stale unused local `relay.starec.ai` Certbot lineage after proving
  DNS and the live relay endpoint belong to another host; relay and Noor TLS are
  green.
- Left swap unchanged after measuring zero current pressure, zero Noor swap,
  zero OOM events and sufficient available RAM.
- Proved Wazzup unexpected-channel warnings are correct fail-closed filtering;
  production channel scope was not widened.

## Remaining external blocker

Polska CBOSA currently receives HTTP 403 from its upstream source. The deployed
`/opt/polska/app` has no Git or release lineage, and no canonical source repo was
found on the host, under `/home/me/code`, or in accessible GitHub repositories.
Changing the timer or masking its failure would hide data loss, so no such
containment was applied.

## Acceptance

Pending the canonical Polska source/owner decision and Wazzup WAuth connection
ownership. Completed Noor repairs and the deployed observe path remain healthy;
the stage must not be described as fully accepted while those two external
boundaries remain unresolved.
