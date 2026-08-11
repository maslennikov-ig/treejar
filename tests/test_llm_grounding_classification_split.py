"""The grounding detector reports doubt before any repair is selected."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scripts.corpus_bridge import real_opening_acceptance

import src.llm.grounding_output as grounding_output
import src.llm.response_policy as response_policy
from src.llm.grounding_output import (
    GroundingOutputAction,
    GroundingOutputResult,
    GroundingViolation,
    enforce_grounding_output,
    repair_grounding_output,
)


def _unchanged_repair(
    text: str,
    *,
    language: str,
    violations: Iterable[GroundingViolation] | None = None,
    inventory_confirmed: bool = False,
    grounded_amounts: Iterable[object] | None = None,
) -> GroundingOutputResult:
    del language, inventory_confirmed, grounded_amounts
    return GroundingOutputResult(
        text=text,
        violations=tuple(violations or ()),
        action=GroundingOutputAction.UNCHANGED,
    )


def test_legacy_enforcement_name_is_only_an_alias_for_the_named_repair() -> None:
    assert enforce_grounding_output is repair_grounding_output


def test_classification_never_enters_the_repair_path(monkeypatch: Any) -> None:
    def fail_repair(*args: object, **kwargs: object) -> str:
        del args, kwargs
        raise AssertionError("classification entered the repair path")

    monkeypatch.setattr(grounding_output, "_repair", fail_repair)

    assert grounding_output.classify_grounding_output(
        "I will check stock and come back to you."
    ) == (GroundingViolation.FUTURE_STOCK_CHECK,)


def test_response_policy_passes_classification_to_the_named_repair(
    monkeypatch: Any,
) -> None:
    events: list[tuple[str, tuple[GroundingViolation, ...]]] = []
    expected = (GroundingViolation.FUTURE_STOCK_CHECK,)

    def classify(text: str, **kwargs: object) -> tuple[GroundingViolation, ...]:
        del text, kwargs
        events.append(("classify", expected))
        return expected

    def repair(
        text: str,
        **kwargs: object,
    ) -> GroundingOutputResult:
        violations = tuple(kwargs["violations"])
        events.append(("repair", violations))
        return _unchanged_repair(text, language="en", violations=violations)

    monkeypatch.setattr(response_policy, "classify_grounding_output", classify)
    monkeypatch.setattr(response_policy, "repair_grounding_output", repair)

    rendered = response_policy.render_reply(
        "A useful answer.",
        state=response_policy.ReplyPolicyState(language="en"),
        provenance="model",
    )

    assert rendered.text == "A useful answer."
    assert events == [("classify", expected), ("repair", expected)]


def test_acceptance_harness_passes_classification_to_the_named_repair(
    monkeypatch: Any,
) -> None:
    events: list[tuple[str, tuple[GroundingViolation, ...]]] = []
    expected = (GroundingViolation.UNVERIFIED_PRICE,)

    def classify(text: str, **kwargs: object) -> tuple[GroundingViolation, ...]:
        del text, kwargs
        events.append(("classify", expected))
        return expected

    def repair(text: str, **kwargs: object) -> GroundingOutputResult:
        violations = tuple(kwargs["violations"])
        events.append(("repair", violations))
        return _unchanged_repair(text, language="en", violations=violations)

    monkeypatch.setattr(
        real_opening_acceptance,
        "classify_grounding_output",
        classify,
    )
    monkeypatch.setattr(
        real_opening_acceptance,
        "repair_grounding_output",
        repair,
    )

    rendered = real_opening_acceptance.apply_shipped_output_guards(
        "A useful answer.",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
    )

    assert "A useful answer." in rendered
    assert events == [("classify", expected), ("repair", expected)]
