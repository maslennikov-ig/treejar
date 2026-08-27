---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-wazzup-boundary-worker
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: /api/v1/webhook/wazzup
bounded_acceptance: privacy-safe production channel equality, history, warning timing, and fail-closed proof
non_goals:
  - production-env-db-config-or-service-mutation
  - deploy-or-restart
  - real-message-send-or-paid-provider-call
  - Wazzup-channel-scope-expansion
evidence:
  - none
task_id: tj-7w8f.4
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: tj-7w8f-prod-wazzup-boundary
milestone: production-wazzup-channel-boundary-diagnosis
milestone_status: accepted
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production authorization boundary required the assigned security auditor with inherited model and reasoning
repo: treejar
branch: codex/prod-wazzup-boundary-validation
base_branch: main
base_commit: 25598101f33f47c9d1117499daeb1f4a02928046
worktree: /home/me/code/treejar/.worktrees/prod-wazzup-boundary
write_zone:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.4.md
success_criteria:
  - configured and incoming channel identities are compared without exposing identifiers or customer data
  - expected production channel ownership is proven from current env, running containers, database, and history
  - warnings are classified as drift or correct fail-closed filtering
  - no real message, paid-provider call, production mutation, restart, or deploy occurs
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-7w8f-prod-host-remediation/summary.md
  - Beads tj-7w8f.4 and tj-ppid
  - https://wazzup24.com/help/api-en/webhooks/ accessed 2026-08-27
  - https://wazzup24.com/help/api-en/authorization/ accessed 2026-08-27
  - https://wazzup24.com/help/api-en/wauth/ accessed 2026-08-27
  - https://wazzup24.com/help/api/webhooks/ accessed 2026-08-27
  - https://wazzup24.com/contact/ accessed 2026-08-27
selected_skills:
  - orchestrator-stage
  - task-router
  - systematic-debugging
selected_agents:
  - built-in-security-auditor
catalog_candidates:
  - none
parallel_group: wazzup-channel-boundary
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: dedicated worktree and merged local branch removed by the stage cleanup entrypoint
risk_level: high
verification_tier: delta
risk_tags:
  - security
  - authorization
  - data
  - rollback
affected_surfaces:
  - api
  - backend
  - data
invariants:
  - rollback
  - test-matrix
docs_impact: docs-only
docs_reviewed: no-change-needed
docs_review_notes: no durable product or operator contract changed; this artifact records current stage evidence and one bounded security follow-up
verification:
  - privacy-safe production env container log and DB metadata inspection at release 7e21de2: passed
  - historical Beads tj-ppid identity and owner-decision comparison by hash: passed
  - uv run --extra dev pytest three focused webhook and worker channel-boundary tests -q --tb=short: passed, 3 passed
  - orch-prompts docs-resolve Wazzup webhook source IP CIDR: blocked, non-package lockfile routing cannot resolve a version
  - official Wazzup webhook documentation and support-page search for source IP CIDR: blocked, no exact ranges published
  - production sudo nginx -T relevant Noor proxy directives and live compose nginx config inspection: passed, read-only
  - production Uvicorn version command and installed ProxyHeadersMiddleware source inspection: passed, version 0.41.0
  - local synthetic X-Forwarded-For extraction preflight: failed safely, trusted star selects attacker-controlled first entry
  - uv run --extra dev pytest three focused origin-allowlist tests -q --tb=short: passed, 3 passed
  - production Wazzup API credential and separate webhook-secret presence equality and length inspection: passed, read-only and sanitized
  - one production authenticated GET https://api.wazzup24.com/v3/webhooks with redirects disabled: passed, HTTP 200 and sanitized registration metadata only
  - python3 scripts/orchestration/validate_artifact.py artifact: passed
  - git diff --check: passed
changed_files:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.4.md
explicit_defers:
  - tj-7w8f.5 owns the owner-approved long-term sender-authentication backlog including provider Bearer binding, trustworthy proxy handling, and a verified source-IP policy
  - channel-specific provider-side webhook routing was not verified and must not be assumed as a safe warning-suppression mechanism
---

# Summary

**Decision: the repeated warnings are correct fail-closed protection, not
`WAZZUP_CHANNEL_ID` drift. No channel/config mutation is the safe fix.**

At the 2026-08-27 06:04:18 UTC snapshot, production release `7e21de2` had one
36-character expected channel value. Its privacy-safe hash tag was identical in
the mode-`0600` current `.env`, the running app container, and the running
worker container. There was no database `system_configs` channel override.
Production DB contained 532 conversations with exactly one stored inbound
channel identity, and that identity matched the current expected value.

The current app container recorded 16 refusals between 05:39:08 and 06:03:48
UTC. Every warning named the same one unexpected identity and the same expected
identity; the two hashes differ. Each refusal was within two seconds of an app
log entry for a webhook receipt containing a message. No missing-channel
configuration event occurred.

The unexpected hash also exactly matches the second channel documented by the
closed `tj-ppid` production investigation. That read-only provider inventory
established that both identifiers belonged to the same Wazzup account. The
owner then explicitly classified the second business-line channel as outside
the test bot's service scope. The current traffic therefore belongs to a known
integration channel but not to the one authorized for Noor processing.

# Scope / Routing

The reviewed boundary is `src/api/v1/webhook.py:262-281`, where
`settings.wazzup_channel_id` is required and equality is checked before a
message can reach Redis or ARQ. The worker repeats the same filter at
`src/services/chat.py:1062-1080`. `src/core/config.py:70-74` maps the expected
value from `WAZZUP_CHANNEL_ID`; `docker-compose.yml` injects `.env` into both
app and worker. No source, test, production configuration, database row,
service, provider account, or webhook route was changed.

Evidence was deliberately reduced to equality, short one-way hash tags,
counts, timestamps, lengths, file modes, and release/container metadata. No
raw channel, phone, chat, message, payload, or secret value is present here.

# Findings

## Correct control — no mutation (confirmed, preventive)

- **Attack/failure path:** a message bearing a channel identity outside the
  single configured scope reaches the webhook.
- **Observed behavior:** the app emits the warning and returns without writing
  to Redis or scheduling ARQ; the worker independently rejects missing or
  mismatched channels before DB/provider work.
- **Impact avoided:** an intentionally excluded business-line message cannot
  enter Noor's customer conversation, LLM, CRM, or outbound response path.
- **Prerequisite for acceptance:** exact equality with the configured channel.
- **Classification:** correct control; no fix. Confidence: high.

Changing `WAZZUP_CHANNEL_ID`, adding the second channel, or weakening equality
from warning traffic would widen customer-data and outbound-message authority
against the recorded owner decision. If product intent changes, that is a new
owner decision and a separately approved rollout, not incident remediation.

There is no evidence-backed in-repository suppression that preserves signal.
Provider-side channel-specific webhook routing was not verified in this pass,
so it must not be recommended as an available control. Keep the warning until
provider capabilities and intended channel ownership are confirmed.

## High — production origin allowlist is disabled (confirmed, must-fix follow-up)

- **Evidence:** production `WAZZUP_ALLOWED_IPS` is empty. In
  `src/api/v1/webhook.py:27-39`, an empty value causes the endpoint to accept
  every request origin. The route is the public Noor Wazzup webhook.
- **Attack path:** an external caller who obtains or guesses the expected
  channel identifier can submit a syntactically valid inbound payload. The
  channel equality guard does not authenticate the HTTP sender.
- **Impact:** unauthorized queue/LLM work and an outbound response to an
  attacker-controlled chat are possible; this can consume provider budget and
  pollute conversation/CRM data. The current warning traffic is not evidence
  that this happened.
- **Prerequisites:** public route access plus the expected channel identifier
  and a valid payload shape. Confidence: high for the missing preventive
  control and code path; unknown for exploitation.
- **Verdict:** **NO-GO for setting the application allowlist now.** Current
  official Wazzup documentation does not publish source CIDRs, and the current
  trusted-proxy chain lets a caller control the address selected by Uvicorn.
  Applying repository example ranges would therefore combine an unverified
  allowlist with a bypassable source-address extractor.
- **Smallest safe mitigation sequence:** obtain current exact CIDRs from an
  official Wazzup page or an attributable support response; enforce those
  ranges at the host nginx TCP peer boundary; overwrite any client-supplied
  forwarded chain; restrict Uvicorn to known proxy hops; prove the resulting
  `request.client.host`; only then set the app allowlist and restart the app
  under production authority. Keep channel equality as the second preventive
  layer. Until those gates pass, do not expose the expected identifier and
  monitor refusal counts. No containment was performed in either read-only
  turn.

# Read-only origin-allowlist preflight — 2026-08-27

## Authoritative source result: blocked

Repository-required `docs-resolve` was executed once for Wazzup webhook source
IP/CIDR behavior. It returned `blocked` before lookup because Wazzup is not a
versioned lockfile package. The permitted fallback then inspected only these
official Wazzup sources on 2026-08-27:

- `https://wazzup24.com/help/api-en/webhooks/` — official API v3 webhook
  behavior;
- `https://wazzup24.com/help/api/webhooks/` — official partner webhook
  behavior and security checklist;
- `https://wazzup24.com/contact/` — official support route for an attributable
  range confirmation.

The API v3 page states that Wazzup sends POST requests to the configured URI,
may attach a Bearer header when a `crmKey` exists, expects HTTP 200, and sends a
test POST when the callback is registered. The partner page requires HTTPS and
documents retry/idempotency behavior. Neither official webhook page publishes
source IP addresses or CIDR ranges. Exact authoritative ranges are therefore
**unavailable**, not inferred. The two ranges present in `.env.example` have no
matching official Wazzup source found in this review and must not be used as
production authority.

The only safe application configuration format, after official ranges exist,
is one comma-separated environment value parsed by `src/api/v1/webhook.py`:

```text
WAZZUP_ALLOWED_IPS=<official-cidr-1>,<official-cidr-2>
```

Whitespace is trimmed and both IPv4 and IPv6 CIDR syntax are accepted by
`ipaddress.ip_network(..., strict=False)`. Placeholder text above is a format
example only; there are no approved values in this artifact.

The official API v3 page's optional Bearer behavior is not sufficient evidence
that this account sends a stable secret header. The current handler does not
validate such a header. Header authentication may be evaluated separately only
after the account-specific contract is confirmed; it is not a substitute
assumed by this preflight.

## Proxy-chain result: blocker confirmed

The production chain is:

```text
internet -> host nginx :443 -> compose nginx :8002 -> app Uvicorn :8000
```

Read-only `sudo nginx -T` proved the Noor host location proxies the webhook to
`127.0.0.1:8002`, sets `X-Real-IP` from `$remote_addr`, and **appends** to
`X-Forwarded-For` with `$proxy_add_x_forwarded_for`. The live compose nginx does
the same append before proxying to the app. Neither layer declares
`real_ip_header`, `set_real_ip_from`, or `real_ip_recursive` in the reviewed
Noor path.

The production app runs Uvicorn 0.41.0 with `--proxy-headers` and
`--forwarded-allow-ips="*"`. Its installed `ProxyHeadersMiddleware` treats every
peer as trusted and selects the **first** `X-Forwarded-For` entry. A synthetic
local preflight proved that a chain shaped as
`attacker-supplied, real-client, host-proxy` resolves to `attacker-supplied`.
With a bounded trusted-proxy set, the same implementation walks from the right
and selects the first untrusted hop.

Consequently, the current `request.client.host` used by
`_verify_webhook_origin()` is not a trustworthy sender identity. A caller can
prepend an allowed address before both nginx layers append their peers. The
existing unit tests prove CIDR membership behavior after `request.client.host`
is chosen; they do not prove the production proxy chain chooses it safely.

## GO criteria for a future authorized change

Verdict for this turn: **NO-GO**. A future production change becomes GO only
when every item below is evidenced in one preflight:

1. Wazzup's current exact webhook source CIDRs are supplied by an official
   published page or an attributable Wazzup support response with date.
2. The host nginx webhook location rejects non-Wazzup TCP peers using those
   official ranges. This first-hop control must use the socket peer, not a
   client-supplied forwarded header.
3. Host nginx overwrites incoming `X-Forwarded-For` with `$remote_addr` for the
   webhook path. Compose nginx passes that normalized value without admitting
   a client prefix.
4. Uvicorn no longer uses `--forwarded-allow-ips="*"`; it trusts only the
   immediate, explicitly bounded proxy hop or network.
5. An offline/local proxy test proves a spoofed prefix is rejected and the
   known synthetic source is preserved through both proxy layers. No real
   webhook is needed.
6. `nginx -t`, a focused application config parse, the existing allowed and
   disallowed-origin tests, and Noor public health all pass before/after the
   authorized reload/restart.

The preferred preventive ordering is host-nginx `allow`/`deny` at the public
TCP boundary first, then a hardened forwarded chain plus application CIDR
check as defense in depth. Do not set the app value against the current proxy
chain merely to make the config non-empty.

## Future rollback contract

Before any authorized change, create mode-`0600` rollback copies of the exact
host nginx Noor config and `/opt/noor/.env`, record their hashes and modes, and
capture current release/health plus baseline webhook 2xx/403 counts without
payloads or identifiers.

Rollback triggers are: confirmed Wazzup deliveries receive 403 after the
change, proxy extraction does not return the expected synthetic source,
`nginx -t` fails, Noor health degrades, or app restarts unexpectedly. Restore
both exact backups, run `nginx -t`, reload only host nginx, recreate only app if
its environment/entrypoint changed, and recheck release identity, public
health, process restart counts, and privacy-safe webhook status counts. A
rollback may temporarily restore the known open-origin risk; it must never
weaken the channel equality filter.

# Read-only callback-registration lookup — 2026-08-27

## Official API contract

The official API v3 sources establish three distinct credentials and actions:

- `https://wazzup24.com/help/api-en/authorization/` documents that requests to
  Wazzup use an account API key in `Authorization: Bearer <api-key>`.
- `https://wazzup24.com/help/api-en/webhooks/` documents exactly one read path
  for the current API v3 callback registration:
  `GET https://api.wazzup24.com/v3/webhooks`. The response contains
  `webhooksUri` plus four subscription booleans.
- The same webhook page documents a full `PATCH /v3/webhooks` replacement with
  `webhooksUri` and the subscription object. Wazzup sends `{test: true}` to the
  proposed callback and accepts the update only when it receives HTTP 200;
  otherwise it reports `testPostNotPassed`.
- `https://wazzup24.com/help/api-en/wauth/` documents `crmKey` as a separate,
  partner-generated value supplied during WAuth connection. When Wazzup has
  that value, it sends it to the CRM callback as an Authorization Bearer
  header. It is not the API key used to call Wazzup.

The documentation describes PATCH as one request, but it does not promise
transactionality, ETag/compare-and-swap protection, preservation of the prior
registration on every failure mode, or a rollback endpoint. A second PATCH of
the protected prior configuration is the only described restoration shape,
and it also triggers a test POST. Therefore "single request" must not be
reported as "atomic rollback".

## One allowed production GET

Production contained a non-empty 32-character Wazzup API credential. Its value
was used only inside the app container for exactly one authenticated GET to the
documented endpoint, with redirects disabled. No token, response payload,
callback URI, query, channel identifier, or customer identifier was printed or
stored in the artifact.

Sanitized result:

- transport succeeded; HTTP status `200`; no redirect;
- response was a JSON object with two top-level fields;
- callback registration exists, uses HTTPS, and has no query string;
- callback one-way hash does **not** equal the canonical
  `https://noor.starec.ai/api/v1/webhook/wazzup` hash;
- all observed live Wazzup POSTs still use exactly that canonical request path,
  so delivery currently reaches Noor, but the protected callback URI or its
  hostname/route intermediary cannot be reconstructed from this sanitized
  result;
- four boolean subscription settings were returned; two are enabled:
  `messagesAndStatuses` and `channelsUpdates`; contact/deal creation and
  template-status subscriptions are disabled;
- no `crmKey` field was returned.

The callback mismatch is a **bounded blocker**, not authority to PATCH. A
future operator must inspect and protect the exact existing URI through an
authorized secret-safe channel, establish why it reaches the canonical Noor
path, and retain the complete prior registration for rollback before proposing
any replacement. Repeating the GET was intentionally avoided.

## Account-specific Bearer verdict

Production also contains a separate non-empty webhook-secret value. It is nine
characters long and differs from the Wazzup API credential. Presence in `.env`
does not prove that the provider account stores the same value as WAuth
`crmKey`.

Repository search found no setting, header comparison, middleware, or webhook
handler use for that secret. The public callback accepts a valid payload
without Authorization whenever the origin allowlist is empty, as the existing
focused test proves. Provider response metadata does not expose `crmKey`, and
request headers are not safely retained in current logs. Thus:

- Wazzup supports account-specific Bearer delivery through WAuth in general;
- whether this production account is configured with that exact `crmKey` is
  **unproven**;
- even if Wazzup sends it, Noor currently does not validate it, so it provides
  no preventive control;
- the observed nine-character secret must not be assumed sufficiently random,
  active, or safe for rollout without a protected value/ownership check and,
  if adopted, a coordinated rotation.

## Remediation-path verdict

The final verdict remains **NO-GO** for provider or production mutation.
Current evidence supports this future sequence only:

1. obtain official current source CIDRs or choose a separately confirmed
   account-specific Bearer contract;
2. resolve the callback hash mismatch and securely snapshot the exact current
   URI plus all four subscription booleans;
3. harden the nginx/Uvicorn trusted-proxy chain before relying on application
   IP allowlisting;
4. implement and locally test constant-time Bearer validation only if the
   provider-side `crmKey` binding and rotation procedure are confirmed;
5. treat any PATCH as an externally visible operation because it necessarily
   causes a Wazzup test POST; request explicit authority for both PATCH and the
   test callback;
6. retain the protected prior registration for a compensating PATCH rollback,
   without claiming provider-guaranteed atomicity.

This final lookup made no PATCH/POST, sent no webhook or message, changed no
provider, environment, database, proxy, container, or service, and performed
no additional provider read after the one authorized GET.

# Verification

Normal path, failure path, and the worker edge passed locally:

- an expected-channel webhook enqueues one batch;
- an unexpected-channel webhook returns success to stop provider retries but
  performs no Redis push and no ARQ enqueue;
- a worker batch with no configured expected channel terminates and quarantines
  before opening a DB session.

The first test command omitted the optional `dev` extra; `uv` therefore had no
`pytest` executable and returned `Permission denied` before collection. The
root cause was confirmed from `pyproject.toml` and the empty environment. The
same exact three-test set with `--extra dev` passed: 3 tests in 1.23 seconds.
This was an environment-launch failure, not a test failure.

Production validation was read-only. It covered current `.env`, running
container environments and creation timestamps, app/worker logs, release SHA,
and aggregate DB metadata. It did not call Wazzup, send a message, invoke a paid
provider, mutate DB/Redis/config, restart services, or deploy.

Root outcome supersession (2026-08-27): later work deployed the application
Bearer path in non-blocking `observe` and proved that the current audit relay
preserves Authorization. Provider binding, trustworthy proxy handling, and a
verified source-IP policy remain together in deferred Bead `tj-7w8f.5`.
`observe` does not authenticate senders. The channel filter itself remains
accepted and fail closed.

# Delivery / Cleanup

This worker branch contained only this artifact. The root orchestrator accepted
the channel-boundary evidence, merged it, and removed the local branch and
worktree. Later Wazzup sender-auth work is tracked separately.

# Risks / Follow-ups / Explicit Defers

1. Do not change channel configuration for `tj-7w8f.4`; the warnings prove the
   existing scope guard is active.
2. The owner postponed sender-authentication hardening as Bead `tj-7w8f.5`.
   It includes the missing origin policy and trusted-proxy correction; until
   then, do not describe source identity as authenticated.
3. If warning volume becomes operationally noisy, first verify whether Wazzup
   supports channel-scoped webhook delivery and whether the owner still wants
   the second channel excluded. Do not suppress or reroute based on an
   unverified assumption.
4. Static and read-only review cannot prove the HTTP sender was Wazzup while
   the origin allowlist is empty. It proves only that the received identifier
   equals the previously known excluded integration channel.
