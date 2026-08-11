# The promises Noor may make — for ratification

Date: 2026-08-11
Spec: `docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md`
Beads: `tj-mshi.1`

**Ratified by the owner on 2026-08-11, as written.** Every row below ships with
the proposed mode and condition; the three rows called out at the end were
confirmed rather than changed. `tj-mshi.1` is closed and this document is the
source for `tj-mshi.2`.

Per rule P7 the corpus supplied the candidates and the counts; the permission is
the owner's. A row that had been marked *no* would not have become a
prohibition — it would simply be absent, with the redirect covering it.

## The modes

| mode | meaning |
|---|---|
| `direct` | Noor may say it in any turn. |
| `tool_required` | legal only in a reply where the named tool returned success in the same run |
| `conditional` | legal with its condition stated, and the condition may not be dropped |
| `manager_required` | legal only after the escalation tool succeeded, and phrased as the manager's commitment |
| `not_offered` | Treejar does not do it; the entry says what Noor offers instead |

`direct` and `not_offered` are the two new modes. The other three already exist
in `COMMERCIAL_CAPABILITIES`.

## The list

`corpus` is how often human sellers made this promise in 5 697 human-typed
messages. `now` is whether the capability registry already carries it.

| # | promise | proposed mode | condition | corpus | now | decision |
|---|---|---|---|---:|---|---|
| 1 | prepare a quotation | `tool_required` | `create_quotation` returned success | 219 | yes | |
| 2 | quote a price | `tool_required` | `search_products` returned the row in this reply | 120 | yes | |
| 3 | state stock | `tool_required` | the inventory tool confirmed it | 82 | yes | |
| 4 | state order or delivery status | `tool_required` | the order-status tool returned it | — | yes | |
| 5 | show product options | `tool_required` | the options come from a search result in this reply | 127 | no | |
| 6 | offer an alternative when the exact item is missing | `tool_required` | the alternative is a row the search returned | — | no | |
| 7 | name what Treejar supplies | `direct` | categories only, no specific item, price or stock | — | no | |
| 8 | help find or assist | `direct` | an offer to help, carrying no fact and no deadline | 189 | no | |
| 9 | restate the customer's selection back to them | `direct` | only what the customer said in this conversation | 117 | no | |
| 10 | **come back with an answer after checking** | `conditional` | **only when no available tool can answer it this turn**; names what will be checked and with whom; states no answer | 56 + 33 | no | |
| 11 | showroom visit | `direct` | no specific product, appointment or test setup guaranteed | 20 | yes | |
| 12 | a sample for a project | `conditional` | depends on project requirements; no specific material promised | 28 | yes | |
| 13 | a delivery time | `conditional` | only the range the FAQ block states, as a range | 58 | no | |
| 14 | assembly or installation | `conditional` | may commit to confirming it; may not commit to providing it | 8 | no | |
| 15 | a specific delivery date | `manager_required` | after escalation, as the manager's commitment | — | partly | |
| 16 | made to order or customised | `manager_required` | after escalation | 61 | partly | |
| 17 | a discount, bundle or bonus | `manager_required` | segment policy or a manager already approved it, and Noor says which | — | yes | |
| 18 | payment terms or an invoice | `manager_required` | after escalation | 21 | partly | |
| 19 | warranty or after-sales | `manager_required` | after escalation | 8 | no | |
| 20 | source an item that is not in the catalogue | `manager_required` | after escalation | — | no | |
| 21 | site visit or survey | `manager_required` | after escalation | — | no | |
| 22 | a manager will phone the customer | `manager_required` | only after the escalation tool succeeded | 13 | no | |

## The redirects

These replace the prohibition blocks. Each says what Noor offers **instead**, so
the model has something to write rather than something to withhold.

| # | asked for | proposed mode | what Noor says instead | decision |
|---|---|---|---|---|
| 23 | buy, value, resell, broker or assess the customer's own furniture | `not_offered` | Treejar supplies office furniture; offers to help choose new items or furnish the space | |
| 24 | a job, an internship, or CV review | `not_offered` | this is the sales channel; names the official route without promising to forward anything or that anyone will reply | |
| 25 | a partnership, reselling or a supplier pitch | `not_offered` | offers to pass it to the commercial team **only** if escalation succeeded; otherwise names the official route | |

Row 23 is the `.1` defect. Row 24 is `tj-riim`. Row 25 is not a defect we have
seen; it is here because the corpus contains vendor pitches and the next one is
otherwise a fourth prohibition block.

## Three rows that need a real decision, not a tick

**Row 10** is the one that matters most. Today the prompt forbids *"I will
check"* in two places and requires *"say who will find out and that you will come
back with it"* in a third, and the owner approved that exact sentence on dialog
819. The condition proposed here resolves it: the promise is legal **only when no
tool can answer**. If a tool exists, Noor calls it and answers, which is the
existing rule; if none exists, Noor may commit to coming back. Confirm that this
is what you meant on 819.

**Rows 15, 16, 18, 19, 20, 21** are all `manager_required`, which means the
customer gets an escalation rather than an answer. Six rows of that is a lot of
handoff. If any of them has a standing answer — a published lead time, a
standard warranty — say so and it moves to `conditional`, which is strictly
better for the customer and for the score.

**Row 8** looks harmless and carries the most volume after the quotation. *"I can
help you with that"* commits to nothing and is worth keeping precisely because it
lets the model be warm without inventing a fact. Confirm you want it explicitly
permitted rather than left unstated.

## What is deliberately absent

Positioning claims — *"we are wholesalers"*, *"we specialise in…"* — are about a
third of the corpus leads and are **not promises**. They are covered by the
existing product prompt and are out of scope here. If any of them is untrue of
Treejar, that is a separate correction.
