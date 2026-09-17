# Model-owned intent release

Task: tj-tn29. Status: candidate verification in progress.
Owner authorized deployment within the existing test0665-only boundary and up to
six main-model HTTP requests without customer messaging or production DB writes.

## Changes and scope

Three reported failures were pre-model routes: service-confirmation-handoff for
`sure`, customer-facts-past-order for LUMA/NOVO comparison, and
verified-policy-clarify for `check alternatives`. All produced zero model tokens.
The original catalog contained both requested workstation families.

The incoming pipeline now leaves interpretation to the main model with history.
Explicit tools own consent, customer details, requirements, proposal decisions,
search constraints and complementary queries. Replacement/removal of selections
is atomic. Postprocessing no longer invents a promise to check deferred services.
Financial/catalog grounding, input validation, durable-write rollback, quote
prerequisites, access controls and the test-channel gate remain enforced.
Legacy pure helper exports are retained where tests or offline consumers use them;
they no longer override inbound customer intent.

## Risk and recovery

Premortem: GO WITH CONDITIONS. Deploy exactly the accepted source overlay on the
current reset-hotfix image; no dependency, environment, DB schema, data repair,
queue cleanup or channel changes. Drain ordinary in-progress work before switching
app and worker together. Check health release, source hashes, image identity and
unchanged environment/test-only flags. No synthetic customer message.

Backup: `/opt/noor/.hotfix-backups/tj-tn29-20260917` (0700).
Previous release: `82299519ac26eee8bcfbfaf2e69a47ec2af98747`.
Rollback image: `sha256:39115e936b2f3b8c8300781153269aaec59a2a715f4ec07594b6015a180a3774`.
Restore `source-before.tar` into `/opt/noor`, use `noor-intent-base:tj-tn29`
for app and worker in a compose override, then recreate only those two services
with `--no-deps --no-build`. Verify health; do not roll back DB/customer activity.

## Verification

Pending final results. Full suite runs in an isolated normal clone named treejar
with the canonical remote identity and existing local frontend dependencies.
Runtime-identity and missing-dependency failures in the initial clone are
environment failures; no acceptance guards were relaxed.

Live-model probes use the candidate system prompt/tool schemas and actual main
model configuration. SQL transactions are read-only, Redis is mocked, tool calls
are recorded but not executed, and responses use clearly labelled catalog
snapshots. This is intent/tool-plan evidence, not fresh Zoho stock or WhatsApp E2E.
