# Orchestrator Handoff

Updated: 2026-08-14
Current branch: `main`
Current stage id: `tj-final27-client-handoff`
Status: accepted, deployed, and ready for client handoff.

Documentation: no external/versioned boundary - repository code and pinned
protected evidence define this delivery.

## Current truth

- Code release `f5be6a26b292b81da1288ca3c394ceac21eb57a3` deployed through
  GitHub Actions run `31805222594`; public `/api/v1/health` returned that
  exact SHA.
- The final client pack keeps the measurement boundary at the start: the
  opening stand charges 8/15 rules, seven rules are unreachable there, and deal
  outcomes exist for only 192/1400 dialogues.
- The pinned protected opening anchor remains
  `Chairs from AED 139, desks and workstations from AED 58.`; preflight is 19
  priced and one withheld.
- Customer-facing output passes through one final deterministic boundary. It
  stays in the language selected for the current turn and contains at most one
  literal question marker. This covers two-character openings and bare
  greetings without changing the model prompt, rubric, applicability map or
  language threshold.
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
- Full pytest: 3832 passed, 20 skipped, 0 failed. The +10 from the supplied
  3822/20/0 baseline is exactly two logging tests, six outbound reply-guard
  tests and two corpus/production-boundary tests. Skips are unchanged.
- Process verification: passed.
- Raw replay retained `1b425bd1…` against frozen `1fc87c04…`, exactly seven
  expected differences only on dialogs 28, 875 and 1291.
- Production safe scan found zero complete access URLs and zero query-bearing
  URLs. A synthetic deployed readback found one redacted marker, one question
  marker, and no second-language letters.

## Beads and package

- `tj-08ve`, `tj-final27.19` and `tj-final27.20` are closed.
- Parent `tj-final27` has 19/19 children complete and is closed.
- Client pack: accepted for handoff; the language, logging-safety and
  double-question blockers are removed.

## Next recommended

Next stage id: not opened
Recommended action: hand the accepted client package to the owner; open a new
stage only for separately authorized work. Do not reopen this accepted stage.

## Starter prompt for next orchestrator

Use $orchestrator-stage only for a new, separately authorized goal. Treat
`tj-final27-client-handoff` as accepted history, keep `tj-jlx4` outside this
delivery, preserve the frozen raw replay, and never use `--second-reader`
without a fresh explicit owner request.

## Explicit defers

- `tj-jlx4` is explicitly outside this task.
- Reader-gap drift re-read remains tracked separately in `tj-4q79`; no second
  reader was authorized or used.
- Referral activation remains an excluded client decision. The implemented
  mechanics remain disabled.
- No real customer message was sent during final readback; only synthetic
  no-body verification was performed.
