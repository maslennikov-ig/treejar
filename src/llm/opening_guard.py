"""Deterministic first-turn dialogue opening guard.

The first reply answers the customer and asks for the name in passing. It used
to do the opposite: the model never ran, and the whole turn was a fixed request
for a name.

The cost was measured, not suspected. 34% of real customers open with a bare
greeting and nothing else, 36% never send a second message, and the median
conversation is two customer messages -- so the median customer never saw a
product or a price, and for a third of conversations the only thing Treejar
ever said to them was "may I know your name". Both independent research reports
of 2026-08-09 named that opening as the single worst move available on this
channel.

Owner decision of 2026-08-10, which this module implements:

- The reply answers first. The name question rides along at the end of it.
- The WhatsApp profile name is not trusted as a source: profiles carry device
  names, emoji, trading names and blanks.
- Ask once. If the customer does not give a name, carry on without one --
  `src/llm/sales_turn_guard.py` holds that half, because this module only ever
  sees the first turn.

What stays deterministic is what the model measurably will not say on its own:
who Treejar is, what it can do right now, and a catalog anchor price. Rule 7,
the value proposition, scored zero in 26 of 26 transcripts while it was left to
a directive.
"""

from __future__ import annotations

import re

from src.llm.closed_question_guard import response_asks_customer_name
from src.llm.money import contains_customer_output_currency

_EN_IDENTITY = "Hello, I'm Noor from Treejar."
_EN_NAME_QUESTION = "And how should I address you?"
_AR_IDENTITY = "مرحبًا، أنا Noor من Treejar."
_AR_NAME_QUESTION = "وكيف أخاطبك؟"

# What Treejar is, which is rule 7 and which the model does not say on its own.
#
# The wording earns its keep twice. It has to name a line of business, and it
# has to survive `enforce_grounding_output`: the clause this replaced promised
# "UAE delivery with installation", an unverified service commitment that the
# grounding policy is right to cut. It only ever reached a customer because the
# old gate returned a static reply and skipped grounding altogether. What is
# left is true on every turn without a tool call -- who we are, and how we work.
_EN_CAPABILITY = (
    "We supply office furniture across the UAE, and I quote from our own catalog "
    "with confirmed prices and stock."
)
_AR_CAPABILITY = (
    "نورّد أثاث المكاتب في الإمارات، وأعمل من كتالوجنا وأؤكد كل سعر وتوفر قبل إرساله."
)


def _is_arabic_language(language: str) -> bool:
    normalized = str(language or "").strip().casefold()
    return normalized in {"ar", "arabic", "العربية"}


def _has_identity(text: str) -> bool:
    normalized = text.casefold()
    return "noor" in normalized and "treejar" in normalized


def _has_customer_name(customer_name: str | None) -> bool:
    return bool(str(customer_name or "").strip())


def _strip_generic_english_opening(text: str) -> str:
    body = text.lstrip()
    body = re.sub(r"\A(?:hello|hi|hey)\b[\s!,.:-]*", "", body, count=1, flags=re.I)
    body = re.sub(
        r"\A(?:welcome\s+to\s+treejar)\b[\s!,.:-]*(?:[^\w\s]+\s*)?",
        "",
        body,
        count=1,
        flags=re.I,
    )
    return body.lstrip()


def _strip_legacy_identity(text: str) -> str:
    body = text.lstrip()
    # `I'm` and `I’m` are the same word, and until 2026-08-10 this pattern knew
    # only the straight one. The model writes the typographic apostrophe, so its
    # own introduction survived the strip, `_has_identity` then saw it, and the
    # whole reply was discarded. Four of twenty customers -- every one of them a
    # bare greeting -- got the identity line and nothing else. Matched here
    # rather than rewritten, so the customer still reads the model's own
    # punctuation.
    body = re.sub(
        r"\A(?:hello|hi|hey)?[\s!,.:-]*(?:i(?:['’ʼ]| a)m|i am)\s+"
        r"(?:si[y]yad|noor)\s+from\s+treejar[\s!,.:-]*",
        "",
        body,
        count=1,
        flags=re.I,
    )
    body = re.sub(
        r"\Aمرحبًا،\s*أنا\s+(?:Si[y]yad|Noor)\s+من\s+Treejar[\s.،!]*",
        "",
        body,
        count=1,
    )
    return body.lstrip()


def _strip_own_capability(text: str, capability: str) -> str:
    """Drop a capability sentence the model wrote itself, so ours is the only one."""

    if capability not in text:
        return text
    return " ".join(text.replace(capability, " ").split())


# The trailing `\s*` keeps each sentence's own spacing attached to it, so
# removing one takes its blank line with it instead of welding its neighbours
# together.
_SENTENCE_RE = re.compile(r"[^.!?؟\n]+(?:[.!?؟]+|\n+|\Z)\s*")


def _drop_identity_sentences(text: str) -> str:
    """Remove the model's own introduction, and only that.

    This used to blank the whole reply the moment "Noor" and "Treejar" both
    appeared anywhere in it. The intent was right -- our identity line is
    already there and two of them read badly -- but the blast radius was the
    entire answer. On 2026-08-10 that cost four of twenty customers everything
    the model had written for them, including the one question that would have
    moved the conversation on.

    A duplicate introduction is one sentence. Only that sentence goes.
    """

    if not _has_identity(text):
        return text
    kept = [
        part
        for part in _SENTENCE_RE.findall(text)
        if not _has_identity(part) or not part.strip()
    ]
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()


def apply_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
    anchor_line: str | None = None,
) -> str:
    """Ensure the first customer-facing reply carries value before it asks.

    Order is the whole point: who we are, what we can do now, the price, the
    answer to what they actually asked, and only then the name question folded
    onto the end of it.
    """

    if not is_first_turn:
        return text

    body = text.strip()
    if not body:
        return text

    is_arabic = _is_arabic_language(language)
    identity = _AR_IDENTITY if is_arabic else _EN_IDENTITY
    capability = _AR_CAPABILITY if is_arabic else _EN_CAPABILITY
    name_question = _AR_NAME_QUESTION if is_arabic else _EN_NAME_QUESTION

    body = _strip_legacy_identity(body) or body
    if not is_arabic:
        body = _strip_generic_english_opening(body) or body
    body = _strip_own_capability(body, capability).strip()
    body = _drop_identity_sentences(body)

    parts = [f"{identity} {capability}"]
    if anchor_line and not contains_customer_output_currency(body):
        parts.append(anchor_line)
    if body:
        parts.append(body)

    if not _has_customer_name(customer_name) and not response_asks_customer_name(body):
        parts[-1] = f"{parts[-1].rstrip()} {name_question}"

    return "\n\n".join(parts)
