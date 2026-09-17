# Telegram reset restored in test-only mode

Task: tj-0pht. Owner authorized enabling reset and resetting the specified test number.
Code commit: 82299519ac26eee8bcfbfaf2e69a47ec2af98747.

## Cause and change

Restore mode returned 503 before Telegram authentication/command routing. The
provider retained one pending update, and the latest recorded reset was June 22.
The September 16 office request therefore reused 36 earlier messages.

Authenticate all updates, then allow only reset commands and admin-chat
reset confirmation/cancellation during restore mode. Acknowledge unrelated
updates as ignored, preventing repeated delivery without executing them.
Existing admin-chat checks, requester binding and five-minute confirmation TTL
remain. Worker cron, Telegram startup sync and non-test WhatsApp stay disabled.
Reset also archives the exact matching customer profile identity; historical
facts and orders remain attached to its old ID and cannot enter a fresh profile.
No external CRM objects are deleted.

## Risk and recovery

Premortem: GO WITH CONDITIONS. Preserve authentication and explicit confirmation;
never enable manager-reply or order-decision routes. Avoid stale profile reuse.
Executor controls: exact two source files, existing image as base, no env changes,
no global queue cleanup and no held namespace inspection.

Backup: /opt/noor/.hotfix-backups/tj-0pht-20260916 (0700).
Contains original source/release archive, old app/worker image IDs, data-before.json
(0600), Dockerfile and compose-hotfix.yml. New image: noor-reset:tj-0pht.
Base image: sha256:158974224c54e390b344967cc13f8afc74fd05eb878dfdcabf631f30e38e0be2.
Runtime uses the previous release plus exactly the two accepted source files and
new release marker. Host source files match. App and worker recreated only;
database, Redis, nginx, environment and held messages preserved.

Code rollback: restore source-before.tar.gz into /opt/noor, create an override
using saved image IDs for app/worker, then compose up --no-deps --no-build those
two services and check health. Do not reverse the owner-requested data reset as
part of code rollback. Data recovery requires checking intervening activity and
restoring only captured conversation/profile/escalation fields; keep messages.

## Evidence

32 focused tests passed (Telegram reset, conversation reset, webhook manager).
Focused Ruff and Mypy passed; git diff --check passed.
Production: health 200 with code commit; invalid Telegram secret 403;
authenticated inert update 200 ignored; provider pending updates 1 -> 0.
Readback: one new conversation, stage greeting, no name, zero messages; zero
profiles at the reset phone variants. One old conversation and one profile
archived, all 38 old messages preserved. Reset transaction locked affected tables
briefly, compared exact rows/message count against backup, then committed.
New conversation: 58f25771-f608-48e1-9586-6e22c503eec3.
Reset time: 2026-09-16T17:18:44Z (20:18 Moscow).
No synthetic customer message, paid model call or submitted Telegram reset was
used for proof. A fresh owner-authored WhatsApp message remains the end-to-end
check. Command dispatch and confirmation are covered by focused tests.

## Delivery boundary

Hotfix is live. Source retained on codex/tj-0pht-telegram-reset; integrate into
main before any later standard deployment. Ordinary main push auto-deploys with
--app-only and stops the worker; do not do that accidentally during this test.
