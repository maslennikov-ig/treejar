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
- `tj-7w8f.5`: staged Wazzup `crmKey` sender authentication.

## Wazzup sender-authentication replan

Verdict: GO WITH CONDITIONS after the read-only provider contract lookup.

Given the existing provider callback and four subscription flags are the owner
configuration, when sender authentication is added, the rollout preserves those
exact values and changes only `crmKey`; it does not redirect or expand delivery.

- Deploy authentication code first in `observe` mode with a newly generated
  high-entropy secret. Observe mode records only `missing`, `mismatch`, or
  `match`; it never logs the header or secret and preserves existing handling.
- Back up the exact provider GET response and production `.env` as mode `0600`.
  The provider PATCH must use the unchanged callback and subscription flags plus
  the new `crmKey`.
- PATCH necessarily emits one Wazzup test POST. Enforcement is blocked until the
  Noor app records a matching Bearer for that test through the existing callback
  path. No match means immediate provider rollback and no enforcement.
- Enable `enforce` only after the matching observation. Missing or wrong Bearer
  must be rejected before Redis, ARQ, database, LLM, CRM, or outbound work.
- Rollback order is app mode back to `observe`, provider registration back to
  the saved response, then code/config release rollback if required. Noor health,
  callback/subscription equality, queue state, and privacy-safe auth counts are
  checked at each boundary.

## Acceptance

Pending delegated root-cause artifacts, sequential production remediation, and
one root-owned host plus public Noor verification.
