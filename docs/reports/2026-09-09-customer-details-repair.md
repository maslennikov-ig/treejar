# Customer detail capture incident — tj-d27h

Scope: fix address/name corruption in quotation detail capture and the adjacent
company/phone/field-alias defects confirmed by pure reproduction. No model change,
channel change, provider messaging, held-queue access, or broad data cleanup.

## Evidence and intended behavior

- A delivery coverage question produced `delivery.address="?"`.
- A complete comma-separated street address was stored by the fast extractor as
  `delivery_address`; the quote bridge expects `delivery.address`.
- Terse comma splitting treated a district as the customer name.
- Company questions produced company facts; `Company name:` also produced a
  person-name fact; an invoice number was captured as a phone number.
- Existing profile aliases `customer.display_name` and `customer.primary_email`
  projected into a profile but were ignored by quotation details.

Given an individual customer supplies a full street address and email, when the
quote resumes, preserve the previously supplied name, retain the complete address,
and stop requesting an address. Questions and invoice identifiers must not fill
customer-detail fields.

## Risk review (technical-premortem)

Verdict: GO WITH CONDITIONS for the targeted repair. The owner subsequently
authorized code deployment and immediate verification. Capture flows into customer facts, profile projections, quotation
metadata, and eventually CRM/PDF/provider actions.

- Confirmed false-positive facts: reject question/label collisions and verify
  adjacent valid company, name and international-phone cases.
- Plausible neighboring regression: keep full address boundaries and existing
  labeled/multiline quotation inputs in focused acceptance.
- Confirmed silent alias loss: normalize known aliases before persistence and
  preserve reading of already-stored supported profile aliases.
- Executor/concurrency risk: repair only the diagnosed conversation and its three
  address facts, lock affected rows, compare a backup fingerprint, and abort on
  changed customer details or newer conversation activity.
- Recovery: preserve all original message rows; back up original conversation
  metadata and all three fact rows before mutation. Restore only changed fields
  after checking for intervening activity; code rollback is separate from data
  recovery. No automatic replay or outbound proof message.

## Acceptance and delivery

Production repair independently reviewed and applied on 2026-09-09: one
conversation and three address facts, protected by a SHA-256 snapshot check and
row locks. A separate post-commit read returned `ALREADY_REPAIRED`. Original
messages were preserved and no outbound message was sent. The local backup is
`/home/me/.local/state/treejar/repairs/tj-d27h-before.json` (0600).

Independent review approved the final question/name/type corrections. Regression
fixtures use a synthetic address preserving the original failure shape; the real
conversation snapshot is kept outside Git. Final acceptance passed on the byte-identical candidate snapshot:

- `python -m pytest tests/ -q --tb=short`: **3,970 passed, 20 skipped**.
- `python -m mypy src/`: no issues in 178 source files.
- Ruff check and format check across `src/ tests/`: passed.
- `git diff --check`: passed.
- Changed source/test files were compared byte-for-byte with the acceptance
  clone before commit. No live model/provider call or customer message was
  used as synthetic proof. Production repair and code deployment were verified
  separately.

Docs reviewed: this incident note records the durable behavior and repair scope.
Project index: no new runtime module or public entrypoint is planned.
Graph reviewed: no graph is present; no refresh needed for this bounded change.

## Separate infrastructure finding

`tj-bgwu` tracks the existing corpus-isolation assertion that assumes the git
common directory is under the linked worktree's `.git` path. No privacy gate was
weakened. Acceptance runs in an isolated normal local clone with the exact source
snapshot, an explicit `PYTHONPATH`, and reused local Python/Node dependencies.

## Production release verification

Owner-authorized release `e071bb683e1fcc876efd40ca16b28ed6d2486241` deployed
on 2026-09-09 through GitHub Actions run `34333335661` (success).
CI: 3,963 passed, 27 skipped; lint and type checks passed. Initial run
`34332793963` stopped before deployment due to current-state handoff digest
maintenance; the repository helper updated only mutable source pins.

The application and worker use identical image
`sha256:158974224c54e390b344967cc13f8afc74fd05eb878dfdcabf631f30e38e0be2`.
Worker startup confirms the test-channel mode. Both have zero restarts and no
OOM event. Public health reports the exact release and healthy database/Redis.
The environment file is unchanged; database, Redis and nginx containers were
preserved. Held messages were not accessed.

Read-only live data checks confirmed the corrected quotation name/address and
sole accepted canonical address fact. Deployed-code checks used the original
question, full address and repeated address with an in-memory conversation:
complete address and name preserved, no missing quotation fields. Adjacent
question/company/invoice negatives passed. Both runtime source files matched
the accepted local SHA-256 hashes. No model calls, outbound messages or database
writes occurred in this verification. A fresh WhatsApp exchange with the tester
is outside this evidence; testing may resume on test0665.

Rollback archive:
`/opt/noor/.hotfix-backups/deploy-20260909T091436Z-from-af93ebd5a07d50e1689df76a28d465ddbbec2c17.tar.gz`.
Local smoke receipt: `/home/me/.local/state/treejar/repairs/tj-d27h-live-smoke.log`.
