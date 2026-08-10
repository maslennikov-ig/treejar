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
_TODAY = "2026-08-07"
# The routes reworked for tj-ja1v and the name gate. Same model, later day.
_ANCHOR_DAY = "2026-08-09"


DETERMINISTIC_CUSTOMER_ROUTES: dict[str, DeterministicRoute] = {
    # --- routes that carry an action -------------------------------------
    "selection-confirmation": DeterministicRoute(
        does=(
            "Resolves the customer's chosen items against the catalog, confirms "
            "live stock and price, and persists or suspends the quote selection."
        ),
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "exact-quote-deterministic": DeterministicRoute(
        does="Creates the quotation for an exact SKU and quantity request.",
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "quote-resume": DeterministicRoute(
        does="Creates the quotation once the missing customer details arrive.",
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "sales-order-quote": DeterministicRoute(
        does="Creates the quotation for a multi-item sales-order request.",
        carries="verified_fact",
        carries_write=True,
    ),
    "sales-order-quote-resume": DeterministicRoute(
        does="Creates the multi-item quotation after the follow-up resolves it.",
        carries="verified_fact",
        carries_write=True,
    ),
    "sales-opportunity": DeterministicRoute(
        does="Writes the CRM opportunity and reports what was recorded.",
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "sales-opportunity-unverified": DeterministicRoute(
        does=("Same as sales-opportunity when the CRM row could not be read back."),
        carries="verified_fact",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    # --- routes that ask for one missing thing ---------------------------
    # `name-gate` was retired on 2026-08-10. It was the whole first turn: the
    # model never ran, the customer's question was parked, and the only reply a
    # third of customers ever read was a request for their name. The name is now
    # a clause folded onto a real answer by `apply_opening_guard`, which is a
    # guard rather than a route because it never owns the turn.
    "name-capture": DeterministicRoute(
        does="Acknowledges the name just given.",
        carries="acknowledges",
    ),
    "detail-capture": DeterministicRoute(
        does="Acknowledges customer details captured mid-quote.",
        carries="acknowledges",
    ),
    "product-quantity-clarify": DeterministicRoute(
        does=(
            "States the price and live stock for the product the customer named, "
            "then asks the quantity the total depends on."
        ),
        # tj-ja1v, 2026-08-09. It used to ask the quantity and nothing else,
        # with the price and stock the customer had asked for one catalog row
        # away.
        carries="verified_fact",
        rechecked_against_model=_LUNA,
        rechecked_on=_ANCHOR_DAY,
    ),
    "exact-quote-clarify-item": DeterministicRoute(
        does="Asks which catalog item an unresolved quote line refers to.",
        # Nothing resolved, so there is genuinely nothing verified to add.
        carries="asks_only",
    ),
    "exact-quote-missing-details": DeterministicRoute(
        does=(
            "States what the quotation will cover and what it comes to, then asks "
            "for the customer details it cannot be issued without."
        ),
        carries="verified_fact",
        rechecked_against_model=_LUNA,
        rechecked_on=_ANCHOR_DAY,
    ),
    "quote-resume-missing-details": DeterministicRoute(
        does="Same, on the resume path.",
        carries="verified_fact",
        rechecked_against_model=_LUNA,
        rechecked_on=_ANCHOR_DAY,
    ),
    "quote-resume-missing-items": DeterministicRoute(
        does="Asks for the items behind a quote frame that has none.",
        carries="asks_only",
    ),
    "quote-frame-repair-missing-items": DeterministicRoute(
        does="Asks the customer to re-confirm items when the saved frame is unusable.",
        carries="asks_only",
    ),
    "sales-order-clarify": DeterministicRoute(
        does="Asks which items belong on an ambiguous multi-item order.",
        carries="asks_only",
    ),
    "quote-brief-confirm": DeterministicRoute(
        does="Reads an unlabeled detail brief back for confirmation.",
        # The customer's own words read back, which is an acknowledgement and
        # not a fact of ours.
        carries="acknowledges",
    ),
    "proposal-clarify": DeterministicRoute(
        does="Asks which items a proposal request should cover.",
        carries="asks_only",
    ),
    "quote-consent-required": DeterministicRoute(
        does="Refuses to collect quotation details before the customer consents.",
        carries="asks_only",
    ),
    "verified-policy-clarify": DeterministicRoute(
        does="Asks what the customer needs when a service turn matched nothing.",
        carries="asks_only",
    ),
    # --- routes that answer or escalate ----------------------------------
    "verified-policy": DeterministicRoute(
        does=(
            "Escalates a service question that needs authority the assistant "
            "does not have. Narrowed on 2026-08-07 by tj-rily."
        ),
        carries="escalates",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "service-confirmation-handoff": DeterministicRoute(
        does="Escalates once the customer confirms they want assembly service.",
        carries="escalates",
    ),
    "showroom-location": DeterministicRoute(
        does="Answers where the showroom is, with the maps link.",
        # Narrowed on 2026-08-09 by tj-6f4z: the bare word "office" used to
        # match this topic, in an office-furniture business.
        carries="verified_fact",
    ),
    "sales-fallback": DeterministicRoute(
        does="Answers a price objection, a retention signal or an off-catalog ask.",
        # The off-catalog branch names what Treejar does carry; the other two
        # ask for what a fair comparison or a later restart would need.
        carries="asks_only",
    ),
    "customer-facts-past-order": DeterministicRoute(
        does="Answers from stored customer facts about a previous order.",
        carries="verified_fact",
    ),
    "post-quotation-accepted": DeterministicRoute(
        does="Acknowledges that the customer accepted the quotation.",
        carries="acknowledges",
    ),
    "post-quotation-ack": DeterministicRoute(
        does="Acknowledges a reply that follows a delivered quotation.",
        carries="acknowledges",
    ),
    "post-quotation-context-ack": DeterministicRoute(
        does="Same, when the reply carries new context rather than a decision.",
        carries="acknowledges",
    ),
    "verified-catalog-functional-failure": DeterministicRoute(
        does=(
            "Ships the verified configuration when the model's rendering of it "
            "cannot be repaired. Demoted to second fallback on 2026-08-07."
        ),
        carries="verified_fact",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "verified-catalog-plan": DeterministicRoute(
        does=(
            "The model's own rendering of a verified catalog decision, kept "
            "only when every verified number survives it."
        ),
        carries="verified_fact",
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
}


# Snapshot of the routes whose history was already unknown when this file was
# written. It does not grow: a route added after 2026-08-07 must carry a date.
ROUTES_NEVER_RECHECKED_AT_INTRODUCTION = frozenset(
    label
    for label, route in DETERMINISTIC_CUSTOMER_ROUTES.items()
    if route.rechecked_on is None
)


# The remaining debt of tj-ja1v, written out rather than derived, so that a new
# route cannot join it without this list changing in the same commit.
#
# Each of these owns a turn and gives the customer a question and nothing else.
# For most of them that is honest -- the customer named an item the catalog does
# not hold, or a saved frame is unusable, and there is no verified fact to offer
# instead. `sales-fallback` is the one worth revisiting: two of its three
# branches could name a comparable catalog row rather than ask the customer to
# go and find the competitor's specifications themselves.
ROUTES_THAT_ONLY_ASK = frozenset(
    {
        "exact-quote-clarify-item",
        "proposal-clarify",
        "quote-consent-required",
        "quote-frame-repair-missing-items",
        "quote-resume-missing-items",
        "sales-fallback",
        "sales-order-clarify",
        "verified-policy-clarify",
    }
)
