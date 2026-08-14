# Orchestrator Handoff

Updated: 2026-08-14
Current branch: `main`
Current stage id: `tj-l6pw-outbound-guard-repair`
Status: accepted, deployed, and ready for client handoff.
Previous stage `tj-final27-client-handoff` stays accepted history.

Documentation: no external/versioned boundary - repository code and pinned
protected evidence define this delivery.

## Current truth

- Code release `d30b2d918f75353b3ad75438b29b409a2776cdca` deployed through
  GitHub Actions run `31811997412`; public `/api/v1/health` returned that
  exact SHA. The measured round was generated on `f5be6a26…`, and the
  difference between the two is the audit repair in
  `tj-l6pw-outbound-guard-repair`.
- The final client pack keeps the measurement boundary at the start: the
  opening stand charges 8/15 rules, seven rules are unreachable there, and deal
  outcomes exist for only 192/1400 dialogues.
- The pinned protected opening anchor remains
  `Chairs from AED 139, desks and workstations from AED 58.`; preflight is 19
  priced and one withheld.
- Customer-facing output passes through one final deterministic boundary. It
  stays in the language selected for the current turn. It also folds the
  canonical name question into an existing question, and the first turn is
  rebuilt by the opening guard, so a first turn carries one question marker;
  there is no general one-question guarantee on a later turn. This covers
  two-character openings and bare greetings without changing the model prompt,
  rubric, applicability map or language threshold.
- That boundary decides language per side, not by a shared ratio. An Arabic
  reply keeps the customer's language when it carries Arabic of its own, so
  naming three Latin-script catalog products, quoting a price or carrying a
  link no longer costs the customer the answer. An English reply still may not
  carry Arabic script. When the removed sentence was the only place a first
  turn asked anything, one work-led question is restored in the selected
  language.
- Application logs pass through a record-editing filter on every active
  handler. Every HTTP(S) URL is reduced to scheme and host plus a redacted
  marker, removing path, query and userinfo independently of logger or client.
  Wazzup upload URLs and catalog image URL/exception logging were also removed.
- Owner decision 2026-08-14: do not rotate the Telegram token. The observed
  copy stayed only in standard output on the owner-controlled server, where the
  same value already exists in `.env`; no external collector exists, CI does
  not call Telegram, and Git, documents and artifacts contain no copy.

## Accepted measurement

- Protected path:
  `.git/codex-orchestration/corpus-bridge/tj-08ve-round-20260814c`.
- Exactly 20 paid `openai/gpt-5.6-luna` generation calls; no repair, scoring
  or second-reader calls. Actual cost $0.006586 under the $0.05 cap. Root read
  all 20 blind and free.
- Acceptance: 20/20 non-empty outputs, 20/20 valid readings, 20/20 replies in
  the selected turn language, zero critical failures, and exactly one question
  marker in every reply.
- Raw mean 12.7; weighted mean 15.2. Against
  `tj-final27.18-round-20260814b`, raw delta is -0.10 (95% -0.25 to 0.00)
  and weighted delta is -0.14 (95% -0.35 to 0.00). Both lie inside the 2.0
  reader gap and support no total-score quality claim.
- Rule score / ceiling / delta: r1 2.00/2.00/0.00; r2 1.85/2.00/0.00; r3
  2.00/2.00/0.00; r4 2.00/2.00/+0.05; r5 1.75/1.95/-0.05; r7
  2.00/2.00/0.00; r8 1.67/2.00/-0.33 (n=6); r9 2.00/2.00/0.00 (n=6).
- The client pack names new, gone and unchanged defect forms without carrying
  protected request or reply bodies.

## Verification

- Ruff check and format: passed.
- Mypy: passed over 177 source files.
- Full pytest: 3842 passed, 20 skipped, 0 failed. The +10 over the deployed
  3832/20/0 is exactly the focused cases of `tj-l6pw-outbound-guard-repair`.
  Skips are unchanged.
- Stored-round replay of the shipped output path over
  `tj-08ve-round-20260814c` with no paid calls: 18 of 20 replies byte-identical
  and dialogs 293 and 1291 each gaining one work-led question folded into the
  name ask. One question marker everywhere; no content and no language changed.
- Process verification: passed.
- Raw replay retained `1b425bd1…` against frozen `1fc87c04…`, exactly seven
  expected differences only on dialogs 28, 875 and 1291.
- Production safe scan found zero complete access URLs and zero query-bearing
  URLs. A synthetic deployed readback found one redacted marker, one question
  marker, and no second-language letters.

## Beads and package

- `tj-08ve`, `tj-final27.19` and `tj-final27.20` are closed.
- Parent `tj-final27` has 19/19 children complete and is closed.
- `tj-l6pw`, `tj-yiiq`, `tj-lo92` and `tj-jgns` came out of the audit of that
  accepted stage and are closed by `tj-l6pw-outbound-guard-repair`.
- Client pack: accepted for handoff; the language, logging-safety and
  double-question blockers are removed. Its deployed baseline names
  `d30b2d9…` and carries the audit repair beside the measured round.

## Next recommended

Next stage id: not opened
Recommended action: hand the accepted client package to the owner. Open a new
stage only for separately authorized work, and start from the deferred opening
defects if that work is quality of the first reply. Do not reopen the accepted
`tj-final27-client-handoff` or `tj-l6pw-outbound-guard-repair`.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a new, separately authorized goal. Treat
`tj-final27-client-handoff` as accepted history, keep `tj-jlx4` outside this
delivery, preserve the frozen raw replay, and never use `--second-reader`
without a fresh explicit owner request.

## Explicit defers

- `tj-s6ah`, `tj-gwg1`, `tj-2f1u`, `tj-c58g` and `tj-q88k` carry the opening
  defect forms that `tj-08ve-round-20260814c` named and nothing tracked: two
  discovery subjects in one question on 442 and 819, a product outside the
  customer's family on 436, catalog-category discovery on 420 and 1000,
  internal machinery wording on 1067, and role discovery continuing after a
  recruitment redirect on 28. None is a critical failure; none blocks handoff.
- `tj-jlx4` is explicitly outside this task.
- Reader-gap drift re-read remains tracked separately in `tj-4q79`; no second
  reader was authorized or used.
- Referral activation remains an excluded client decision. The implemented
  mechanics remain disabled.
- No real customer message was sent during final readback; only synthetic
  no-body verification was performed.
