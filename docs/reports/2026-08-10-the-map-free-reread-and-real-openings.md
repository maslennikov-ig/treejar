# The map-free re-read and the real-openings baseline

## Result

The applicability-map confound is removed. The same 53 stored bot packets over
19 scenarios received 106 independent blind reads from nine readers, with 11–12
packets per reader. Every one of 1590 criterion reads scored all 15 rules from
the transcript alone; the score files contain neither `applicable` nor `n_a`.

On the client's raw /30 convention, the map-free result is **18.71/30 ±0.31**
for another read of this fixed 53-packet, 19-scenario set and **18.71/30 ±1.66**
for another draw of scenarios. Mean absolute reader disagreement is **1.08 raw
points across 53 double-read packets**.

Against the previous applicability-mapped reading of **13.58/30 ±0.26** for
another read of the same 53 packets and **13.58/30 ±1.11** for another draw of
19 scenarios, the paired change is **+5.13/30 ±0.25** on the fixed set and
**+5.13/30 ±1.35** on another scenario draw. The change is larger than its own
between-scenario interval, so it moved. It is a measurement correction, not a
build improvement: the build and all 53 packet transcripts stayed fixed.

The judge confound remains. The client reports **6.05/30 ±about 0.85**, clustered
over 1247 evaluated dialogues from 1400 unfiltered dialogues, five manager
groups, and one group contributing about 67%. Their judge is
`claude-haiku-4.5`; this panel is a different blind reader class. The project has
already observed a 3.8-point judge shift on identical text. Therefore this
report does not subtract 6.05 from 18.71 and does not print a ratio. That bridge
is `tj-vz7o.4`.

## Response coverage and first reply

“Substantive” means a later non-empty seller text in the same heuristically
7-day-cut dialogue. The one repeated WhatsApp call-footer text is excluded when
it occurs in at least 100 dialogues, contains the masked phone token, and is at
least 200 characters. This excludes 1121 boilerplate messages; the client's
continuity flag finds the footer in 1136 of 1400 dialogues, so 15 flagged
variants remain in the human side and can only bias its coverage upward.

| Side | Customer messages answered | Coverage, clustered 95% interval | First reply observed | Median first reply, clustered 95% interval |
|---|---:|---:|---:|---:|
| Treejar salespeople | 8452 / 9477 customer messages in 1400 dialogues | 89.18%, 84.22%–90.46%, clustered over 7 raw manager labels | 1223 / 1358 dialogues with a customer message | 1080 s, 840–1890 s |
| Noor stored packets | 141 / 141 customer messages in 53 packets over 19 scenarios | 100.00%, 100.00%–100.00%, clustered over 19 scenarios | 53 / 53 packets | 15.61 s, 9.99–21.51 s |

The corpus reader reproduces the client's continuity block exactly: 478 of
1400 dialogues end with a customer message unanswered in-channel, while 922 of
1400 end with a seller message unanswered by the customer. These are channel
continuity facts, not outcomes.

## Frozen real-opening scenarios

The opening classifier reproduces the corpus population without exporting any
message text into the working tree: 1358 of 1400 dialogues have a customer
opening; 525 of those 1358 share the dominant 48-character lead-template
prefix; 146 of 1358 are an attachment filename or a non-text attachment; and
687 of 1358 are natural text with a median length of 21 characters. Attachments
cannot be reproduced because their files were not exported.

Seed **20260810** selects 20 openings from the 629 evaluated natural-text
openings, five from each of four length strata. The tracked manifest contains
only `dialog_id` and integer-derived fields. The protected full set is stored at
`<git-common-dir>/codex-orchestration/corpus-bridge/tj-vz7o-real-openings-20260810/scenarios.json`
with directory/file modes 0700/0600.

The no-call baseline attached to this frozen set is the client's already stored
human-dialogue raw score: **5.60/30 with a 95% manager-cluster interval of
3.91–6.45**, over the selected 20 dialogues and five manager groups. This is a
human baseline on the selected openings, not a Noor build baseline. No model
call, live traffic, deployment, or production mutation was used to create it.

## Two transcripts read by eye

Two selected corpus dialogues were read in full, with no text copied into a
tracked artefact.

- In the first, four customer messages — including a request for exact photos
  and an attachment — arrived before the first seller reply. The later delivery
  question did receive an answer, but the reply still asked for quantity and
  location instead of confirming a delivery option or charge. This is why
  “answered” must not be read as “resolved”.
- In the second, the automated contact footer arrived first. A human seller then
  sent three catalogue files and asked the customer to choose, rather than
  helping replace an existing reception desk. After the customer asked for an
  on-site measurement, the only next question was location; the customer later
  wrote that they had chosen someone else. That sequence is observable, but it
  does not establish causality or an off-channel sales outcome.

The manual read supports a narrow claim: Noor answers every stored opening and
does so faster on these packets. It does not show conversion, revenue, deal
size, close rate, or that Noor closes deals. Outcomes are visible in-channel for
only 192 of 1400 corpus dialogues, and rules 12, 14, and 15 reached the
conversion phase in only one of 53 bot packets.

## Decision drafts and remaining gate

The rule-11 owner decision (`tj-vz7o.8`) and rubric-validity client question
(`tj-vz7o.9`) are drafted beside the stage summary and have not been sent.
`tj-vz7o.4` remains the external authorization boundary: exactly 53 paid
`claude-haiku-4.5` calls over the stored bot packets, using the client's exact
evaluator prompt if supplied or an explicitly labelled reconstruction from
`rubric.json` anchors. `tj-vz7o.5` remains dependent on that arm.
