# Stage tj-vz7o-openings Summary

Updated: 2026-08-10
Status: accepted; stage closeout passed

## Boundary

One local measurement slice closes `tj-vz7o.3`, `tj-vz7o.6`, and
`tj-vz7o.7`; prepares but does not send the decision texts for `tj-vz7o.8` and
`tj-vz7o.9`; and records the exact authority request that leaves `tj-vz7o.4`
open and keeps `tj-vz7o.5` dependent. No paid call, live traffic, production
mutation, deploy, push, or real-user message belongs to this stage.

## Ownership

- Root owns Beads, corpus access, tracked code and reports, integration, the two
  manual transcript reads, the one final acceptance set, and local commits.
- Blind-reader streams may write only raw score files under the protected
  git-common-dir run. Each reader sees at most 13 packets and no applicability
  map, build identity, baseline, or peer score.

## Acceptance intent

Run the exact release gates named by the user, process verification, the stage
readiness check, and one `slice_acceptance` closeout command that covers the
focused corpus-bridge tests and protected derived evidence. The working tree
must finish clean and nothing is pushed.

## Documentation

`no external/versioned boundary` — the work is governed by the local frozen
specification, stored packets, private corpus note, and repository code.

project-index: reviewed-no-change — only the active stage pointers changed; no
repository entry point or ownership boundary changed.

docs-reviewed: updated - measurement report, current-state handoff, frozen
integer-only scenario manifest, and unsent decision drafts now record this slice.

## Result by Beads issue

- `tj-vz7o.3`: ready to close. The same 53 packets over 19 scenarios received
  106 reads from nine readers, with exactly 15 scores per file and no
  applicability fields. Raw mean 18.71/30, another-scenario interval +/-1.66;
  paired correction from 13.58 is +5.13 +/-1.35. Mean absolute raw reader
  disagreement is 1.08 over 53 double-read packets.
- `tj-vz7o.6`: ready to close. Humans answered 8452/9477 customer messages in
  1400 dialogues, 89.18% with 84.22%-90.46% cluster interval; first reply median
  1080 seconds with 840-1890 interval over 1223/1358 answered openings. Noor
  answered 141/141 messages in 53 packets over 19 scenarios, 100%-100%; first
  reply median 15.61 seconds with 9.99-21.51 interval over 53/53 packets.
- `tj-vz7o.7`: ready to close. Seed 20260810 froze 20 openings, five per length
  stratum, from 629 evaluated natural openings within the 687 natural-text
  population. The stored human raw baseline is 5.60/30 with 3.91-6.45 manager
  cluster interval over 20 dialogues and five managers.
- `tj-vz7o.4`: must remain open. No paid call was made; the exact authority ask
  is 53 `claude-haiku-4.5` calls over the stored packets, raw transcript only.
- `tj-vz7o.5`: remains dependent on `.4` and was not started.
- `tj-vz7o.8` and `.9`: decision texts are drafted and unsent; both remain open.

## Manual transcript read

Two selected human dialogues were read in full. One showed four customer
messages before the first seller response and an eventual delivery reply that
still did not resolve the delivery charge. The other showed the automated
footer, three catalogues, and a request for an on-site measurement reduced to a
location question before the customer later said they had chosen someone else.
The read confirms that “answered” is not “resolved” and supports no causal or
outcome claim.

## Protected evidence

- Map-free inputs and scores:
  `<git-common-dir>/codex-orchestration/noor-e2e-acceptance/remediation-live/tj-vz7o-map-free-20260810/`
- Frozen opener text:
  `<git-common-dir>/codex-orchestration/corpus-bridge/tj-vz7o-real-openings-20260810/scenarios.json`
- Corpus remains at
  `<git-common-dir>/codex-orchestration/treejar-dialogs-corpus/`.

All three roots use 0700 directories and 0600 files where the sensitive payload
is stored. No corpus message, company, or amount entered the working tree.
