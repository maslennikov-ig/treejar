"""Shared response-policy composition helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _has_meaningful_reply(text: str) -> bool:
    return any(character.isalnum() for character in text)


def apply_guard_with_reply_bound(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
) -> str:
    candidate = guard(text)
    if _has_meaningful_reply(text) and not _has_meaningful_reply(candidate):
        logger.error(
            "Response guard removed the reply: guard=%s before_chars=%d after_chars=%d",
            guard_name,
            len(text),
            len(candidate),
        )
        return text
    return candidate
