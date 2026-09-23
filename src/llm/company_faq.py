"""Owner-approved company facts that must reach the model without the RAG index.

The live knowledge base held no FAQ rows on 2026-09-23 (``index_documents`` is
never called), so a customer asking "Do you provide delivery and assembly in
Dubai?" got "I can't confirm Dubai delivery or assembly". The owner ruled the
same day that Noor answers these questions as ``docs/faq.md`` does. Only the
entries listed here are approved as standing facts; the rest of the FAQ still
touches manager-controlled terms (warranty, payment, price matching) and stays
out.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from src.llm.verified_answers import _entry_topics, _query_topics

logger = logging.getLogger(__name__)

_FAQ_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "faq.md"

# FAQ question number -> approval that makes it a standing fact.
APPROVED_FAQ_QUESTIONS: dict[int, str] = {
    9: "owner decision 2026-09-23",
    10: "owner decision 2026-09-23",
}

FAQ_SOURCE = "faq_static"


def _parse_approved_entries(text: str) -> tuple[dict[str, str], ...]:
    entries: list[dict[str, str]] = []
    for part in text.split("\n## ")[1:]:
        heading, _, body = part.partition("\n")
        number, dot, title = heading.strip().partition(". ")
        if not dot or not number.isdigit() or not body.strip():
            continue
        if int(number) not in APPROVED_FAQ_QUESTIONS:
            continue
        title = title.strip()
        entries.append(
            {
                "source": FAQ_SOURCE,
                "category": "faq",
                "title": title,
                "content": f"Q: {title}\nA: {body.strip()}",
            }
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def approved_faq_entries() -> tuple[dict[str, str], ...]:
    try:
        text = _FAQ_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Approved FAQ source is missing: %s", _FAQ_PATH)
        return ()
    entries = _parse_approved_entries(text)
    if len(entries) != len(APPROVED_FAQ_QUESTIONS):
        logger.warning(
            "Approved FAQ source yielded %d of %d entries: %s",
            len(entries),
            len(APPROVED_FAQ_QUESTIONS),
            _FAQ_PATH,
        )
    return entries


def with_approved_faq(
    query: str, faq_context: Sequence[Mapping[str, str]]
) -> list[dict[str, str]]:
    """Add approved FAQ entries whose topic the customer's message raises."""

    merged = [dict(item) for item in faq_context]
    topics = set(_query_topics(query))
    if not topics:
        return merged
    seen_titles = {str(item.get("title", "")).casefold() for item in merged}
    for entry in approved_faq_entries():
        if entry["title"].casefold() in seen_titles:
            continue
        if topics & _entry_topics(f"{entry['title']} {entry['content']}"):
            merged.append(dict(entry))
    return merged
