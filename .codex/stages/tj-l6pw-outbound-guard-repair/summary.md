# Stage `tj-l6pw-outbound-guard-repair`

Status: implemented, awaiting delivery authorization.
Base: `main` at `c70e7e9`.
Acceptance owner: root orchestrator.

Documentation: no external/versioned boundary — repository code and the stored
protected round define this repair.

## Why this stage exists

The accepted stage `tj-final27-client-handoff` closed a real critical failure,
and an audit of it found four things it left behind. Accepted history is not
edited; this stage carries the repair.

## What changed

- `src/llm/language_guard.py`. The whole-reply gate no longer asks an Arabic
  reply to be 35% Arabic letters. Our catalog is named in Latin script, so that
  test also failed true Arabic answers that name three products, quote a price
  or carry a link, and the customer received a fixed sentence instead of the
  answer. The two sides are deliberately not symmetric: an Arabic sentence
  keeps the reply when it carries Arabic of its own, and an English reply
  still may not carry Arabic script, because nothing we sell needs it.
- `src/llm/outbound_reply_guard.py`. When the removed second-language sentence
  was the only place a first turn asked anything, the reply now regains one
  work-led question folded into the name ask. Bounded to a first turn: re-asking
  something a customer already answered is its own defect.
- `src/llm/opening_guard.py`. `canonical_discovery_question` states that
  question in both languages, one subject and no product list.

## Evidence

- Focused: `tests/test_llm_outbound_reply_guard.py`, 16 passed. New coverage is
  five Arabic replies that must reach the customer unchanged, one English reply
  to an Arabic customer that must still be replaced, one English reply that must
  lose only its Arabic sentence, first-turn question restoration in both
  languages, and a later turn that must never be handed a discovery question.
- Stored-round replay of the shipped output path over
  `tj-08ve-round-20260814c`, no paid calls: 18 of 20 replies byte-identical,
  dialogs 293 and 1291 changed. Both changes are the same one — the final
  sentence gains a work-led question folded into the name ask, so both first
  turns now carry a substantive question that the accepted round shipped
  without. Every reply still carries exactly one question marker. No reply lost
  content, and no reply changed language.
- Full pytest: 3842 passed, 20 skipped, 0 failed. The +10 against the
  `3832/20/0` baseline is exactly this stage's new focused cases.
- Ruff check, Ruff format and Mypy over 177 source files: passed.
- Process verification: passed.
- Protected raw replay: `1b425bd1…` against frozen `1fc87c04…`, the same seven
  expected differences on dialogs 28, 875 and 1291. No re-baseline.

No paid round was bought for this repair, and none is needed for the language
claim: the stored-round replay shows the shipped text directly. The rule-5
scores on 293 and 1291 are not restated, because a score needs a reading.

## Documentation and graph review

- `docs-reviewed: updated` — the handoff carries the corrected one-question
  wording, the per-side language rule and the new defer list.
- `project-index: reviewed-no-change` — only `current_stage_id` and the current
  stage summary pointer moved in `.codex/orchestrator.toml`; no entrypoint,
  module or ownership boundary changed.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Beads

- `tj-l6pw` (P1) and `tj-yiiq` (P2) are closed by this stage.
- `tj-jgns` (P3) is closed by correcting the handoff wording.
- `tj-lo92` (P2) is closed by opening `tj-s6ah`, `tj-gwg1`, `tj-2f1u`,
  `tj-c58g` and `tj-q88k` for the defect forms the accepted round named and
  nothing tracked.

## Explicit defers

- `tj-s6ah`, `tj-gwg1`, `tj-2f1u`, `tj-c58g` and `tj-q88k` are bounded opening
  defects carried out of the accepted round. None is a critical failure and
  none blocks handoff.
- `tj-jlx4` remains excluded by the owner.
- No second reader was authorized or used.
