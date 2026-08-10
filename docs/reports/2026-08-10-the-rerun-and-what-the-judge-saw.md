# The rerun: the two defects are gone, the score did not move, and I found a third

Date: 2026-08-10
Beads: `tj-vz7o.10`, `tj-vz7o.11`, `tj-vz7o.12`
Build measured: `b244711`
Judge: Claude, reading blind. `z-ai/glm-5.2` scored the same texts as a second
reader, not as the arbiter. Owner instruction, 2026-08-10.

## What was authorised and what it cost

Exactly 20 `openai/gpt-5.6-luna` calls and 20 `z-ai/glm-5.2` calls, on the
frozen seed-`20260810` set of 20 real customer openings. No live traffic, no
deploy, no production mutation, no message to a real person, nothing pushed.

Actual cost **$0.0046 + $0.1753 = $0.180**, against a preflight worst case of
$0.73 and a hard cap of $1.00 per model.

## The result against the contract frozen before the run

| | frozen requirement | observed |
|---|---|---|
| Luna responses | 20/20 | **20/20** |
| GLM evaluations | 20/20 | **20/20** |
| Correct language | 20/20 | **20/20** |
| Critical failures | **zero** | **0**, down from 2 |
| Score | paired delta, no absolute level | see below |

Time to first reply: median **1.906 s**, 95% CI 1.826–2.177, over 20/20.

**Both defects from the previous round are gone.** Opening 1022 — the bare
"Good Afternoon" that came back with an invented starting price — now greets and
asks what the customer is furnishing, with no figure at all. Opening 819 — the
assembly question that was acknowledged and dropped — now reads "I'll confirm
assembly with our team and come back to you."

## The score did not move, and that is the honest answer

Paired over the same twenty openings and the same judge, build `8e50dea` against
build `b244711`:

- weighted **+0.82 ± 1.45**
- `raw_total` **+0.20 ± 0.66**

Both deltas sit inside their own uncertainty. By this project's standing rule —
no movement smaller than the instrument's own uncertainty is evidence — **the
score did not change.**

That is the expected result and not a disappointment. The work fixed two
defects and removed an instruction that invited a third; none of it was aimed at
the rubric. What changed is the thing the rubric does not score: **2 critical
failures became 0**.

## My own reading, and where it disagrees with GLM

I scored all fifteen criteria on every opening, no applicability map, on the
text a customer would actually receive.

| | mine | GLM |
|---|---:|---:|
| `raw_total` mean | **13.30/30** | 11.20/30 |
| ceiling 9.6 band, 11 openings | 87% of ceiling | 86% |
| ceiling 30.0 band, 9 openings | 64% of ceiling | 60% |

Mean absolute disagreement **2.05 ± 0.78** raw points — and it is systematic,
not noise: **I scored at or above GLM on all twenty**, never below. That is the
same phenomenon this project measured at 3.8 points between two other judges on
identical text, and it is the exact reason no figure here may be set beside the
client's 6.05.

The two judges agree far more closely on **share of ceiling** than on the raw
total — 87/86 and 64/60. That is worth keeping: expressed against what an
opening could attain, the measurement survives a change of judge much better
than the level does.

## What I will not certify

The round passes the contract that was frozen before it ran. It does **not**
make the opening client-ready, and as judge I am not saying it does. Reading the
twenty replies turned up four things the deterministic detector cannot see, all
recorded in `tj-vz7o.12`:

- **Opening 789.** Asked "do you buy office table i have", Noor replied "Yes,
  Treejar can help you sell or assess an office table you already have." We have
  no evidence Treejar buys used furniture. This is an unverified service
  commitment — the same class as the "UAE delivery with installation" clause the
  grounding policy already removes.
- **Openings 436 and 1067.** The customer named a category, or asked outright
  for details; three catalog rows were available; the reply quoted no product
  and no price. Our own greeting rule says to quote when they name a category.
- **Openings 28 and 875.** The customer signs their name, Noor uses it —
  "Dickson," and "Thanks, Binu" — and then asks "And how should I address you?"
  The harness always passes `customer_name=None`, so this may be a harness
  artefact rather than a product defect. It needs checking against the real
  fact-extraction path before anyone writes a guard for it.
- **Opening 420.** "SIZE ?" carried no referent and was answered about "this
  cabinet", an item the customer never named.

## The third defect, found by reading rather than by measuring

Four of the twenty replies — 293, 421, 867, 1217 — reached the customer as the
identity line and the name question and nothing else. The model had written a
capability sentence and a qualifying question for each of them, and a guard
deleted the lot.

The cause is one character. `_strip_legacy_identity` matched only the straight
apostrophe in "I'm"; the model writes the typographic one. Its own introduction
survived the strip, `_has_identity` then found "Noor" and "Treejar" still in the
body, and `body = ""` threw away the entire answer.

Every one of the four is a bare greeting, and bare greetings are **34% of real
traffic** — the most common opening we have. The same defect is in the previous
round's output, so it is not a regression; it is something nobody had read
closely enough to notice. Three of the last four rounds' most useful findings
came from reading transcripts by eye, and this is the fourth.

Fixed in `tj-vz7o.11` under five tests: the pattern now accepts both
apostrophes, matched rather than rewritten so the customer still reads the
model's own punctuation, and a duplicate introduction now costs one sentence
instead of the whole reply.

**This fix needed no further paid call, and that is a property of the fix rather
than a shortcut.** A post-processing guard cannot change what the model wrote,
so re-applying the corrected chain to the twenty stored raw outputs gives the
exact result, not an approximation. Verified: exactly those four replies change
and no other. My scores above are on the corrected text.

## Denominators

20 openings drawn with seed 20260810 from the 629 evaluated natural-text
customer openings in the 1400-dialogue corpus, stratified into four length
bands. Not a sample of "1400 real openings": 525 of the population are one
identical lead template and 146 are an attachment only, which the export did not
carry. Eleven of the twenty have a deterministic ceiling of 9.6/30 and nine can
reach 30.0, so no level is quoted across the two.

Nothing here supports a claim about conversion, revenue, deal size or close
rate, and nothing here is comparable with the client's 6.05: a different judge
read a different genre.
