"""Presentation helpers for owner-facing reports and alerts.

This replaces the former ``report_localization`` module. That module existed to
turn already-English enum values into Russian labels, and it had no locale
switch: with the product settled on English there is nothing left to translate.
What survives here is the part that was never translation -- normalising the
several spellings a trigger arrives in, naming a criterion the judge left blank,
and the placeholders shown when a value is missing.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import logfire

from src.quality.manager_schemas import MANAGER_RULE_NAMES
from src.quality.schemas import RULE_NAMES

logger = logging.getLogger(__name__)

# Escalation reasons reach a report from several places -- the dialogue runner,
# the manager webhook, the verified-answer policy -- and each spells them its own
# way. One label per reason, so a weekly report does not count the same cause
# four times under four names.
_REPORT_TRIGGER_LABELS: Mapping[str, str] = {
    "idle 3h": "no reply for 3 hours",
    "closed": "conversation closed",
    "customer_angry": "customer unhappy",
    "customer angry": "customer unhappy",
    "complex_order": "complex order",
    "complex order": "complex order",
    "human_requested": "manager requested",
    "human requested": "manager requested",
    "customer asked for manager": "manager requested",
    "customer asked for a manager": "manager requested",
    "customer requested human": "manager requested",
    "customer wants human": "manager requested",
    "manager requested": "manager requested",
    "manager_requested": "manager requested",
    "order_confirmation": "order confirmation",
    "order confirmation": "order confirmation",
    "customer not convinced": "customer not ready to buy",
    "order > 10k aed": "order above 10,000 AED",
    "b2b wholesale order": "B2B wholesale order",
    "low_score": "score below threshold",
    "threshold_breach": "score below threshold",
}

_CRITERION_STATUS_LABELS: Mapping[int, str] = {
    0: "not met",
    1: "partially met",
    2: "met",
}

_RED_FLAG_TITLE_LABELS: Mapping[str, str] = {
    "missing_identity": "No identification",
    "hard_deflection": "Hard deflection",
    "unverified_commitment": "Unverified commitment",
    "ignored_question": "Customer question ignored",
    "bad_tone": "Inappropriate tone",
}

_RED_FLAG_EXPLANATION_LABELS: Mapping[str, str] = {
    "missing_identity": (
        "The assistant did not introduce itself as Noor from Treejar in its first reply."
    ),
    "hard_deflection": (
        "The assistant handed the customer to a manager too quickly, "
        "without trying to help."
    ),
    "unverified_commitment": (
        "The assistant promised facts or commitments unconfirmed by the context."
    ),
    "ignored_question": "A direct customer question got no substantive answer.",
    "bad_tone": "An inappropriate or off-putting tone was used in the conversation.",
}

_MISSING_VALUES = frozenset({"n/a", "na", "unknown", "none", ""})


def owner_na() -> str:
    """Owner-facing replacement for a value that does not apply."""
    return "n/a"


def owner_unknown(*, kind: str = "generic") -> str:
    """Owner-facing replacement for a value that is missing."""
    if kind == "person":
        return "not specified"
    if kind == "stage":
        return "unknown stage"
    if kind == "trigger":
        return "other reason"
    return "unknown"


def _log_presentation_miss(*, surface: str, module: str, value: str) -> None:
    logfire.info(
        "owner_presentation.miss",
        surface=surface,
        module=module,
        value=value,
    )
    logger.warning(
        "owner_presentation.miss surface=%s module=%s value=%s",
        surface,
        module,
        value,
    )


def format_quality_rating(value: str | None) -> str:
    """Render a canonical rating for display: ``good`` -> ``Good``."""
    raw = (value or "").strip()
    if raw.lower() in _MISSING_VALUES:
        return owner_unknown()
    return raw.capitalize()


def format_sales_stage(value: str | None) -> str:
    """Render a sales stage enum for display: ``needs_analysis`` -> ``Needs analysis``."""
    raw = (value or "").strip()
    if raw.lower() in _MISSING_VALUES:
        return owner_unknown(kind="stage")
    return raw.replace("_", " ").capitalize()


def format_report_trigger(
    value: str | None,
    *,
    surface: str = "owner_output",
    module: str = "owner_presentation",
) -> str:
    """Normalise an escalation trigger to one label per underlying reason."""
    raw = (value or "").strip()
    normalized = raw.lower()

    if normalized in _MISSING_VALUES:
        return owner_unknown(kind="trigger")

    if "verified-answer policy requires manager confirmation" in normalized:
        return "manager confirmation required"

    label = _REPORT_TRIGGER_LABELS.get(normalized)
    if label is not None:
        return label

    # An unmapped trigger is an internal string -- a policy sentence, a raw
    # enum, whatever the caller happened to pass -- and it does not belong in an
    # owner-facing alert. Show the generic reason and log the miss, because a
    # spelling that keeps arriving here belongs in the map above.
    _log_presentation_miss(surface=surface, module=module, value=raw)
    return owner_unknown(kind="trigger")


def format_criterion_status(score: int | None) -> str:
    """Render a 0-2 criterion score as words."""
    if score is None:
        return owner_na()
    return _CRITERION_STATUS_LABELS.get(score, owner_unknown())


def quality_rule_name(rule_number: int | None, value: str | None = None) -> str:
    """Name a quality criterion by its number, canonically.

    The rule number wins over whatever wording the stored review carries, so a
    report rendered today reads the same for rule 1 as one rendered a year ago.
    Old rows hold whatever phrasing the judge used at the time.
    """
    if rule_number is not None and rule_number in RULE_NAMES:
        return RULE_NAMES[rule_number]
    return (value or "").strip() or "Evaluation criterion"


def manager_rule_name(rule_number: int | None, value: str | None = None) -> str:
    """Name a manager criterion by its number, canonically."""
    if rule_number is not None and rule_number in MANAGER_RULE_NAMES:
        return MANAGER_RULE_NAMES[rule_number]
    return (value or "").strip() or "Manager evaluation criterion"


def red_flag_title(code: str | None, value: str | None = None) -> str:
    """Title a red flag deterministically, falling back to the judge's wording."""
    if code:
        label = _RED_FLAG_TITLE_LABELS.get(code.strip().lower())
        if label:
            return label
    return (value or "").strip() or "Critical signal"


def red_flag_explanation(code: str | None, value: str | None = None) -> str:
    """Explain a red flag deterministically, falling back to the judge's wording."""
    if code:
        label = _RED_FLAG_EXPLANATION_LABELS.get(code.strip().lower())
        if label:
            return label
    return (value or "").strip() or "The conversation needs a manual review."
