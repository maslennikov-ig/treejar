# Less caution, more selling — and two criteria that charged for the impossible

Owner instruction, 2026-08-08: *"мы построили лишнюю осторожность. Нужно снизить
осторожность. Её главная задача всё-таки продавать."* This is what changed, what
it is worth, and what cannot be measured until a deploy.

No live traffic, no paid judge call, no production mutation. Everything below is
either a code change or arithmetic over transcripts already stored.

## Three kinds of caution, and only one of them was a defect

**Grounding stays.** Noor still states no price, stock or specification absent
from a verified catalog row. Naming a price the catalog does not carry is not a
bolder salesperson, it is an invoice somebody has to honour. The owner already
loosened this once, on 2026-08-06 — the contract blocks only what a retrieved
row *refutes* — and no further.

**Discounts stay the owner's.** Rule 11 asked for an incentive; three separate
places in the runtime forbid one. Resolved below without committing money.

**Obedience generalised past the request was the defect.** S08 is the clean
case, because it scored **+0.0** between the two stored builds and reads
identically in both: a standing defect, not sampling noise. The customer opens
with "do not create a quotation". Three of the four assistant turns that follow
are a bulleted restatement of the customer's own requirement — no product, no
price, no question. The closing turn then proposes, as the customer's next step,
"verify whether three units fit within AED 6,000" — an action Noor holds the
tools to perform. A ban on a quotation had become a ban on selling.

## What changed

Four changes, two on the measuring side and two on the dialogue side.

**Measuring side — rule 3 stands down when the customer signs their opening.**
`_build_applicability_assessment` charged "asked how to address the customer" on
every conversation with an assistant turn. Where the customer opens with "My
name is Leila", there is nothing to ask, and the rule marked a correct reply
down for skipping a rude question. Now the rule stands down only when the name
appears *before the assistant's first turn*; a name volunteered later does not
excuse an opening that never asked.

**Measuring side — rule 11 applies only to a comprehensive order.** The source
guideline offers a bundle "при комплексном заказе", not on every catalog turn.
The rule now needs the catalog signal *and* a request spanning two or more
product families, read from the runtime's own `catalog_planning_v1`. It applies
in three of the ten stored scenarios instead of ten, and where it applies it
stays charged, because those really are the fit-outs a bundle belongs to.

**Dialogue side — a directive on every turn that forbids the empty reply.**
`substantive_reply_directive` carries no trigger by design. It separates the
stated restriction from everything the customer did not rule out, forbids a
reply whose whole content is a restatement or a statement of intent, and tells
Noor to perform with her tools any next step she was about to hand back. It
fires on the narrowed turns the selling directives stand down on — a customer
who wants one exact price still deserves that price rather than a summary of
their own message.

**Dialogue side — the consultative opening now widens the sale.** On the owner's
decision that Noor may suggest a complementary catalog item, rules 9 and 10
joined the directive that already carried 6, 7 and 13: find out what the
furniture is *for* and recommend against that job rather than against the words
of the request; name the one missing piece, looked up with `search_products`
first; one piece, not a list. Rule 11 arrives in its honest form — where the
project spans several kinds of furniture, quote the pieces as one package at
their combined verified total. **A package, never a discount.** Merged into the
existing directive rather than added beside it, so the "at most one question"
bound stays shared and the reply does not become an interrogation.

A fifth, smaller change: `defers_the_purchase` detects a customer who is not
buying today, and `next_contact_directive` answers rule 15 by proposing one
specific time and asking them to confirm it — while claiming nothing has been
scheduled unless a tool call did it. A date alone does not count: "we need 20
chairs next week" is a deadline, not a deferral. That distinction came from an
existing test failing, which is the test earning its keep.

## What the measuring-side corrections are worth

The readers' judgements are untouched: their per-criterion scores are kept
verbatim, only the applicability map changes, and the arithmetic goes back
through the product's own `calculate_weighted_score`.

| build | before | after | delta |
|---|---|---|---|
| `6a14f2f` | 12.59 | **13.57** | +0.98 |
| `5656c82` | 12.54 | **13.43** | +0.89 |

Per scenario, the whole movement sits in the five conversations where one of the
two rules was charged wrongly:

```
S03  12.05 -> 15.10   +3.05   name given in the opening; single-family request
S04  13.80 -> 17.00   +3.20   same
S08   7.85 ->  9.50   +1.65   same
S07  14.50 -> 15.50   +1.00   single-family request
S06/S09/S10           +0.00   rule 11 off, rule 3 correctly charged
S01/S02/S05           +0.00   both rules correctly charged
```

**The honest baseline is now about 13.4 of 30, and the gap to 24.0 is 10.6.**
The build did not improve; the instrument stopped charging for two things the
runtime could not do. That is worth saying plainly, because it is the third
correction to this number in two days and none of them was a product change.

## What cannot be measured yet, and why

The acceptance harness posts to the deployed webhook at `noor.starec.ai`. It
measures whatever is running on the server, not the working tree. The two
dialogue-side changes are therefore **written and tested but unmeasured**, and
they join `consultative_opening_directive` — in the repository since `14881b5`
and never yet in a scored build. Measuring any of them needs a deploy, which is
a separate authority nobody has granted.

And when that run happens it has to be repeated. The owner declined to pin
`PATH_CORE_CHAT` to temperature 0, on the ground that a bot which always writes
the same sentence stops being a salesperson: varied phrasing is part of the job,
and each customer sees only one conversation. The decision is accepted, and its
price is that a single run per scenario proves nothing. Build `8b8635f` ran S05
three times: the deterministic template turn is byte-identical in all three,
every model-written turn differs in structure and in the products it
recommends, and turn 4 returned the error fallback in two runs of three. So the
next comparison is k runs per scenario against k runs per scenario, with the
interval those repeats justify — `tj-2m5m.7`.

That also retires a claim from yesterday's report. The S07 regression there
(−3.3) was measured from one generation each side. It stands as an observation
and falls as a conclusion; `tj-2m5m.6` is downgraded to P2 and blocked behind
the repeat protocol. S08's +0.0 is unaffected, and is why the standing defect
above could be worked on at all.

## Verification

`uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`,
`uv run mypy src/` (167 sources), `uv run pytest tests/` — **3336 passed, 19
skipped**. Twelve new tests: five on the corrected applicability, seven on the
new directives and their stand-downs.
