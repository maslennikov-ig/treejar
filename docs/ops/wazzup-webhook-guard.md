# Wazzup webhook guard

Task: `tj-vqcc`. Deployed and enabled with explicit owner approval on
2026-10-13; release `d2de7b3f47260cbb88114fc42f8cb6c85e27832d`.
The owner confirmed on 2026-10-12 that audit capture is unnecessary
and that events should reach Noor directly. The same audit callback reappeared
on 2026-10-13. The owner then requested protection against further changes.

## Behavior and prerequisites

- `WAZZUP_WEBHOOK_GUARD_ENABLED=false` by default. When enabled in the worker,
  reconciliation runs at startup and once per minute, including restore mode.
- Target is the repository's canonical endpoint:
  `https://noor.starec.ai/api/v1/webhook/wazzup`. This setting is shared by all
  channels in the Wazzup account; enable only with account-owner authorization.
- The API key must exist and sender/allowlist must match. Missing Redis or an
  occupied lease prevents writes. Each run has a 30-second network deadline,
  a 45-second Redis lease and an ownership-checked lease release.
- Healthy routing performs one GET and no PATCH. Drift performs two validated
  configuration reads; any intervening configuration change aborts the write.
- Wazzup requires subscription values in PATCH. Send the latest unchanged
  subscription object and the approved URL, then verify both with another GET.
  No sender, channel permission, customer data, held message or queue is changed.
- Notify the configured Telegram administrator on drift. Success and failure
  notifications have separate hourly limits, so a successful repair does not
  hide the first subsequent failure. Notification failure does not undo routing.
- Logs/notifications show only the displaced host and outcome. Never print
  callback query strings, provider response bodies, API keys or Telegram tokens.

Official API: https://wazzup24.com/help/api-en/webhooks/.
Live compatibility probe on 2026-10-13 assigned the already-correct URL with
only `webhooksUri`; the provider rejected it with HTTP 400. This implementation
therefore follows the documented full request with subscriptions. Existing
owner-authorized repairs with that request passed HTTP 200 and preserved flags.

## Technical premortem

Verdict: GO WITH CONDITIONS — local and CI proof passed; the owner explicitly
authorized deployment and enabling the shared-account writer. The competing
writer remains a separate follow-up, `tj-zc6k`.
Scope: provider callback configuration, ARQ registration, Redis lease and
administrator notification. No new permissions or credentials are introduced.

| Failure symptom | Evidence / mechanism | Detection and mitigation |
| --- | --- | --- |
| Another integration keeps changing the callback | Confirmed: exact audit URI returned after a successful repair | Restore drift; alert the administrator. Resolve account ownership separately. |
| A subscription changes while repairing | Plausible: provider PATCH requires a subscription snapshot and exposes no conditional-write contract | Compare two reads and skip a changing configuration; verify the result. A race between the final read and PATCH cannot be eliminated by this API. |
| Timeout, malformed response, rate limit or worker overlap | Plausible: network and shared-worker execution | Validate data, bound network time, use Redis ownership lease; never retry a PATCH within a run or claim repair before readback. |
| Callback query secret leaks or alert repeats | Confirmed: the displaced audit URI contains a secret query | Log only host/error class; hourly notification limits; regression tests. |
| Executor enables the guard on the wrong account | Plausible: shared-account callback affects every channel | Opt-in default, matching sender/allowlist, operator preflight, exact target and retained backup. |

This is recovery after a change, not a provider permissions lock. Detection
can wait for the next minute, queue capacity and network responses. Messages
that reached the displaced receiver before repair are not replayed. A competing
writer can still win again after a successful check. Stop that writer or change
its account access only with separate authority.

## Activation and recovery

1. Confirm exact candidate release and current provider URL/subscriptions, keep
   a private `0600` backup, and reconfirm approved test sender/allowlist.
2. Deploy the accepted source through the existing isolated release helper and
   test-worker-preserving deployment path. The canonical VPS helper's
   `--app-only` option automatically enables preservation of a verified
   restore-mode worker, including candidate fingerprint validation and safe
   app/worker recreation. Keep the current test0665 boundary.
3. Set `WAZZUP_WEBHOOK_GUARD_ENABLED=true` in the approved runtime environment
   and recreate the affected worker under the same deployment authority.
4. Verify effective worker settings, registered cron/function, unchanged sender
   boundaries, health/release, startup result `ok`, and a fresh natural message.
   Do not deliberately divert live customer callbacks as an acceptance test.

To stop the guard, set the flag to `false` and recreate the worker. Its last
correct callback stays in place; turning off the guard does not reroute messages.
Restore another callback from the private backup only on an owner decision,
after checking the current configuration. No database or queue rollback is needed.

Local proof uses mocked provider/Redis/Telegram boundaries. Separate live proof
on October 13 establishes effective activation, startup/minute cron checks and
the deployed repair path against the real provider with drift injected only
into an isolated process's GET observations. The real callback was never
diverted; one real PATCH retained the correct callback and subscriptions.
This controlled test does not establish a naturally observed external overwrite
or resolution of its writer. The earlier natural owner test confirmed text and
three images after manual repair; a fresh postdeployment round trip remains
pending. See `docs/reports/2026-10-13-wazzup-webhook-guard-delivery.md` for
source/CI/runtime receipts and the private rollback directory.

Local acceptance on 2026-10-13: 89 passed in 2.42 seconds using
`python -m pytest tests/test_wazzup_webhook_guard.py tests/test_worker.py
tests/test_scripts_vps_deploy.py tests/test_wazzup_outbound_safety.py -q
--tb=short --import-mode=importlib`; affected-file Ruff/format and Mypy on the
three changed source files passed, along with `bash -n scripts/vps-deploy.sh`
and `git diff --check`. Tests used fake credentials and unreachable test
database/Redis endpoints; no paid completions or live alerts were sent.
