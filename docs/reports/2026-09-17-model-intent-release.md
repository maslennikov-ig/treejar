# Model-owned intent release

Task: tj-tn29. Status: deployed and checked on the test-only runtime.
Code release: `9a0868356065395853bcfaabd293639f78ce2ab5`.
Image: `noor-intent:tj-tn29`, ID
`sha256:377be8c6c98489bb39cb98404a49204b62fb12e2b321515288973599f6e1c6ec`.
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

Full suite: 4,045 passed, 20 skipped. After the final import/export typing fix
and incomplete-search prompt clarification, 190 affected tests passed; Ruff
check/format and Mypy (179 files) passed. No size guard was relaxed. Full suite ran in an isolated normal clone named treejar
with the canonical remote identity and existing local frontend dependencies.
Runtime-identity and missing-dependency failures in the initial clone are
environment failures; no acceptance guards were relaxed.

Live-model probes use the candidate system prompt/tool schemas and actual main
model configuration. SQL transactions are read-only, Redis is mocked, tool calls
are recorded but not executed, and responses use clearly labelled catalog
snapshots. This is intent/tool-plan evidence, not fresh Zoho stock or WhatsApp E2E.

## Model observations and limits

Six of six authorized requests used against `z-ai/glm-5.3-flash`; recorded
provider cost USD 0.045969111. All three first responses selected catalog search:
- `sure`: four-seat workspace and seating configuration.
- comparison: separate LUMA 9719-4 and NOVO four-person searches.
- alternatives: black chair alternatives, four seats; also attempted to record
  an unverified SKU. The real tool validates SKUs before saving (covered locally).

Do not count this as three fully accepted final answers. The comparison probe
fixture took the first 30 sorted matching catalog rows and omitted the actual
four-person NOVO SKU. The model then incorrectly generalized absence from that
subset. This is a probe-fixture limitation plus an observed model overclaim; the
final prompt now explicitly forbids treating partial or empty search results as
proof that a product does not exist. That final prompt refinement was checked
locally, not by a seventh paid call. Real DB readback confirms both LUMA 9719-4
and NOVO 2400 four-person records are active and have searchable embeddings.

Probe source release was 7526b16; subsequent tool-module extraction preserved
the schemas/behavior, followed by the prompt clarification above. No full
WhatsApp/Zoho tool-execution acceptance is claimed. Testers can now exercise the
actual deployed flow; future model misunderstandings cannot be ruled out.
Private evidence: `/home/me/.local/state/treejar/tj-tn29/`.

## Deployment evidence and delivery tail

App and worker recreated at 12:14 UTC on 2026-09-17. Startup briefly returned
502 while Uvicorn initialized; subsequent public health is 200 with the exact
release SHA and healthy Redis/database. Both containers use the accepted image.
Eight changed app source hashes match local source; worker engine/intent-module
hashes match, as do preserved reset files. Host engine matches the image.
Environment SHA-256 is unchanged. Restore mode is true; allowed channel stays
`b49b1b9d-757f-4104-b56d-8f43d62cc515`; worker registers only
`process_incoming_batch`, with zero cron jobs and no embedding warmup.
Ordinary queue and in-progress jobs were empty before cutover; queue empty after.
No synthetic customer messages, DB repair, resets or held-message changes.

`tj-a1bi` tracks integration into main while preserving the running test worker.
Ordinary main CI currently uses app-only deployment and would stop it; the
authorized source-overlay release is live independently of that delivery tail.
