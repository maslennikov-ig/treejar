# Stage tj-7w8f-prod-host-remediation

Status: in progress.

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

## Acceptance

Pending delegated root-cause artifacts, sequential production remediation, and
one root-owned host plus public Noor verification.
