"""What every deterministic customer-visible route is, and when it was checked.

Nine of these accumulated one at a time between 2026-05-15 and 2026-07-30. Each
fixed a real complaint and no commit body recorded why; the reasoning survived
only in test names. When the main model changed on 2026-08-05, none of them was
re-tested against it, and the 2026-08-07 acceptance found that two were
treating the wrong cause and one had lost its premise entirely. Nothing made
that visible until a whole run was scored turn by turn.

So a route now has to say what it does and when it was last checked against the
model in production. ``rechecked_on`` is ``None`` for the ones whose history is
genuinely unknown -- that gap is the finding, and inventing dates for it would
bury the thing this file exists to show. New routes do not get that option: see
``tests/test_deterministic_routes.py``.

``carries`` is the second record, added 2026-08-09 for ``tj-ja1v``. The
2026-08-07 acceptance separated on one variable: scenarios where every
substantive turn was model-written averaged 24.8, and scenarios where a route
replaced at least one turn averaged 13.3. Reading those turns says why. The
routes were factually safe and told the customer nothing they did not already
know: no acknowledgement, no verified fact, no next step in their own terms.

The contract is therefore that a route owning a customer-visible turn either
carries a verified fact of its own, or asks for the one thing it genuinely
cannot proceed without, or escalates. ``asks_only`` is the honest label for the
third case and for the remaining debt: ``ROUTES_THAT_ONLY_ASK`` is frozen, so a
new route cannot quietly join it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Prose = Literal["deterministic", "model_written"]
# What the route's own reply gives the customer.
#
#   verified_fact -- a figure, a row or a link read this turn, plus a next step
#   asks_only     -- a question and nothing else, because there is nothing else
#   escalates     -- hands the question to a person who has the authority
#   acknowledges  -- confirms what the customer just said and does not add to it
Carries = Literal["verified_fact", "asks_only", "escalates", "acknowledges"]


@dataclass(frozen=True, slots=True)
class DeterministicRoute:
    """One route that can own a customer-visible turn without the model."""

    does: str
    carries: Carries = "asks_only"
    carries_write: bool = False
    prose: Prose = "deterministic"
    rechecked_against_model: str | None = None
    rechecked_on: str | None = None


_LUNA = "openai/gpt-5.6-luna"
_QUOTATION_COMPLETION_DAY = "2026-09-24"


DETERMINISTIC_CUSTOMER_ROUTES: dict[str, DeterministicRoute] = {
    "quotation-completion": DeterministicRoute(
        does=(
            "Sends the verified quotation tool result when the post-quotation "
            "model rewrite fails."
        ),
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_QUOTATION_COMPLETION_DAY,
    ),
}


# Snapshot of the routes whose history was already unknown when this file was
# written. It does not grow: a route added after 2026-08-07 must carry a date.
ROUTES_NEVER_RECHECKED_AT_INTRODUCTION = frozenset(
    label
    for label, route in DETERMINISTIC_CUSTOMER_ROUTES.items()
    if route.rechecked_on is None
)


# Frozen debt list for routes that only ask a question without verified facts.
ROUTES_THAT_ONLY_ASK: frozenset[str] = frozenset()
