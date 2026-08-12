# One owner for what the reply says

Spec date: 2026-08-12
Base: `main` at `cdd909f`
Author: root orchestrator
Status: ready for implementation

## Why this exists

Three of the twenty replies in the `tj-vhto` round scored 8.9, 8.9 and 12.2
against a set mean of 15.3 — the three worst in the round. The blind readings
recorded their faults as "the self-introduction is written twice", "used the
name the customer had just given, then asked for it again", and "closes with a
farewell and then asks for a name already signed".

We spent three days looking for the cause in the model, the prompt and the
vendor. It is in our own guard layer. In every one of those cases the model
wrote a reasonable reply and **we added the duplicate ourselves**.

Research (2026-08-12, four parallel streams) settles what is standard practice
and what is not:

- "Never ask for something already known" is solved, structurally and
  unanimously, by Rasa CALM (`collect` is skipped when the slot is filled),
  Dialogflow CX (the prompt is queued only if required parameters remain), and
  Amazon Lex V2 ("you can loop back to re-elicit a slot provided that you set
  that slot value to null beforehand"). None of them uses a prompt instruction.
  Rasa names the prompt-based version "prompt and pray".
- **No framework guarantees anything about a reply contradicting itself**,
  because in all of them the reply text is templated. Our class of bug exists
  only where the model writes the text. The closest published analogue to our
  architecture is Chirpy Cardinal (Stanford, Alexa Prize): generate candidates,
  filter deterministically, and record "we asked X" into state at send time
  rather than reading it back out of the text later.
- Of our five grounding checks, exactly one (a service we do not offer) has an
  industrial equivalent. Detecting an unkept promise is shipped by nobody:
  not one of Guardrails AI's 65 validators, no NeMo rail, no Bedrock or Azure
  policy. We are not reinventing a framework.
- **The best published precedent for our shape is Google's Meena**
  (arXiv:2001.09977), verified in the full text: "We wrote a rule that detects
  if any two turns contain long common sub-sequences. We automatically remove
  candidates that are detected as repetition." About a third of interactive
  conversations carried cross-turn repetition before it; interactive SSA went
  72% (base) → 74% (tuned decoding) → 79% (full, with the filter). Google's own
  answer to a generative chatbot repeating itself was a deterministic rule
  filtering candidates — not a prompt, and not a model judging a model.

## What is actually broken

### 1. The identity strippers do not recognise the company alone

`src/llm/opening_guard.py` already implements single ownership: it strips the
model's own introduction, then prepends ours. The discipline is right. The
recognition is too narrow:

- `_strip_legacy_identity` matches only "I'm/I am (Siyad|Noor) from Treejar" at
  the very start of the text.
- `_drop_identity_sentences` runs only when `_has_identity` is true, and that
  requires **both** `noor` and `treejar`.
- `_strip_own_capability` matches our capability sentence as an exact string.

The model routinely names the company without the persona — "Thanks for
contacting Treejar", "Treejar can supply…" — and not at the start. Nothing
strips it, ours is prepended, and the company is introduced twice.

Measured on the twenty stored replies of `tj-vhto`: **5 of 20** have the model
naming the company without the persona. Dialogs 28, 436, 789, 875, 1291. The
guard adds 124–170 characters to each.

### 2. The name question is appended from state that does not know the name yet

`apply_opening_guard` appends `_EN_NAME_QUESTION` unless `customer_name` is set
or the model already asks. `Turn.known_customer_name()` reads
`name_gate_resume_customer_name` or `conv.customer_name` — both persisted
state. A customer who signs their name **in the first message** has not been
extracted yet at render time: capture happens later in the turn
(`src/llm/message_processor.py` around the name-gate resume path).

So on a first turn the model can use the name from the message body while the
guard, reading empty state, appends "And how should I address you?". That is
dialog 875 exactly, and it is a production bug, not a harness artefact.

### 3. Two guards that would have caught some of this are switched off on first turns

`render_reply` gates `question_form`, `name_chase` and `company_question`
behind `if not state.is_first_turn`. Measured: `refuse_to_chase_the_name`
catches **none** of the three bad replies even when ungated and even with the
name known — it looks for the wrong thing. `collapse_question_form` **does**
remove the surplus name question from 1291 and 875, and its reduction proof
`only_asks_were_dropped` holds in both cases.

### 4. The repair judge is anchored to the candidate we hand it

Shipped yesterday in `tj-0h5d`: telling the judge the deterministic candidate
is safe to follow took delivery from 1 in 4 to 4 in 4 — and made it return that
candidate **verbatim in 7 of 7 deliveries**. Under the previous prompt the
judge independently caught a delivery city the reply had invented; that catch
is gone.

The literature explains it and points the same way three times: judges defer to
provided references (Yeadon et al., arXiv:2603.14732 — with deliberately false
reference solutions accuracy falls and "models defer to provided references");
authority, bandwagon and refinement-aware biases all push toward approval
(CALM, llm-judge-bias.github.io); and intrinsic self-correction reduces
accuracy rather than raising it (Huang et al., ICLR 2024, arXiv:2310.01798 —
GPT-4 GSM8K 95.5 → 91.5 → 89.0 across correction rounds).

No published study covers our exact failure mode. Our own 7-of-7 result is the
evidence, and it is consistent with all three lines.

## What we are going to do

### D1. One owner, recognised by the company name

Widen identity recognition so that a reply already naming Treejar is treated as
having introduced us, wherever in the text it appears, with or without the
persona.

- `_has_identity` becomes: the company is named. The persona alone is not an
  introduction and must not count.
- `_drop_identity_sentences` removes the sentence carrying the company mention,
  as it does today for the two-token case — one sentence, never the reply.
- The existing blast-radius protection stays: if removal would leave nothing
  meaningful, keep the original text and prepend nothing.

Acceptance: on the twenty stored `tj-vhto` replies, no shipped reply names
Treejar more times than the model's own raw text did, except where our prepended
opening is the only mention.

### D2. The name question reads the message, not only the stored state

The guard must not ask for a name the customer has just given.

- Extend the first-turn state passed to the guard with a name observed in the
  current inbound message, so the existing `_has_customer_name` check sees it.
- Where the name is captured later in the turn, that capture must be the same
  source of truth — one extraction, read twice, not two heuristics.

Acceptance: a first turn whose inbound message carries a signature does not
receive the name question. Dialog 875 replayed does not ask for the name.

### D3. An ask is recorded in state, not read back out of the text

Adopt the Chirpy discipline and the Lex idiom together.

- Add a slot recording that the customer name has been asked, set at the moment
  the reply is sent, not inferred afterwards from `previous_assistant_turns`.
- The only way to ask again is to clear the slot. Re-asking and the customer
  correcting a value become one mechanism rather than two rules that can
  disagree.
- Keep a named exception path for legitimate confirmation ("did I note your
  number correctly?"), as Rasa does with `ask_before_filling` — a blanket ban
  would block confirming an order.

Acceptance: the decision to ask for the name is taken from the slot alone. No
production path decides it by matching text.

### D4. The allowed asks are computed before generation

Today we decide after the model has written. Every structural system decides
before, so the wrong question is never generated.

- Derive the set of asks permitted this turn from state, once.
- Pass it into the generation prompt **and** enforce it in the guard layer from
  that same value. The prompt buys phrasing; the guard buys the guarantee; both
  read one source of truth instead of two sets of text heuristics.

Acceptance: one function owns the permitted-ask set, and both the prompt
assembly and the guard consume it. A test asserts they cannot diverge.

### D5. Enable the first-turn guards that earn it, and only those

- Run `question_form` on first turns. It removes a surplus name question in two
  of the three bad replies, and its reduction proof holds, so it is safe under
  the existing `REDUCING` contract.
- Do **not** enable `name_chase` on first turns on this evidence: measured, it
  changes nothing on any of the three. Leave it gated and record why.

Acceptance: the change to the first-turn gate is per guard with a stated
reason, not a blanket lifting of the condition.

### D6. Stop losing the reply, and stop anchoring the judge

Two coupled changes to the repair path. **This reverses part of `tj-0h5d` and
needs the owner's explicit nod before implementation.**

- When the judge is unavailable, answers `cannot_fix`, or its correction is
  rejected, fall back to the **deterministic repair** rather than the manager
  handoff notice. The deterministic repair cannot state anything ungrounded —
  that is what the guard guarantees — and it preserved 86% and 53% of the two
  flagged replies. The manager notice preserves nothing, and dialog 819 scored
  7.5 against a set mean of 15.3 because of it.
- Escalate to a manager only when the deterministic repair leaves no meaningful
  reply.
- With that fallback in place, remove the deterministic candidate from what the
  judge sees. Give it the original reply and the reason for the flag. Delivery
  no longer has to be bought with anchoring, because a judge that declines now
  costs us the free repair rather than the whole answer.

Acceptance: replaying dialogs 819 and 789, no outcome is a manager handoff, and
the judge's answers are no longer byte-identical to the deterministic repair in
every case. Measured live, both dialogs, at least four calls each.

## Beads

Epic `tj-q1a2`. Children `tj-q1a2.1` (D1) through `tj-q1a2.6` (D6). D3 depends
on D2, D4 on D3, D5 on D1. **`tj-q1a2.6` must not be started until the owner
has decided**, because it reverses part of `tj-0h5d` and touches the standing
rule that customer-facing content is not deleted automatically.

The discovery gap already had an issue: `tj-2m5m.4`, "Noor never asks why, and
never widens past the literal request", carrying the original judge quotes from
six scenarios. The 2026-08-12 research is in its notes.

## Out of scope, deliberately

**The discovery slot — tracked as `tj-2m5m.4`, not here.** The largest single score gap is that the bot asks
quantity and finish rather than what the customer is trying to do — the five
top-scoring replies all lose the same quarter. Research says it is real
(Need Elicitation is one of only two dimensions correlating with conversion
after Bonferroni correction, ρ=0.368, d=0.74, arXiv:2604.00022) and that a
prompt edit will not fix it (ReqElicitGym, arXiv:2602.18306: the best of seven
models extracts 32% of implicit requirements, and chain-of-thought moves
questions earlier without improving coverage). No open-source sales agent has a
required job slot gating product presentation. This needs its own measured
round and a structural gate, not a line in a prompt. Tracked separately.

## Constraints

- No paid call is required by D1–D5. D6 requires live replay to accept.
- The protected 60-output replay must stay byte-identical for D1–D5 except
  where a stored reply is one of the five that carries a duplicate
  introduction; every intended change must be shown one dialog at a time.
- The corpus stays outside the repository. Derived evidence carries
  `dialog_id`, integers and digests only.
- No push, deploy, production or staging mutation, model-configuration change,
  or real-user message.

## Evidence and its limits

Everything numeric here was measured on the twenty stored replies of the
`tj-vhto` round and the two flagged replies we hold. That is the entire
evidence base.

Three of four research streams delivered. The GitHub-archaeology stream was
lost to a reboot and did not return after a restart either, so the claim "open
source mostly does not fix this" rests on my own searching. What that searching
found: the symptom appears mostly as open, undiagnosed issues in small
projects, and the two merged fixes both apply the same mechanism — remove one
of two components that emit the greeting, rather than detect a duplicate.
`aeroventmarketing-ctrl/automated-quotation#282` ("the message owns the
greeting", merged 2026-08-09) and `bcgov/klamm#246` ("Fix salutation
duplication in email notifications", merged 2025-06-11, five notification
classes). Two instances is not a survey, but it is the same pattern twice and
it is the pattern this spec follows.

The Meena quotation and its SSA figures were verified by reading the paper, not
taken from a summary.
