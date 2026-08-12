# Stage tj-q1a2-one-reply-owner

Status: accepted
Base: `main` at `56227dc`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — the behavior is owned by the
repository's local reply-policy contract, implementation and tests.

## Outcome

D1-D6 move reply ownership from post-generation text guesses into pre-generation
state. The opening guard removes at most one duplicate introduction sentence; a
current-message name prevents a duplicate ask; the name-ask slot records what
was actually sent; and one immutable permitted-ask set feeds prompt and guard.
The first-turn question fold retains its unchanged `REDUCING` proof.

`tj-w224` corrects three things this stage got wrong and was accepted with.
D1 originally treated any mention of the company as an introduction, which
deleted sentences that answered the customer and stripped the canonical opening
off quotation replies; an introduction is again our persona *and* our company,
now also in Arabic script. The `this is X from Y` name extraction was unbounded
and stored names like "a follow-up"; it is now one or two words and never a
determiner. `notify_on_failure_override=False` had been hardcoded into the
production repair-judge call to satisfy a diagnostic constraint; only the
diagnostic replay passes it now.

The repair judge is unanchored from deterministic repair. Validated deterministic
grounding repair is the fallback, with manager escalation only when it leaves
Noor's own opening plus a question and no answer content. Diagnostic calls cannot
page a manager.

## Protected proof

- Frozen baseline: `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
- Current replay: `825f26ca85533b6d6499b4606a2e0fcb87df1ee10ce7fba2dbd434381b965900`;
  55 intended changed records across three runs. One reply is grounding-flagged,
  `tj-vz7o-luna-glm-20260810-rerun/789`, which is the baseline's own behaviour
  restored by `tj-w224` and is what the repair path exists for.
- D6: eight calls, four each for dialogs 819 and 789, zero failures, zero stubs,
  notifications disabled on all eight, cost $0.00066402. Dialog 789 escalated
  4/4 by the stated rule; dialog 819 escalated 0/4 and shipped a substantive
  reply. The judge itself delivered nothing in 8 of 8: 819 was rejected four
  times as `correction_still_flagged`, 789 four times as
  `correction_has_no_answer`, and every delivery came from the deterministic
  fallback. `tj-3h0w` then re-measured this with twenty approved calls under
  current code: 0/20 byte-identical to the deterministic candidate, 819
  delivered 0/10 judge corrections and 789 delivered 2/10, and eighteen of
  twenty deliveries came from the deterministic fallback. The judge approved a
  guard-flagged 819 reply 2/10, which is `tj-uhbq`.
- Corpus text stayed outside Git. The tracked artifact contains ids, counts,
  explanations and digests only.

## Verification

Focused D1-D5 tests passed (960), the full engine file passed (823), and the
focused D6/policy set passed (102). Ruff, format, Mypy and process verification
are green. Final full Pytest passed with 3641 tests and 19 environment skips,
re-run after `tj-w224`.
Stage closeout also passed its affected-package (107), security (29),
concurrency (102) and integration (145) selections.

docs-reviewed: updated — this summary, the artifact and handoff record the
durable behavior and privacy-safe proof.

project-index: reviewed-no-change — no module was added, removed or moved.

graph-reviewed: no-change-needed — Graphify is not initialized.

## Risks / Follow-ups / Explicit defers

No in-scope product defect is deferred. `tj-2m5m.4` remains separate discovery
work. `tj-9e15` and `tj-3h0w` are closed. `tj-uhbq` carries one owner decision:
whether a paid judge may override a deterministic grounding flag. The push to
`origin/main` was authorized; no deploy, runtime mutation or model-configuration
change occurred.
