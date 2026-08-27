# Stage tj-7w8f-prod-host-remediation

Status: accepted for Treejar production testing.

## Outcome

Treejar production health is green at release `43d6430`:

- GitHub Actions run `33047773974` passed Ruff, format, Mypy, 3891 tests with
  20 skips, semantic evidence, and deploy.
- Public health reports the exact release SHA. PostgreSQL and Redis are healthy;
  all five containers are running with zero restarts and no OOM events.
- The public API smoke passed 8/8.
- The customer-facing model is `z-ai/glm-5.3-flash` in both runtime sources and
  worker startup.

## Completed production repairs

- Removed the duplicate Noor nginx logrotate owner. `logrotate.service` and its
  timer validate and run successfully; the previous file has a protected backup.
- Left swap unchanged after proving zero current pressure, zero Noor swap use,
  zero OOM events, and sufficient available RAM.
- Retired the stale unused local `relay.starec.ai` Certbot lineage after proving
  that DNS and the live relay endpoint belong to another host. Relay and Noor
  TLS remain green.
- Proved Wazzup unexpected-channel warnings are correct fail-closed filtering.
  The production channel scope was not widened.
- Deployed staged Wazzup Bearer authentication in non-blocking `observe` with a
  strong protected secret. The relay and app authentication path passed a
  bounded synthetic probe. `observe` does not authenticate or reject senders.

## Owner scope decisions

- Polska is a separate client product that merely shares the host. The owner
  excluded it from Treejar scope on 2026-08-27. No Polska service, timer, source,
  or data was changed.
- Wazzup provider-side Bearer enforcement is a long-term backlog item. The
  current compatibility mode remains non-blocking; it is not a sender-security
  guarantee. The postponed work includes a supported WAuth binding plus a
  trustworthy proxy chain and verified source-IP policy. No further
  `PATCH /v3/webhooks` attempt is allowed for `crmKey`.

## Acceptance

The root-owned code and process acceptance passed before deployment, and the
deployed artifact passed host, service, TLS, model-readback, and public API
smoke checks. The two former external items are not current Treejar blockers:
one is out of product scope and the other is explicitly postponed.

Final closeout on 2026-08-27 passed 65 focused API, security, and webhook tests,
artifact/stage readiness, process verification, documentation review, cleanup,
and the repository's blocking-findings check.

## Documentation and graph

- `docs-reviewed: updated` — this stage summary and current handoff now reflect
  the owner's product boundary and long-term defer.
- `graph-reviewed: no-change-needed` — no repository ownership, entrypoint, or
  structural boundary changed.

## Explicit defers

- Wazzup sender-authentication hardening remains a low-priority long-term
  backlog item. It includes provider-side Bearer binding, trusted-proxy handling,
  and a verified source-IP policy; production stays in compatibility `observe`
  until that work is scheduled.
- The five-call paid model verifier remains deferred and requires separate
  explicit authority.
