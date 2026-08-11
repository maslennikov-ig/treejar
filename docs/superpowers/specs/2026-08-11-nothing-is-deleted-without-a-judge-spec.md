# Nothing is deleted without a judge

Date: 2026-08-11
Build audited: `8f7b277`
Beads epic: `tj-n7p4`
Owner decision: no automatic deletions. Where there is doubt, the judge reads
it, and either corrects it — proposing better wording — or says it is fine and
approves it.

Counted on the 60 stored replies of the three measured rounds (2026-08-10 ×2,
2026-08-11). Where a claim is an estimate it says so.

---

## 1. What the reply chain does to the model's text today

`render_reply` runs six guards in order. Run the 60 stored raw model outputs
through them and count, per guard, how many replies lost a sentence:

| guard | replies touched | replies losing a sentence | sentences lost |
|---|---:|---:|---:|
| `closed_question` | 0 | 0 | 0 |
| `premature_quote_details` | 0 | 0 | 0 |
| **`first_turn_opening`** | **60** | **28** | **31** |
| `selling_turn` | 0 | 0 | 0 |
| `deferred_commitment` | 3 | 0 | 0 |
| **`grounding_output`** | **1** | **1** | **2** |

The first number is the surprise. A guard removes a sentence from **28 of 60
replies**, not from one. A first measurement by character delta showed zero cuts
for it, because it strips and prepends in the same pass and the net is positive.
That measurement was wrong and this one replaces it.

## 2. Two kinds of removal, and only one of them is the problem

Every one of those 31 sentences was classified, and all 31 are the model's own
greeting or identity line — *"Hello, I'm Noor from Treejar…"*, and its Arabic
equivalent. Zero were anything else.

The opening guard removes them because the deterministic anchor line says the
same thing verbatim, and without the strip the customer reads it twice. Nothing
is lost. So:

**Replacement.** The guard removes text and puts equivalent text in its place.
Content survives. 28 replies in 60, and no model is needed to approve a
de-duplication.

**Removal.** The guard removes text and puts nothing in its place. Content is
gone. **One reply in sixty**, all of it `grounding_output`.

That is the distinction the rule needs. Not *"never remove"* — the opening guard
must keep removing — but *"never remove without putting something in its
place"*, and where nothing can be put, the judge decides.

The four guards that never fired on this set are unexercised, not innocent:
`sales_turn_guard` contains `_drop_trailing_questions` and its own comment says
*"nothing but questions is ever dropped"*, and `opening_guard` carries
`_strip_generic_english_opening` and `_strip_legacy_identity`. They are on a
first-turn corpus that does not reach them. Each has to be **read and declared**,
not measured into safety.

## 3. The judge has three answers, not one

Owner decision. When a check fires it has found doubt, not a verdict. The reply,
the flag, and the evidence available this turn go to the judge — a model from
the other vendor, because the point is a second opinion rather than a second
try — which answers one of:

1. **Approved.** The flag was a false positive; send the text unchanged.
2. **Corrected.** Here is the reply rewritten so the flag no longer applies.
3. **Cannot fix.** Neither the text nor a rewrite is safe to send.

Answer 1 matters as much as answer 2. Today a fired detector means the text
*will* be edited, so every false positive costs the customer a sentence. Giving
the judge the power to approve is what makes the detector affordable to make
sensitive.

## 4. The five rules

**D1. No customer-visible content is removed without a replacement.** A guard
either declares itself *replacing* — and a test holds that what it removes is
covered by what it adds — or it is *removing*, and it may not edit the text at
all. It raises a flag instead.

**D2. A flag is a question, not a verdict.** The only thing a deterministic check
may do is classify. `classify_grounding_output` already exists and is pure; it
becomes the whole of the deterministic decision.

**D3. The judge answers, and may approve.** Approve, correct, or cannot-fix.
Every approval over a flag is counted separately, because that is the number
that tells us whether the judge is being used or being trusted. If a class of
flag is ever wrongly approved, that class stops being overridable — measured,
not assumed in advance.

**D4. The fallback is a handoff, never a deletion.** If the judge is unavailable,
or its correction still fails the check, escalate to a manager and say so. At the
measured rate — one trigger in sixty, and a provider failure on top of that — this
is on the order of 0.02% of turns. Falling back to the deletion would restore
exactly the behaviour being removed.

**D5. The bound still applies to the judge.** R2 is not suspended because a model
wrote the replacement. A correction that empties the reply is rejected like any
other, and the judge's output is re-classified before it is sent: a rewrite that
introduces a new violation is a failure, not an improvement.

## 5. What changes, in order

**`tj-n7p4.1` — split classification from repair.** `classify_grounding_output`
becomes the only deterministic decision. The sentence-dropping repair moves
behind one named function that nothing calls by default. Behaviour-preserving:
production still calls it, so the customer sees no change yet.

**`tj-n7p4.2` — declare every guard.** Each of the six is marked *replacing* or
*removing*, by reading it rather than by whether it fired on 60 first-turn
openings. A test holds the declaration: a replacing guard's output must cover
what it removed. This is where `sales_turn_guard`'s question-dropping and
`opening_guard`'s two strips get decided.

**`tj-n7p4.3` — the judge.** Second-vendor call on a flag, three answers,
re-classification of a correction, R2 bound applied to it. Counted per turn:
flag raised, answer given, model identity.

**`tj-n7p4.6` — the fallback.** Handoff on judge failure, counted distinctly.

**`tj-n7p4.4` — the harness follows.** `apply_shipped_output_guards` says in its
own docstring that it applies everything production would do. Once production
consults a judge and the harness deletes, the harness measures a different reply
on exactly the turns where something went wrong. It takes the same path; at one
trigger per sixty openings that is about one extra call per round.

**`tj-n7p4.5` — one measured round.** Against 2026-08-11, same judge, same
twenty. Read for: criticals do not rise; how often a flag was raised; how often
it was approved rather than corrected; and whether any correction was worse than
the text it replaced.

## 6. What this must not become

**A model call on half of all turns.** The opening guard fires on every first
turn and removes a duplicate identity line 28 times in 60. It is *replacing*, it
stays deterministic, and it never reaches the judge. If the implementation ends
up consulting a model on 47% of replies, D1's distinction has been lost.

**A judge that always agrees.** If `tj-n7p4.5` shows every flag approved, the
detector is wrong or the judge is not reading. Both are findings.

**Distrust hard-coded in advance.** D3 starts permissive on purpose. Which flags
may not be overridden is a question for measurement, not for this document.

## 7. Not covered here

- The promise registry, `tj-mshi`. Its rule P8 points at this epic; the two do
  not overlap in code.
- Retiring the deterministic routes.
- The rubric, the applicability map, and the scoring rulers. Frozen.
