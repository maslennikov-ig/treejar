"""What every selling turn owes the customer, guaranteed rather than asked for.

Three rules were written down, all three were given to the model as directives,
and all three were measured at or near zero on 2026-08-09 over 82 blind reads of
41 packets:

    rule 11  a package at a combined total   0.28/2 on 18 reads
    rule 13  what the customer's company does  0.00/2 on 12 reads
    one question per reply                   broken on every realistic opening

Rule 7 was in the same place a day earlier at 0.08, and moved to 1.66 the moment
the opening guard started *carrying* the value proposition instead of asking the
model to. That is the whole argument for this module: **a deterministic
guarantee beats a directive where the behaviour is unconditional.**

Read S01 turn 2 for what the directives were up against. Asked to find out what
Cedarline Test Offices does, the model wrote "a test-office company" -- inferred
straight from the name, which the directive explicitly forbids -- and then asked
five questions in a numbered list, which the system prompt explicitly forbids.
The instruction was correct, present and ignored.

Everything here reads the customer, stored slots and catalog rows. Nothing reads
what Noor thinks she already did: that is the escape-clause pattern four rules
died on in `tj-2m5m.8`, and it is not reintroduced here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.llm.closed_question_guard import response_asks_customer_name
from src.services.customer_language import is_arabic_customer_language

# A question the guard itself folds in is not a second question. The rubric
# counts a folded pair as one and the consultative directive says so in as many
# words, so the cap is one question the model chose plus at most one the guard
# added.
_MODEL_QUESTION_LIMIT = 1

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u061f])\s+")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+")
# The lead-in that turns a list into a form. Measured on R04: the four items
# under "please share:" carry no question mark at all -- they are nouns, not
# questions -- so counting question marks misses the very shape the system
# prompt bans. The list itself is innocent; a bulleted set of products is good
# selling and must survive untouched. It is the request-for-information lead-in
# that makes the list a form, so that is what this matches.
_ASK_LIST_LEAD_IN_RE = re.compile(
    r"(?:"
    r"(?:could|can|would)\s+you\s+(?:please\s+)?(?:share|confirm|tell|let\s+me\s+know)|"
    r"please\s+(?:share|confirm|provide|send|let\s+me\s+know)|"
    r"(?:i|we)\s+(?:will\s+)?need\s+(?:the\s+following|to\s+know)|"
    r"let\s+me\s+know|"
    r"\u064a\u0631\u062c\u0649\s+(?:\u0645\u0634\u0627\u0631\u0643\u0629|\u062a\u0623\u0643\u064a\u062f|\u0625\u0631\u0633\u0627\u0644)|"
    r"\u0623\u062e\u0628\u0631\u0646\u064a"
    r")",
    re.IGNORECASE,
)


def _is_question(text: str) -> bool:
    return "?" in text or "\u061f" in text


def _question_lines(lines: list[str]) -> list[int]:
    return [index for index, line in enumerate(lines) if _is_question(line)]


def collapse_question_form(text: str) -> str:
    """One question per reply, whether or not it was punctuated as one.

    Measured 2026-08-09: S01 turn 2 asked five things in a numbered list, R04
    turn 2 asked four. Both faced a customer whose median conversation is two
    messages, and neither carried a catalog row. A customer handed a form
    answers none of it and leaves, which is what 36% of them do anyway.

    Two passes, because the two failures look different. R04's items are nouns
    under "please share:" and contain no question mark, so the form has to be
    found by its lead-in. S01's are punctuated questions and are found by
    counting. The first item survives either way -- it is the one the model
    thought most important -- and nothing but questions is ever dropped.
    """

    return _collapse_inline_questions(_collapse_ask_list(text))


def _collapse_ask_list(text: str) -> str:
    """A request for information followed by a list keeps one item.

    The surviving item is folded back onto the lead-in, because "please share:"
    followed by a lone "1." reads like a form with three items deleted -- which
    is what it is, and the customer should not have to see that.
    """

    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not _ASK_LIST_LEAD_IN_RE.search(line):
            continue
        first = index + 1
        while first < len(lines) and not lines[first].strip():
            first += 1
        item_indices = []
        cursor = first
        while cursor < len(lines) and (
            _LIST_ITEM_RE.match(lines[cursor]) or not lines[cursor].strip()
        ):
            if lines[cursor].strip():
                item_indices.append(cursor)
            cursor += 1
        if len(item_indices) < 2:
            continue
        kept = _LIST_ITEM_RE.sub("", lines[item_indices[0]]).strip()
        lead = line.rstrip()
        if lead.endswith(":"):
            merged = f"{lead} {kept}"
        else:
            merged = f"{lead}\n{lines[item_indices[0]]}"
        # Resume at the line after the last item, not after the blank lines the
        # scan ran through, so the paragraph break below the form survives.
        rebuilt = lines[:index] + [merged] + lines[item_indices[-1] + 1 :]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(rebuilt)).strip()
    return text


def _collapse_inline_questions(text: str) -> str:
    """Two questions in one paragraph are still two questions."""

    lines = text.split("\n")
    seen_question = False
    result: list[str] = []
    for line in lines:
        if not _is_question(line):
            result.append(line)
            continue
        if not seen_question:
            sentences = _SENTENCE_SPLIT_RE.split(line)
            kept: list[str] = []
            for sentence in sentences:
                if _is_question(sentence):
                    if seen_question:
                        continue
                    seen_question = True
                kept.append(sentence)
            result.append(" ".join(kept).strip())
            continue
        trimmed = _drop_trailing_questions(line)
        if trimmed:
            result.append(trimmed)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip()


def _drop_trailing_questions(line: str) -> str:
    kept = [
        sentence
        for sentence in _SENTENCE_SPLIT_RE.split(line)
        if not _is_question(sentence)
    ]
    return " ".join(part for part in kept if part.strip()).strip()


def refuse_to_chase_the_name(
    text: str,
    *,
    previous_assistant_turns: Sequence[str],
    customer_name: str | None,
) -> str:
    """Ask for the name once. If it does not come, carry on without it.

    Owner decision of 2026-08-10: the name is worth one passing question and
    nothing more. WhatsApp profiles are an unreliable source -- device names,
    emoji, trading names, blanks -- so the question is still asked, but a
    customer who ignores it has answered it. Asking a second time spends a turn
    on something they have already declined to give, in a median conversation
    two messages long.

    The condition is on the world, not on what Noor thinks she did: it reads the
    assistant's own previous turns and the stored name, both facts. The sibling
    case -- asking for a name we already hold -- belongs to
    `apply_closed_question_guard`, and both read the same signal list so they
    cannot drift apart.
    """

    if str(customer_name or "").strip():
        return text
    if not response_asks_customer_name(text):
        return text
    if not any(response_asks_customer_name(turn) for turn in previous_assistant_turns):
        return text

    stripped = _drop_name_questions(text)
    # An empty reply cannot be sent at all, so a repeated question beats one.
    return stripped or text


def _drop_name_questions(text: str) -> str:
    kept_lines: list[str] = []
    for line in text.split("\n"):
        if not response_asks_customer_name(line):
            kept_lines.append(line)
            continue
        kept = [
            sentence
            for sentence in _SENTENCE_SPLIT_RE.split(line)
            if not response_asks_customer_name(sentence)
        ]
        remainder = " ".join(part for part in kept if part.strip()).strip()
        if remainder:
            kept_lines.append(remainder)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()


_EN_ACTIVITY_QUESTION = "And what does your company actually do, day to day?"
_AR_ACTIVITY_QUESTION = "وما طبيعة عمل شركتكم فعليًا؟"
_EN_ACTIVITY_SIGNALS = (
    "what does your company",
    "what your company does",
    "line of work",
    "what kind of work",
    "what sort of work",
    "what does the company do",
    "nature of your business",
    "what business are you in",
    "day to day",
)
_AR_ACTIVITY_SIGNALS = ("طبيعة عمل", "مجال عمل", "ماذا تعمل شركت")


def asks_the_company_activity(text: str) -> bool:
    normalized = text.casefold()
    return any(signal in normalized for signal in _EN_ACTIVITY_SIGNALS) or any(
        signal in text for signal in _AR_ACTIVITY_SIGNALS
    )


def carry_the_company_question(text: str, *, language: str) -> str:
    """Fold in the one question rule 13 asks for, when nobody has asked it.

    Scored 0.00/2 on every one of the twelve reads where it was charged. The
    directive is explicit that a company's name is not its line of work, and on
    S01 the model read "Cedarline Test Offices" and asserted "a test-office
    company" rather than asking. An assertion is worse than a silence here: it
    closes the question in the transcript without ever putting it to the
    customer.

    Folded rather than appended as a second turn's worth of questions, which is
    what the rubric and the directive both mean by counting a folded pair as
    one.
    """

    if asks_the_company_activity(text):
        return text
    question = (
        _AR_ACTIVITY_QUESTION
        if is_arabic_customer_language(language)
        else _EN_ACTIVITY_QUESTION
    )
    body = text.rstrip()
    if not body:
        return question
    return f"{body} {question}"
