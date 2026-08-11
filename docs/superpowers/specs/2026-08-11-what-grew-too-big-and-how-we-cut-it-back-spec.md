# What grew too big, measured — and the order in which we cut it back

Date: 2026-08-11
Beads epic: `tj-rt7w`
Build audited: `8cfbe91`

This is an audit of over-complication, not of correctness. Every number below was
measured on the tree at `8cfbe91`; nothing here is an impression. Where a claim
could not be measured it is marked as an opinion and labelled.

The conclusion in one line: **the complexity is live, not dead.** Only 41 lines
of `engine.py` are unreachable. Nothing can be deleted for free, so this is a
programme of consolidation, not of cleanup.

---

## Part 1 — What was measured

### F1. One file holds a third of the runtime, and it is still doubling

| | lines |
|---|---:|
| `src/` total | 59 690 |
| `src/llm/engine.py` | **17 380** (29% of `src/`) |
| next largest, `src/services/chat.py` | 1 692 |

`engine.py` holds **470** function definitions, 443 of them private, and 26
classes. Its growth, sampled from its own history:

| date | lines |
|---|---:|
| 2026-04-01 | 926 |
| 2026-05-05 | 2 697 |
| 2026-05-26 | 7 429 |
| 2026-06-09 | 10 418 |
| 2026-07-29 | 11 526 |
| 2026-07-30 | 14 161 |
| 2026-08-09 | 16 941 |
| 2026-08-11 | 17 380 |

**+5 854 lines in the twelve days after 29 July.** In the last thirty days,
**108 of 428 commits** touched this one file — one commit in four.

The single worst structure inside it is `process_message`: **1 827 lines**, with
**17 nested closures**, spanning `L15554–L17380`.

### F2. There are four exits, and they do not agree

Every customer-facing reply leaves `process_message` through one of four
closures, and each applies a different subset of the post-processing chain:

| exit | guards applied | grounding? |
|---|---|---|
| `_build_llm_response` | 7 | yes |
| `_build_static_response` | 3 | **no** |
| `_build_policy_handoff_response` | 1 | **no** |
| `_build_verified_catalog_recovery_response` | 3 | **no** |

This is not hypothetical. The "UAE delivery with installation" clause — an
unverified service commitment — reached a customer precisely because a static
reply skipped grounding. That was fixed at the wording; **the structure that let
it out is unchanged**, and three of four exits still bypass the policy.

No test asserts that the four chains agree. Repo-wide, the three short exits are
named in exactly **one** test line, and that test is about route naming.

### F3. The guards cannot be tested where they live

`_apply_first_turn_opening_guard`, `_apply_selling_turn_guard`,
`_repair_closed_questions` and the four exits are **closures defined inside
`process_message`**. Consequences, all three structural rather than stylistic:

- they are unreachable from a unit test — the only way in is a full
  `process_message` call with a database, Redis and a mocked model;
- they cannot be reused by the acceptance harness, which is why the harness
  measured "model plus one guard" for an entire round;
- they are rebuilt on every turn.

### F4. Money is parsed four different ways

393 regex operations in `src/`, **196 of them in `engine.py`**. There is no
shared money module — `find src -name '*money*' -o -name '*amount*' -o -name
'*currency*'` returns nothing. The amount pattern exists in four independent
copies:

| module | pattern shape |
|---|---|
| `src/llm/engine.py` | `AED\|DHS\|dirhams?`, four variants, named groups |
| `src/llm/fact_extractor.py` | `AED\|DHS\|dirhams?`, four variants |
| `src/llm/grounding_output.py` | `\bAED\b\|درهم` with decimal canonicalisation |
| `src/llm/opening_guard.py` | `\bAED\b\|درهم`, presence only |

So a price the extractor recognises is not necessarily a price grounding
recognises, and only one of the four canonicalises `290` against `290.00`. That
mismatch is exactly the class of defect that produced five false criticals in the
2026-08-10 round.

### F5. A guard may delete the whole reply, and did

Nothing bounds what post-processing may remove. Measured cost on 2026-08-10:
`_drop_identity_sentences` blanked **4 of 20** replies end to end — every one of
them a bare greeting, which is 34% of real traffic. The trigger was one
character, a typographic apostrophe.

The defect is fixed. **The absence of a bound is not.** Any future guard can
repeat it, and no test will notice, because the tests assert what a guard removes
and never what it must leave behind.

### F6. The deterministic paths are 8 259 lines, and the project already measured them as worse

| module | lines |
|---|---:|
| `src/llm/verified_answers.py` | 1 355 |
| `src/dialogue/claim_contract.py` | 1 135 |
| `src/llm/order_quote_routes.py` | 1 060 |
| `src/dialogue/runner.py` | 890 |
| `src/dialogue/order_state.py` | 703 |
| ten more | 3 116 |

`tj-swgu` measured the counterfactual on this project's own scenarios:
**22.8 comparable where the model wrote every substantive turn, 13.3 where a
template replaced at least one.** Thirteen of that epic's fourteen children are
closed, and the finding has not been carried into the paths above.

### F7. The refactoring tax is already on the books

90 447 lines of tests against 59 690 lines of source. `tests/test_llm_engine.py`
alone is **23 577 lines — 26% of the whole suite**. Any move inside `engine.py`
pays there first. This is stated so the cost is not discovered mid-way; it is not
an argument against the work.

### F8. There is almost nothing to delete

Nine private functions in `engine.py` are unreferenced repo-wide, totalling
**41 lines** — 0.2%. Every other line is wired into something.

This is the finding that shapes the whole plan. There is no cleanup available.
Each step below has to *replace* a structure while it is carrying traffic.

---

## Part 2 — Six rules the fix cycle holds to

**R1. One exit.** Every customer-facing reply leaves through one function that
applies one chain. Provenance and cost may differ per path; the text policy may
not.

**R2. A guard may delete a sentence, never a reply.** Enforced as an invariant in
the chain itself, not as a convention: if post-processing turns a meaningful
reply into one with no meaningful sentence, the guard is wrong and the pipeline
keeps the previous text and records a defect. Character count is not a validity
signal: a safe repair may legitimately be much shorter. What the reply says is
owned by the guard-specific semantic validator. This one rule would have caught
F5 the day it shipped.

**R3. Guards are modules with pure functions.** `(text, explicit state) -> text`.
No closure over `process_message`, no database, no Redis. Unit-testable, and the
acceptance harness imports the same objects production runs.

**R4. One money parser.** One module owns "is this an amount, and what amount is
it", with one canonical form. Extraction, grounding and the guards all call it.

**R5. No new guard until the prompt has been tried and measured.** F6 is the
evidence. A guard is admissible when the model was instructed and still failed on
measured text — and the beads issue says which measurement.

**R6. A refactor and a behaviour change never ride in the same measured round.**
The project already holds this for the scenario set; it now holds for structure.
Structural steps must be provably behaviour-preserving: same suite, no test
edited to accommodate the move.

---

## Part 3 — The order of work

Sequenced so that each step is safe to stop after. Steps 1–2 are safety; 3–6 are
structure; 7 is measurement.

### Step 1 — The unverified service commitment (`tj-vz7o.12`, finding 789)

The only item that is a customer-facing safety defect rather than structure.
Asked "do you buy office table i have", Noor replied that Treejar can sell or
assess it. Same class as the two criticals already fixed. Per R5 the prompt is
tried first; a grounding rule only if the prompt is measured to fail.

*Not behaviour-preserving.* Ships alone.

### Step 2 — The damage bound (R2)

Add the invariant to the chain, with a test per existing guard proving it cannot
blank a reply. Expected to change no output on the current corpus — if it does,
that output was already a defect and the run says so.

### Step 3 — One money module (R4)

Move the four patterns behind one module with one canonical form. Pure movement,
no behaviour change. Measured by: all four call sites agree on the 20 stored raw
outputs.

### Step 4 — Guards out of the closure (R3)

Lift `_apply_first_turn_opening_guard`, `_apply_selling_turn_guard`,
`_repair_closed_questions` and `_guard_premature_quote_detail_collection` into
`src/llm/response_policy.py` as pure functions taking explicit state. No logic
change; the closures become one-line calls.

### Step 5 — One exit (R1)

Collapse the four exit closures onto one `render_reply()` that applies the full
chain, with per-path provenance passed in rather than branched on. This is the
step that closes F2. It **will** change behaviour on the three short paths, since
they begin to run grounding — so it ships alone, after Step 4, with the changed
outputs read by eye before anything else moves.

### Step 6 — Split `process_message`

Only after 4 and 5, because they remove most of the closure state that makes the
split hard. Target: `process_message` under 300 lines, `engine.py` under 12 000,
with catalog planning, quote/order routing and response rendering as their own
modules.

**This step is intended, not optional.** It differs from steps 1–5 in kind, not
in importance: each of those closes a defect that has already happened and been
measured, while this one closes none and instead makes future change cheaper.
That is a different sort of claim and deserves a different sort of decision, so
its *size* is settled after Step 5 rather than now — steps 4 and 5 will have
removed perhaps 1 500–2 000 lines and most of the closure state, and the
remaining difficulty can then be measured instead of estimated.

What it must not become is indefinite deferral. Steps 4 and 5 do not flatten the
growth curve of F1 on their own; at +5 854 lines in twelve days, skipping this
step returns the same audit in a month against a larger file.

### Step 7 — Re-measure

One paired round on the frozen twenty openings after Step 5, per R6, against
`8cfbe91`. Expected result is **no score movement** — the steps above fix
structure, and the project's rule is that movement smaller than the instrument's
uncertainty is not evidence. What the round is actually for is the critical-failure
count and a read of the three previously ungrounded paths.

---

## Part 4 — What this audit does not claim

- **It does not claim the system is broken.** Gates are green at `8cfbe91`:
  3 503 tests pass, ruff, format and mypy clean. Over-complication is a cost on
  future change, not a present failure.
- **It does not claim a score will improve.** No step above targets the rubric.
  Anyone reporting a score move from this work must show it exceeds reader noise.
- **It does not claim the deterministic paths should be removed.** This is the
  largest simplification available — 8 259 lines — and it is left out on purpose.
  F6 measures those paths as scoring worse; it does not measure what breaks
  without them, and they carry fact guarantees and side effects that reach
  quotations, orders and the CRM. Retiring any of them is a separate decision
  with its own evidence, and should not begin until steps 1–6 are closed.
- **Line counts are a proxy.** They locate concentration, not badness. F2, F3,
  F4 and F5 are the substantive findings; F1 is where they live.
