"""Last deterministic guard before a reply leaves the application."""

from __future__ import annotations

import json
from typing import Any

from src.llm.language_guard import enforce_customer_reply_language
from src.llm.opening_guard import (
    canonical_discovery_question,
    canonical_name_question,
    fold_name_question,
    name_question_conjunction,
)
from src.services.customer_language import normalize_customer_language

_STRUCTURED_PAYLOAD_FALLBACK = {
    "en": (
        "I want to make sure the details I give you are accurate. Which point "
        "would you like me to confirm first?"
    ),
    "ar": "أريد التأكد من دقة التفاصيل التي أقدمها لك. ما النقطة التي تريد أن أؤكدها أولًا؟",
}


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = stripped[3:].lstrip()
    if stripped[:4].casefold() == "json":
        stripped = stripped[4:].lstrip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped


def looks_like_structured_payload(output: Any) -> bool:
    """Whether the text is a JSON object/array rather than customer prose.

    Structural, not lexical: internal model contracts (the claim contract among
    them) ask for a JSON envelope, and a reasoning model that runs out of
    completion tokens returns that envelope cut mid-string. Such text parses as
    nothing, yet it is not a plain-text answer and must never be sent as one.
    """
    return _strip_code_fence(str(output or ""))[:1] in {"{", "["}


def _replace_structured_payload(text: str, *, language: str) -> str:
    """Final invariant: a JSON envelope never reaches the customer.

    A readable envelope that carries a prose `answer` gives that answer back;
    anything else becomes a short neutral notice in the customer's language.
    """
    if not looks_like_structured_payload(text):
        return text
    try:
        parsed = json.loads(_strip_code_fence(text))
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        answer = parsed.get("answer")
        if (
            isinstance(answer, str)
            and answer.strip()
            and not looks_like_structured_payload(answer)
        ):
            return answer.strip()
    normalized = normalize_customer_language(language)
    return _STRUCTURED_PAYLOAD_FALLBACK.get(
        normalized, _STRUCTURED_PAYLOAD_FALLBACK["en"]
    )


def _fold_trailing_name_question(text: str, *, language: str) -> str:
    """Make the canonical name ask share an existing question mark."""

    stripped = text.rstrip()
    trailing_whitespace = text[len(stripped) :]
    name_question = canonical_name_question(language)
    if not stripped.endswith(name_question):
        return text

    prefix = stripped[: -len(name_question)].rstrip()
    guarded_prefix = enforce_customer_reply_language(prefix, language=language)
    question_positions = [
        position for mark in ("?", "؟") if (position := guarded_prefix.find(mark)) >= 0
    ]
    if not question_positions:
        if guarded_prefix == prefix:
            return text
        return f"{guarded_prefix} {name_question}{trailing_whitespace}"

    position = min(question_positions)
    tail = guarded_prefix[position + 1 :].replace("?", "").replace("؟", "")
    conjunction = (
        "، وكيف أخاطبك؟"
        if normalize_customer_language(language) == "ar"
        else ", and how should I address you?"
    )
    return (
        f"{guarded_prefix[:position].rstrip()}{conjunction}{tail}{trailing_whitespace}"
    )


def _asks_anything(text: str) -> bool:
    return "?" in text or "؟" in text


def _restore_lost_discovery(guarded: str, before: str, *, language: str) -> str:
    """Give back the questions the language guard just removed.

    `tj-yiiq`. On dialog 293 the removed second-language sentence was the only
    place the reply asked the customer anything, so a fix for the language left
    a first turn that asked for a name and nothing else. The opening guard folds
    the name ask into a question already standing there, so that sentence can
    carry both asks and a removal can take the whole turn's questions with it.

    Bounded to a first turn, which is the only turn that ends with our own name
    ask or its folded form: re-asking what someone already told us is its own
    defect.
    """

    stripped = guarded.rstrip()
    trailing = guarded[len(stripped) :]
    name_question = canonical_name_question(language)
    discovery = canonical_discovery_question(language)
    asked_the_name = name_question in before or (
        name_question_conjunction(language) in before
    )

    if stripped.endswith(name_question):
        body = stripped[: -len(name_question)].rstrip()
        if _asks_anything(body):
            return guarded
        rebuilt = f"{body} {discovery} {name_question}".strip()
    elif not _asks_anything(stripped) and asked_the_name:
        rebuilt = f"{stripped} {discovery} {name_question}".strip()
    else:
        return guarded

    return f"{fold_name_question(rebuilt, language=language)}{trailing}"


def finalize_customer_reply_text(text: str, *, language: str) -> str:
    """Enforce the selected language and one first-turn question at send time."""

    original = _replace_structured_payload(str(text or ""), language=language)
    folded = _fold_trailing_name_question(original, language=language)
    guarded = enforce_customer_reply_language(folded, language=language)
    if guarded == original:
        return guarded
    # The fold removes foreign narrative of its own, so what the reply lost is
    # only visible against the text this boundary was handed.
    return _restore_lost_discovery(guarded, folded, language=language)
