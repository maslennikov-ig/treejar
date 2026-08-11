# Stage tj-rt7w-real-split

Status: in_progress
Base: `main` at `19556ba`
Acceptance owner: root orchestrator (Claude)

Documentation: no external/versioned boundary — internal first-party Python,
no new dependency, no public contract or version-sensitive behaviour changed.

project-index: reviewed-no-change — no module added, moved or renamed so far;
the extractions land inside `src/llm/message_processor.py`.
graph-reviewed: no-change-needed — Graphify is not initialised.

## Goal

`tj-rt7w.10`. `tj-rt7w.6` reported `process_message: 40 lines` and delivered a
facade over a 2,044-line function with 15 nested closures. Close F1 and F3 for
real: no function on the `process_message` path over 300 lines, with the turn's
phases as named functions over explicit state.

Behaviour-preserving throughout. The guard and policy sources must stay
byte-identical, no existing test may be edited, and the twenty stored raw
outputs must replay unchanged.

## Step A — the closures that were nested only because everything was

Eight of the fourteen closures are out, and none of them needed a design
decision first; the capture analysis showed why.

| closure | lines | captured |
|---|---:|---|
| `_is_first_turn` | 17 | nothing |
| `_has_escalation` | 2 | nothing |
| `_deferred_product_media_for_response` | 42 | nothing |
| `_get/_set/_clear_verified_policy_repair_state` | 25 | `conv`, `db` |
| `_ensure_model_runtime` | 20 | `db`, a `nonlocal` memo |
| `_run_prose_agent` | 14 | the memo |

The first three closed over nothing at all. The repair-state trio closed over
exactly the conversation and the session, which is state passed in, not state
captured; its twenty call sites keep their zero-argument shape through a
`partial` bound once the conversation is loaded — several of them hand the
clearer to the order/quote adapter as a `Callable[[], Awaitable[None]]`, so that
shape is load-bearing. `_ensure_model_runtime` was a closure over a `nonlocal`
where the memo and the memoized thing shared one name; it is now
`_LazyModelRuntime`, which can be read and tested on its own.

Result: **1,947 → 1,830 lines, 14 → 6 closures.** Guard and policy sources
unchanged. No existing test edited.

## Step B — the response builders (next)

The six that remain are one family: `_render_customer_reply`,
`_build_llm_response`, `_build_static_response`, `_build_policy_handoff_response`,
`_run_agent`, `_known_customer_name_for_guards` — 226 lines sharing `conv`,
`deps`, `dialogue_kernel_result`, `dialogue_kernel_mode`, `pii_map`,
`is_first_turn`, `opening_anchor_line`, `policy_decision`,
`name_gate_resume_customer_name`, `history`, `masked_text`, `latency_trace`.

Several of those are **reassigned as the turn runs**, so a `partial` bound early
would freeze the wrong value — this is why Step B needs a mutable turn-context
object and Step A did not. That object is the design decision this stage owes,
and it is also what Step C needs, so it comes first and alone.

## Step C — the sequence

~1,600 lines of straight-line orchestration, to be cut into phases over the
Step B context: load and enrich, dialogue kernel, name gate, quote-detail
capture, route selection, agent run, render.

## Verification so far

Ruff, format, Mypy clean. Focused engine and patch-point set: 821 passed. The
full suite is run at each step; the guard and policy sources are compared
byte-for-byte against `19556ba` after every extraction.
