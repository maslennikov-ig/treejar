# Stage `tj-final27-client-handoff`

Status: accepted and delivered.

## Outcome

- A final record-editing log filter removes HTTP(S) paths, queries and userinfo
  before active application handlers format records. Telegram is covered
  without depending on the `httpx` logger name; Wazzup signed upload URLs and
  catalog image URL/exception logging were also removed.
- Owner decision 2026-08-14: the Telegram token is not rotated. The observed
  copy stayed only in standard output on the owner-controlled server, where the
  same value already exists in `.env`; it did not enter an external collector,
  CI, Git, documentation or a protected artifact.
- The final outbound boundary deterministically keeps the selected turn
  language and folds the name question into the one substantive question.
  Two-character openings are covered without a prompt change.
- `tj-08ve`, `tj-final27.19` and `tj-final27.20` are closed. All 19 children
  of `tj-final27` are complete.

## Measurement

Protected path:
`.git/codex-orchestration/corpus-bridge/tj-08ve-round-20260814c`.

- Preflight: 19 priced / 1 withheld, exact AED 139 / 58 anchor, zero paid calls.
- Paid execution: 20 Luna generation calls, no repair or scoring calls,
  $0.006586 total under the $0.05 cap.
- Root read 20/20 blind and free. No second reader.
- Acceptance: 20/20 turn-language matches, 20/20 valid readings, zero critical
  failures, and one literal question marker in every reply.
- Raw mean 12.7 and weighted mean 15.2. Paired against
  `tj-final27.18-round-20260814b`: raw delta -0.10 (95% -0.25 to 0.00);
  weighted delta -0.14 (95% -0.35 to 0.00). Both are inside the 2.0 reader gap.
- Rule score / ceiling / paired delta: r1 2.00/2.00/0.00; r2
  1.85/2.00/0.00; r3 2.00/2.00/0.00; r4 2.00/2.00/+0.05; r5
  1.75/1.95/-0.05; r7 2.00/2.00/0.00; r8 1.67/2.00/-0.33 (n=6); r9
  2.00/2.00/0.00 (n=6).

Named defect movement is recorded in the client pack. The critical
second-language form and two-question greeting are gone; four low-score forms
are newly named; wrong-family, product-led and internal-machinery wording
remain unchanged and noncritical.

## Verification and delivery

- Ruff check and format: passed.
- Mypy: passed over 177 source files.
- Full pytest: 3832 passed, 20 skipped, 0 failed. Relative to the supplied
  3822/20/0 baseline, the exact +10 is two safe-logging tests, six outbound
  reply-guard tests, and two corpus/production-boundary tests. Skips are
  unchanged.
- The first formal closeout run had five documentation-maintenance failures:
  three direct traceability-digest checks, one repin self-check and one required
  handoff-shape check. The handoff received its required next-stage fields and
  the declared current-state source was re-pinned; no product code changed.
- Process verification: passed.
- Protected raw replay: current `1b425bd1…` versus frozen `1fc87c04…`,
  exactly seven differences only on dialogs 28, 875 and 1291; no re-baseline.
- GitHub Actions run `31805222594`: passed and deployed
  `f5be6a26b292b81da1288ca3c394ceac21eb57a3`.
- Production `/api/v1/health`: OK with that exact SHA.
- Safe production scan: zero complete access URLs, zero query-bearing URLs and
  one expected redacted marker. Synthetic deployed guard readback: one question
  marker and zero second-language letters.

## Documentation and graph review

- `docs-reviewed: updated` — handoff, client pack, artifact and this summary
  carry current behavior and evidence.
- `project-index: reviewed-no-change` — no stable entrypoint or ownership
  boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Explicit defers

- `tj-jlx4` is excluded by the owner from this task.
- Reader-gap drift re-read remains separately tracked in `tj-4q79`; this round
  did not buy or use a second reader.
- No real customer message was sent during final readback; only synthetic,
  no-body checks were authorized and needed.
