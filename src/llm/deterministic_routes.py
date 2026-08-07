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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Prose = Literal["deterministic", "model_written"]


@dataclass(frozen=True, slots=True)
class DeterministicRoute:
    """One route that can own a customer-visible turn without the model."""

    does: str
    carries_write: bool = False
    prose: Prose = "deterministic"
    rechecked_against_model: str | None = None
    rechecked_on: str | None = None


_LUNA = "openai/gpt-5.6-luna"
_TODAY = "2026-08-07"


DETERMINISTIC_CUSTOMER_ROUTES: dict[str, DeterministicRoute] = {
    # --- routes that carry an action -------------------------------------
    "selection-confirmation": DeterministicRoute(
        does=(
            "Resolves the customer's chosen items against the catalog, confirms "
            "live stock and price, and persists or suspends the quote selection."
        ),
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "exact-quote-deterministic": DeterministicRoute(
        does="Creates the quotation for an exact SKU and quantity request.",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "quote-resume": DeterministicRoute(
        does="Creates the quotation once the missing customer details arrive.",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "sales-order-quote": DeterministicRoute(
        does="Creates the quotation for a multi-item sales-order request.",
        carries_write=True,
    ),
    "sales-order-quote-resume": DeterministicRoute(
        does="Creates the multi-item quotation after the follow-up resolves it.",
        carries_write=True,
    ),
    "sales-opportunity": DeterministicRoute(
        does="Writes the CRM opportunity and reports what was recorded.",
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "sales-opportunity-unverified": DeterministicRoute(
        does=("Same as sales-opportunity when the CRM row could not be read back."),
        carries_write=True,
        prose="model_written",
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    # --- routes that ask for one missing thing ---------------------------
    "name-gate": DeterministicRoute(
        does="Asks how to address the customer before the first substantive turn."
    ),
    "name-capture": DeterministicRoute(does="Acknowledges the name just given."),
    "detail-capture": DeterministicRoute(
        does="Acknowledges customer details captured mid-quote."
    ),
    "product-quantity-clarify": DeterministicRoute(
        does="Asks for the quantity behind a product reference that has none."
    ),
    "exact-quote-clarify-item": DeterministicRoute(
        does="Asks which catalog item an unresolved quote line refers to."
    ),
    "exact-quote-missing-details": DeterministicRoute(
        does="Asks for the customer details a quotation cannot be issued without."
    ),
    "quote-resume-missing-details": DeterministicRoute(
        does="Same, on the resume path."
    ),
    "quote-resume-missing-items": DeterministicRoute(
        does="Asks for the items behind a quote frame that has none."
    ),
    "quote-frame-repair-missing-items": DeterministicRoute(
        does="Asks the customer to re-confirm items when the saved frame is unusable."
    ),
    "sales-order-clarify": DeterministicRoute(
        does="Asks which items belong on an ambiguous multi-item order."
    ),
    "quote-brief-confirm": DeterministicRoute(
        does="Reads an unlabeled detail brief back for confirmation."
    ),
    "proposal-clarify": DeterministicRoute(
        does="Asks which items a proposal request should cover."
    ),
    "quote-consent-required": DeterministicRoute(
        does="Refuses to collect quotation details before the customer consents."
    ),
    "verified-policy-clarify": DeterministicRoute(
        does="Asks what the customer needs when a service turn matched nothing."
    ),
    # --- routes that answer or escalate ----------------------------------
    "verified-policy": DeterministicRoute(
        does=(
            "Escalates a service question that needs authority the assistant "
            "does not have. Narrowed on 2026-08-07 by tj-rily."
        ),
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "service-confirmation-handoff": DeterministicRoute(
        does="Escalates once the customer confirms they want assembly service."
    ),
    "showroom-location": DeterministicRoute(
        does="Answers where the showroom is, with the maps link."
    ),
    "sales-fallback": DeterministicRoute(
        does="Answers a price objection, a retention signal or an off-catalog ask."
    ),
    "customer-facts-past-order": DeterministicRoute(
        does="Answers from stored customer facts about a previous order."
    ),
    "post-quotation-accepted": DeterministicRoute(
        does="Acknowledges that the customer accepted the quotation."
    ),
    "post-quotation-ack": DeterministicRoute(
        does="Acknowledges a reply that follows a delivered quotation."
    ),
    "post-quotation-context-ack": DeterministicRoute(
        does="Same, when the reply carries new context rather than a decision."
    ),
    "verified-catalog-functional-failure": DeterministicRoute(
        does=(
            "Ships the verified configuration when the model's rendering of it "
            "cannot be repaired. Demoted to second fallback on 2026-08-07."
        ),
        rechecked_against_model=_LUNA,
        rechecked_on=_TODAY,
    ),
    "verified-catalog-plan": DeterministicRoute(
        does=(
            "The model's own rendering of a verified catalog decision, kept "
            "only when every verified number survives it."
        ),
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
