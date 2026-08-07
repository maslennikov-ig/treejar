# The slot rewrite, and what the score can and cannot tell us

Second half of 2026-08-07, after `tj-swgu.8`. Two results: the model-written
rewrite now works, and the instrument used to grade it is far noisier than
anyone here has been treating it as.

## The rewrite works

The problem it started from: the wrap fired on every action route and the guard
refused nearly every result, because the model would not carry a unit price, a
stock figure or a quotation number through. The customer got the template
anyway.

Research first, which is what changed the design. Asking a model to reproduce
figures and checking them afterwards is a documented dead end; the answer is
not to let it handle the figures at all. ASPIRO (Vejvar & Fujimoto, EMNLP
Findings 2023) prompts for entity-agnostic templates "rather than relying on
LLMs to faithfully copy the given example entities" and reports a 66% error
reduction. Practitioners writing financial commentary and citation-heavy text
independently arrive at the same method: replace each protected value with a
token, rewrite only the prose around it, count the tokens, restore by
substitution.

So the route's sentence is now masked before the model sees it:

```
1. Operative Office Chair CH {{f1}} NEW black
   Quantity: {{f2}}
   Unit price: {{f4}} AED
```

The model writes around the tokens and never touches a digit; code puts the
values back. A wrong figure is no longer something to detect — it cannot be
produced.

Two experiments got it working, and both are worth recording because neither
was guessable from the code:

- **Given only the rewrite directive, the model carries every token through and
  passes.** Given the same directive underneath the frozen product system
  prompt, it ignores the tokens entirely. The rewrite is a text transformation,
  not a sales turn, and it now runs on its own agent with no tools, no catalog
  and no persona. That single change is what made the mechanism work.
- Giving that agent its own prompt took away its conversation, and the first
  reply was correct, complete and addressed to nobody. It now gets the
  customer's name and the message it is answering, and nothing else.

The structural result is unambiguous, because it is counted rather than judged:

| | deterministic turns | scenarios fully model-written |
|---|---|---|
| morning, `c977b07` | 15 of 29 | 2 of 10 |
| `6a14f2f` | 13 of 29 | 3 of 10 |
| `5656c82`, slots on | **9 of 29** | 3 of 10 |

The nine that remain are seven `name-gate` turns, which are out of scope by
design, one catalog fallback and one detail request.

## The score cannot see it

Three acceptance runs on materially different builds:

| | mean comparable |
|---|---|
| `c977b07` | 18.0 |
| `6a14f2f` | 18.5 |
| `5656c82` | 18.2 |

That looks like a mechanism that changes nothing. It is not, and the reason is
the instrument.

**The same S03 transcript, scored five times, with no live traffic and not one
byte of difference between the runs:**

```
15.2   16.2   21.5   21.6   23.9
```

Standard deviation 3.8, range 8.7, on identical text. Which means:

- a **single scenario's** score carries roughly ±7 at 95% confidence;
- the **ten-scenario mean** carries roughly **±2.3**.

18.0, 18.5 and 18.2 are therefore one number, not three. And the per-scenario
deltas that the earlier reports read as evidence about code are mostly not:
S03 went 25.4 → 28.9 → 17.6 across three runs on a path nobody touched, and S07
went 24.0 → 23.5 → 15.2 the same way. I attributed some of those to the change
in the previous report. That was wrong, and this measurement is the correction.

The morning report's central claim — model-written scenarios averaging 22.8
against 13.3 for template-touched ones — is a 9.5-point gap between two groups
of five, so it is probably real. It is less certain than it was presented as.

## What follows

1. **Score each conversation several times and report the spread.** Scoring is
   offline against a stored transcript and costs no live traffic, so this is
   cheap. Filed as `tj-swgu.9` at P0, because every other number in this stream
   depends on it.
2. Until that exists, the honest gate is the structural one: turn provenance is
   deterministic, and it moved from 15 deterministic turns to 9.
3. `tj-swgu`'s acceptance — a mean of 24.0 — is a 5.8-point move from here,
   which is detectable above the noise. But it has to be measured with repeats,
   or the run that appears to pass will be as trustworthy as the three above.

## Test data

Four sale orders voided with readback across the day's runs plus `Fr3716` from
this one, the test contact deactivated, the CRM deal retained for audit. S09
and S10 were each run on a freshly reset conversation.
