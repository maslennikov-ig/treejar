# What Noor may promise

Date: 2026-08-11
Build audited: `11e3c59`
Beads epic: `tj-mshi`
Owner decision that started this: prohibitions hold badly on Luna, so state the
permission instead.

Everything below is counted on the tree at `11e3c59` and on the 1400-dialogue
corpus. Where a claim is an estimate it says so.

---

## 1. The defect is the shape of the list, not any entry on it

Three promise defects have been found and each was answered with a new
prohibition.

| found | promise | answer |
|---|---|---|
| 2026-08-10, dialog 789 | Treejar will value or buy your used furniture | `CUSTOMER_OWNED_FURNITURE_POLICY`, a new prompt block |
| 2026-08-10, dialog 819 | assembly acknowledged and dropped | a required commitment, added |
| 2026-08-11, dialog 28 | I will route your CV and someone will call you | `tj-riim`, open, and a fourth block is the obvious fix |

The list of things Treejar does not do has no end. A fourth block buys the
fourth defect and nothing else, and the audit returns in a month against a
longer prompt. The list of things Treejar **does** do has an end, and the corpus
says roughly where it is.

Two facts make the prohibition shape worse than merely unbounded.

**It already contradicts itself.** `prompts.py:41` forbids replying *"I will
check"* or *"Let me check"* in any language. `communication_policy.py:108`
forbids offering *"to check, confirm, look up, or verify it later"*. The
greeting stage rule at `prompts.py:157` requires the opposite: *"Where you
cannot answer something they asked, say who will find out and that you will come
back with it."* And the owner approved exactly that sentence on dialog 819 —
*"I'll confirm assembly with our team and come back to you."* The difference the
prompt is trying to express is whether a tool exists for the question. A
prohibition cannot express it; a permission with a condition can, and that is
the whole of it.

**Negative instruction is the weaker instrument on this model.** Owner
observation, and consistent with what we measured: the used-furniture
prohibition needed a measured failure before the bounded grounding rule was
admitted (`tj-rt7w.1`), and it took three authorised Luna calls to establish
that the prompt alone did not hold it.

## 2. The mechanism exists and is half-built

`src/llm/communication_policy.py` already carries `COMMERCIAL_CAPABILITIES`:
**eight entries** in four modes — `direct`, `conditional`, `tool_required`,
`manager_required` — rendered into the prompt as
`[AUTHORIZED COMMERCIAL CAPABILITIES]`.

This is the allowlist. It is under-populated against what sellers actually
promise, and every one of its instruction strings is still phrased as a
prohibition:

```
discount [manager_required]: Never approve or promise a discount without
                            explicit support.
showroom_visit [direct]:     ...do not guarantee a particular product,
                            appointment, or test setup...
project_samples [conditional]: ...preserve that condition and do not promise a
                            specific material sample.
```

So the work is not a new architecture. It is: fill the registry to cover what a
seller actually says, turn every entry the right way round, and delete the
scattered prohibitions that the registry then subsumes.

## 3. What sellers actually promise, counted

From the protected corpus, seller messages only. No text left the protected
store; the numbers below are counts and the type names are ours.

```
10 468  seller messages
 4 771  are one of 51 template lines (46%) — the WhatsApp autoresponder
 5 697  actually typed by a human
 1 391  contain a first-person forward-looking lead
   180  of those are "let me know", which is a request, not a promise
 1 211  real commitments
```

Collapsed to verb-and-object, sixteen types cover two thirds of them:

| count | promise type | | count | promise type |
|---:|---|---|---:|---|
| 219 | prepare or send a quotation | | 58 | deliver, or give a delivery date |
| 189 | help find or assist | | 56 | ask the team or supplier |
| 127 | send the catalogue or options | | 33 | come back with an answer |
| 120 | check or confirm a price | | 28 | send a sample or photo |
| 117 | confirm the selection or order | | 21 | invoice or payment terms |
| 82 | check stock | | 20 | showroom visit or site visit |
| 61 | make to order | | 13 | phone the customer |
| | | | 8 | assemble or install |
| | | | 8 | warranty or after-sales |

The residual third is mostly positioning claims rather than promises — *"we are
wholesalers of…"*, *"we specialise in…"* — plus two types worth adding: **offer
an alternative** when the exact item is unavailable, and **source an item that
is not in the catalogue**.

Two things follow. The list is short enough to write down, which is what makes
the approach possible at all. And the largest single promise a human seller
makes — the quotation — is one Noor already has a tool for, so most of the
volume is already inside the mechanism rather than outside it.

## 4. The seven rules

These bind the work the way the six rules bound `tj-rt7w`.

**P1. One list.** `COMMERCIAL_CAPABILITIES` is the only place in the codebase
that says what Noor may promise. A promise rule that lives anywhere else is a
defect, not a special case.

**P2. Every entry is a permission with its condition.** No entry is phrased as a
prohibition. `discount` stops being *"never approve or promise a discount
without explicit support"* and becomes *"you may name a discount that segment
policy or a manager has already approved, and you say which."* The condition is
not softened; it moves from being the sentence to being the qualifier.

**P3. Absence is the prohibition.** Nothing Treejar does not do gets a block of
its own. It is simply not on the list. The redirect is itself a listed
permission: what Noor **does** say when asked for something absent.

**P4. `tool_required` means this turn.** A promise in that mode is legal only in
a reply where its tool returned success in the same run. This is already the
rule for prices and it is already enforced for numbers; it extends unchanged.

**P5. Prompt first, then measure.** Inherited R5. The registry rewrite ships and
is measured before any deterministic check is written. A check with no measured
leak behind it is a guard nobody asked for.

**P6. A refactor and a behaviour change never ride in the same round.**
Inherited R6. The registry rewrite is a behaviour change and travels alone.

**P8. Doubt is resolved by a second model, not by deleting a sentence.** Owner
decision, 2026-08-11. When a check fires, it has said *something is wrong here*
— it has not said what the reply should be. A deterministic detector may
therefore trigger a review; it may not decide the customer's text. The review
and the corrected wording come from a model, and — because the point is a second
opinion rather than a second try — from the other vendor. Nothing is deleted
automatically.

This is the general form of `tj-swgu.2`, which already turned the verified-catalog
check from a substitution into a repair directive and is closed. What is new is
that it applies to every check that today edits the customer's text, and that the
rewrite comes from a different model rather than the same one.

It also supplies what `tj-rt7w.14` records as missing: the R2 bound is
letters-or-digits-in, letters-or-digits-out and cannot tell that four sentences
became one word. A second reader can.

**P7. The corpus supplies candidates, the owner supplies permission.** The
counts above say what humans *said*. They do not say what Treejar can honour:
86% of outcomes are outside the channel, so we cannot tell which of the 1211
promises were kept, and a seller may have over-promised too. Every entry is
ratified by the owner before it ships.

## 5. What changes, in order

**Step 1 — the list.** Extend `COMMERCIAL_CAPABILITIES` to cover the ratified
types, each with a mode and a source. Add one mode, `not_offered`, whose
instruction is the permitted redirect rather than a refusal.

**Step 2 — turn the entries round.** Rewrite all eight existing instructions and
write the new ones as permissions with conditions. `_format_capability_registry`
renders them; the header becomes what Noor may say, not what is authorised in
the abstract.

**Step 3 — delete what the registry now covers.** `CUSTOMER_OWNED_FURNITURE_POLICY`
goes, and with it the `LANGUAGE_DIRECTIVE` splice that carries it. The
`"I will check"` prohibition at `prompts.py:41` goes and is replaced by the
`tool_required` condition, which is what it was trying to say. The grounding
policy bullets that duplicate a registry entry go.

**Deleting the used-furniture block is safe, and it is not the test of
anything.** `tj-rt7w.1` shipped two layers: the prompt block, and a bounded
deterministic backstop in `grounding_output.py` — a pattern and a repair that
the comment there records as earned by a measured failure. The guarantee lives
in the backstop and does not read the prompt. So the block can go and dialog 789
stays fixed either way, which means it proves nothing about the permission list.

One existing test does break, and it is a text assertion rather than a
behaviour one:
`test_llm_prompts.py::test_customer_owned_furniture_prompt_covers_the_service_promise_family`
asserts that the block is present in the built prompt. It is replaced in the
same child by a test asserting the same coverage against the `not_offered`
entry. That is a declared removal, not a test edited to accommodate a move, and
the distinction has to be stated in the child's artifact. Every test in
`test_llm_grounding_output.py` must pass untouched; those are the ones that hold
the behaviour.

**Step 4 — measure.** One round on the frozen twenty, seed `20260810`, judged by
the orchestrator, paired against **2026-08-11**, which is the first baseline on
this judge. Two directions are measured, not one:

- fewer unsupported promises. **Dialog 28 is the honest test, not 789.** There
  is no deterministic backstop for a recruitment routing promise, so it is the
  case where the permission list is the only thing standing between the model
  and an invented commitment. 789 is protected by its guard whatever the prompt
  says. Critical failures must not rise;
- **more supported ones**: rules 14 and 15 — confirm the next step, agree the
  next contact — currently score **zero**, and a permission list is the thing
  that could move them.

**Step 5 — the deterministic half, only if step 4 shows a leak.** Extract
forward-looking first-person commitments from the reply, map each to a registry
entry, and treat a commitment with no entry, or a `tool_required` entry with no
successful call this turn, as a violation of the same kind as an ungrounded
number. It belongs beside `find_ungrounded_numbers` in the grounding output, not
in a new guard, and it owes its own measured round.

Under P8 that detector is a **trigger**, not a repair: it names the doubt and the
second model writes the corrected reply. The repair architecture that makes this
possible is its own epic, `tj-n7p4`, and this step depends on it rather than
inventing a second copy.

## 6. What this must not become

**A bot that promises nothing.** The client's own rubric charges for the next
step (rule 14) and the next contact (rule 15), and Noor scores zero on both
today. A list short enough to be safe and too short to sell trades a safety
defect for a commercial one, and the rubric will show it. If step 4 moves
critical failures to zero and leaves 14 and 15 at zero, the list is too tight
and that is a finding, not a success.

**A second place where promises are decided.** P1 exists because the prompt
already has promise rules in four files. Adding a ninth block beside the
registry would reproduce the defect this spec is about.

**A claim that the corpus authorises anything.** P7. The counts are evidence of
practice.

## 7. What this spec does not cover

- The three `tj-vz7o.12` defects that reproduced on 2026-08-11. Different cause,
  different fix, and none of them is a promise.
- Retiring the deterministic routes. Still out, still for the reason recorded in
  the previous spec: nobody has measured what breaks without them.
- The rubric and the applicability map. Frozen.
