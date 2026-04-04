from __future__ import annotations

import re

__all__ = ["is_high_confidence_first_turn_order"]

_CONSULTATIVE_BLOCKERS = (
    "what options",
    "options",
    "recommend",
    "recommendation",
    "pricing",
    "price",
    "quote",
    "quotation",
    "availability",
    "available",
    "moq",
    "wholesale",
    "bulk pricing",
    "ideas",
    "catalog",
    "show me",
)

_QUANTITY_RE = re.compile(r"\b\d{1,4}\b")
_PRODUCT_RE = re.compile(
    r"\b(?:"
    r"acoustic pods?|"
    r"phone booths?|"
    r"workstations?|"
    r"chairs?|"
    r"desks?|"
    r"pods?|"
    r"booths?|"
    r"tables?|"
    r"sofas?"
    r")\b"
)
_NEED_RE = re.compile(r"\b(?:i need|we need)\b")
_DELIVERY_INSTALL_RE = re.compile(
    r"\b(?:deliver|delivered|delivery|install|installed|installation)\b"
)
_EXPLICIT_FULFILLMENT_RE = re.compile(
    r"\b(?:place the order|confirm the order|please deliver|arrange delivery|arrange installation)\b"
)
_LOCATION_RE = re.compile(
    r"\b(?:to|in|at)\s+"
    r"(?!stock\b|bulk\b|wholesale\b|available\b|availability\b|next\b|this\b|the\b|our\b|your\b)"
    r"[a-z]+(?:\s+[a-z]+){0,2}\b"
)
_TIMEFRAME_RE = re.compile(
    r"\b(?:"
    r"by\s+(?:next\s+)?(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"this\s+(?:week|month)|"
    r"today|tomorrow"
    r")\b"
)


def is_high_confidence_first_turn_order(text: str) -> bool:
    """Return True only for narrow, concrete first-turn order handoff candidates."""
    normalized = " ".join(text.casefold().split())
    if not normalized:
        return False

    if any(blocker in normalized for blocker in _CONSULTATIVE_BLOCKERS):
        return False

    if not _QUANTITY_RE.search(normalized):
        return False

    if not _PRODUCT_RE.search(normalized):
        return False

    delivery_or_install = bool(_DELIVERY_INSTALL_RE.search(normalized))
    explicit_fulfillment = bool(_EXPLICIT_FULFILLMENT_RE.search(normalized))
    need_with_fulfillment = bool(_NEED_RE.search(normalized) and delivery_or_install)

    if not (explicit_fulfillment or need_with_fulfillment):
        return False

    logistics_signal_count = sum(
        (
            delivery_or_install,
            bool(_LOCATION_RE.search(normalized)),
            bool(_TIMEFRAME_RE.search(normalized)),
        )
    )
    return logistics_signal_count >= 2
