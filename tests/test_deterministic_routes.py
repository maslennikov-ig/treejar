"""A deterministic route cannot land unnoticed any more.

Nine of them accumulated over ten weeks, one at a time, and the only record of
why any existed was a test name. Two turned out to be treating the wrong cause
and one had lost its premise when the main model changed. This test is the
thing that was missing: a route the engine can send to a customer has to be
declared, and a route declared from now on has to say when it was last checked
against the model that is actually in production.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.llm import deterministic_routes as registry
from src.llm.deterministic_routes import (
    DETERMINISTIC_CUSTOMER_ROUTES,
    ROUTES_NEVER_RECHECKED_AT_INTRODUCTION,
    ROUTES_THAT_ONLY_ASK,
)

_ROUTE_SOURCES = ("src/llm/engine.py", "src/llm/order_quote_routes.py")
_RESPONSE_BUILDERS = frozenset(
    {"_build_static_response", "build_static_response", "_verified_prose_response"}
)


def _literal_route_label(node: ast.expr) -> str | None:
    """The route label in a response-builder argument, when it is written out.

    A label assembled from a variable is invisible here. Those are declared in
    the registry by hand, and the registry test below is what keeps the two in
    step for every label a reader can see in the source.
    """

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.rsplit("|", 1)[-1]
    if isinstance(node, ast.JoinedStr) and node.values:
        tail = node.values[-1]
        if (
            isinstance(tail, ast.Constant)
            and isinstance(tail.value, str)
            and "|" in tail.value
        ):
            return tail.value.rsplit("|", 1)[-1]
    return None


def _labels_in_source() -> dict[str, tuple[str, int]]:
    found: dict[str, tuple[str, int]] = {}
    for source in _ROUTE_SOURCES:
        tree = ast.parse(Path(source).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            argument: ast.expr | None = None
            if name in _RESPONSE_BUILDERS:
                argument = next(
                    (kw.value for kw in node.keywords if kw.arg == "model_name"),
                    node.args[1] if len(node.args) > 1 else None,
                )
            elif name == "OrderQuoteSideEffectPlan":
                argument = next(
                    (kw.value for kw in node.keywords if kw.arg == "model_suffix"),
                    None,
                )
            if argument is None:
                continue
            label = _literal_route_label(argument)
            if label and label != "error":
                found.setdefault(label, (source, node.lineno))
    return found


def test_every_route_the_engine_can_send_is_declared() -> None:
    undeclared = {
        label: where
        for label, where in _labels_in_source().items()
        if label not in DETERMINISTIC_CUSTOMER_ROUTES
    }

    assert not undeclared, (
        "These routes can reach a customer and are not in "
        f"src/llm/deterministic_routes.py: {undeclared}. Add an entry saying "
        "what the route does and the date it was last checked against the "
        "model in production."
    )


def test_the_registry_does_not_describe_routes_that_no_longer_exist() -> None:
    """A retired route must leave the registry with it, or the record lies."""

    in_source = set(_labels_in_source())
    # Labels built from a variable are invisible to the scan above.
    assembled_at_runtime = {
        "sales-opportunity",
        "sales-opportunity-unverified",
        "verified-policy",
        "verified-catalog-plan",
    }
    stale = set(DETERMINISTIC_CUSTOMER_ROUTES) - in_source - assembled_at_runtime

    assert not stale, f"registry describes routes that are gone: {sorted(stale)}"


@pytest.mark.parametrize("label", sorted(DETERMINISTIC_CUSTOMER_ROUTES))
def test_every_declared_route_says_what_it_does(label: str) -> None:
    route = DETERMINISTIC_CUSTOMER_ROUTES[label]

    assert route.does.strip()
    assert route.does.strip().endswith(".")


def test_a_route_added_from_now_on_carries_a_dated_recheck() -> None:
    """The undated ones are a snapshot of what was already unknown.

    That set is frozen deliberately. It is the measure of the debt, and a new
    route joining it would hide the next instance of exactly this problem.
    """

    undated = {
        label
        for label, route in DETERMINISTIC_CUSTOMER_ROUTES.items()
        if route.rechecked_on is None
    }

    assert undated == set(ROUTES_NEVER_RECHECKED_AT_INTRODUCTION)


@pytest.mark.parametrize("label", sorted(DETERMINISTIC_CUSTOMER_ROUTES))
def test_a_recheck_names_both_the_model_and_the_date(label: str) -> None:
    """Half a record is what the old test names were."""

    route = DETERMINISTIC_CUSTOMER_ROUTES[label]

    assert (route.rechecked_on is None) == (route.rechecked_against_model is None)


def test_every_route_that_carries_a_write_is_marked_as_one() -> None:
    """These are the ones that cannot simply be switched off to be tested."""

    writers = {
        label
        for label, route in DETERMINISTIC_CUSTOMER_ROUTES.items()
        if route.carries_write
    }

    assert writers == {
        "selection-confirmation",
        "exact-quote-deterministic",
        "quote-resume",
        "sales-order-quote",
        "sales-order-quote-resume",
        "sales-opportunity",
        "sales-opportunity-unverified",
    }


@pytest.mark.parametrize("label", sorted(DETERMINISTIC_CUSTOMER_ROUTES))
def test_a_route_that_carries_a_write_reports_what_it_wrote(label: str) -> None:
    """A route that changed something owes the customer the result of it.

    Every one of these creates a quotation, persists a selection or writes a
    CRM row. A reply that does not name what happened leaves the customer to
    guess, which is the failure tj-ja1v measured at 13.3 against 24.8.
    """

    route = DETERMINISTIC_CUSTOMER_ROUTES[label]

    if route.carries_write:
        assert route.carries == "verified_fact"


def test_the_routes_that_still_only_ask_are_the_ones_named() -> None:
    """The tj-ja1v contract, with the remaining debt written down.

    A route owning a customer-visible turn carries a verified fact, or
    acknowledges what the customer just said, or escalates -- or it asks and
    gives nothing, which is the shape that scored 13.3. That last set is
    allowed to shrink and must never grow silently: adding a route to it means
    editing this list, in the same commit, on purpose.
    """

    asks_only = {
        label
        for label, route in DETERMINISTIC_CUSTOMER_ROUTES.items()
        if route.carries == "asks_only"
    }

    assert asks_only == set(ROUTES_THAT_ONLY_ASK)


def test_no_route_can_only_ask_and_also_claim_a_recheck() -> None:
    """A recheck that left the turn empty is not a recheck worth recording."""

    for label in ROUTES_THAT_ONLY_ASK:
        assert DETERMINISTIC_CUSTOMER_ROUTES[label].rechecked_on is None, label


def test_the_registry_reports_how_much_of_itself_is_unverified() -> None:
    """Not a threshold, a number. tj-swgu.7 is what moves it."""

    total = len(DETERMINISTIC_CUSTOMER_ROUTES)
    unverified = len(ROUTES_NEVER_RECHECKED_AT_INTRODUCTION)

    assert unverified < total
    assert registry.__doc__ is not None
