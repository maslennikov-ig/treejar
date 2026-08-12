# Stage tj-q1a2-one-reply-owner

Status: accepted
Base: `main` at `56227dc`
Acceptance owner: root orchestrator

Documentation: no external/versioned boundary — the behavior is owned by the
repository's local reply-policy contract, implementation and tests.

## Outcome

D1-D6 move reply ownership from post-generation text guesses into pre-generation
state. The opening guard removes at most one duplicate identity sentence; a
current-message name prevents a duplicate ask; the name-ask slot records what
was actually sent; and one immutable permitted-ask set feeds prompt and guard.
The first-turn question fold retains its unchanged `REDUCING` proof.

The repair judge is unanchored from deterministic repair. Validated deterministic
grounding repair is the fallback, with manager escalation only when it leaves
Noor's own opening plus a question and no answer content. Diagnostic calls cannot
page a manager.

## Protected proof

- Frozen baseline: `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
- Current replay: `c842132fde97fa2fec40b7bbb5f6c7637a9a61fbc8bbeed7a2268d4f57dd7fc5`;
  56 intended changed records across three runs and zero current grounding flags.
- D6: eight calls, four each for dialogs 819 and 789, zero failures, zero stubs,
  notifications disabled on all eight, cost $0.00066402. Dialog 789 escalated
  4/4 by the stated rule; dialog 819 escalated 0/4. No judge correction equalled
  the deterministic candidate byte-for-byte.
- Corpus text stayed outside Git. The tracked artifact contains ids, counts,
  explanations and digests only.

## Verification

Focused D1-D5 tests passed (960), the full engine file passed (823), and the
focused D6/policy set passed (102). Ruff, format, Mypy and process verification
are green. Final full Pytest passed with 3640 tests and 19 environment skips.
Stage closeout also passed its affected-package (107), security (29),
concurrency (102) and integration (145) selections.

docs-reviewed: updated — this summary, the artifact and handoff record the
durable behavior and privacy-safe proof.

project-index: reviewed-no-change — no module was added, removed or moved.

graph-reviewed: no-change-needed — Graphify is not initialized.

## Risks / Follow-ups / Explicit defers

No in-scope product defect is deferred. `tj-2m5m.4` remains separate discovery
work. No push, deploy, runtime mutation or model-configuration change occurred.
