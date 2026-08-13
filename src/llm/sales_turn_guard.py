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
_QUESTION_ITEM_RE = re.compile(
    r"^(?:(?:who|what|when|where|why|how|which|whose|can|could|would|should|"
    r"do|does|did|is|are|was|were|will|may)\b|"
    r"(?:هل|ما|ماذا|من|متى|أين|كيف|كم|أي|لماذا)\b)",
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
            if kept and kept[-1] not in ".!?\u061f":
                if _QUESTION_ITEM_RE.match(kept):
                    terminal = "\u061f" if re.search(r"[\u0600-\u06ff]", kept) else "?"
                else:
                    terminal = "."
                kept = f"{kept}{terminal}"
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


def _ask_item_lines(lines: list[str]) -> set[int]:
    """The item lines of a form, found the same way the fold finds them.

    A noun under "please share:" is an ask with the question mark left off, so
    the proof below has to treat it as one. It mirrors `_collapse_ask_list`
    exactly, two-item minimum included: a single item is not a form and the
    fold leaves it alone, so the proof must protect it.
    """

    items: set[int] = set()
    for index, line in enumerate(lines):
        if not _ASK_LIST_LEAD_IN_RE.search(line):
            continue
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        found: list[int] = []
        while cursor < len(lines) and (
            _LIST_ITEM_RE.match(lines[cursor]) or not lines[cursor].strip()
        ):
            if lines[cursor].strip():
                found.append(cursor)
            cursor += 1
        if len(found) >= 2:
            items.update(found)
    return items


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", str(text or "").casefold(), flags=re.UNICODE)


def _appear_in_order(required: Sequence[str], available: Sequence[str]) -> bool:
    cursor = iter(available)
    return all(any(word == candidate for candidate in cursor) for word in required)


def _content_words(text: str) -> list[str]:
    """Every word the fold is not allowed to touch.

    Everything that is not a question and not an item of a form. This is the
    line between the two removals: a surplus question costs the customer
    nothing, and anything else costs them the answer they came for.
    """

    lines = text.split("\n")
    forms = _ask_item_lines(lines)
    kept: list[str] = []
    for index, line in enumerate(lines):
        if index in forms:
            continue
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            if sentence.strip() and not _is_question(sentence):
                kept.extend(_words(sentence))
    return kept


def only_asks_were_dropped(text: str, candidate: str) -> bool:
    """Whether the fold took surplus asks and nothing else.

    `collapse_question_form` and `refuse_to_chase_the_name` both remove without
    writing a replacement, so under D1 neither may be trusted on its say-so.
    What makes them safe is narrower than a replacement and provable: they take
    only the reply's own surplus asks, and everything the customer came for
    survives in place.

    Two clauses, and both are needed. Nothing is invented -- the candidate's
    words are a subsequence of the original's, so no guard can quietly write
    customer-facing text here. And every content word survives in order. When
    either fails the guard does not edit the reply; it raises a flag and the
    judge reads it, which is exactly what D1 asks for in the case where the
    deterministic rule turns out to be wrong about a particular reply.
    """

    available = _words(candidate)
    if not _appear_in_order(available, _words(text)):
        return False
    return _appear_in_order(_content_words(text), available)


def refuse_to_chase_the_name(
    text: str,
    *,
    customer_name_asked: bool,
    customer_name: str | None,
    ask_before_filling: bool = False,
) -> str:
    """Ask for the name once. If it does not come, carry on without it.

    Owner decision of 2026-08-10: the name is worth one passing question and
    nothing more. WhatsApp profiles are an unreliable source -- device names,
    emoji, trading names, blanks -- so the question is still asked, but a
    customer who ignores it has answered it. Asking a second time spends a turn
    on something they have already declined to give, in a median conversation
    two messages long.

    The condition is the explicit ask slot recorded when a reply is selected,
    never a text match over assistant history. Clearing that slot is the only
    re-elicitation mechanism. `ask_before_filling` is the named confirmation
    exception: confirming a supplied value is not another attempt to fill it.
    """

    if str(customer_name or "").strip():
        return text
    if not response_asks_customer_name(text):
        return text
    if ask_before_filling or not customer_name_asked:
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


# --- a deferral is not an answer, tj-vz7o.10.1 ----------------------------
#
# Measured 2026-08-10 on a real customer opening: asked "will you also assembly
# the desk upon delivery?", the reply ended "Current stock, mobile-drawer
# options, and whether assembly can be included for delivery within 2-3 days
# still need confirmation." Every word of that is true and the customer still
# learned nothing about who would find out, or whether anyone would. The judge
# scored it as an ignored request, and reading it by eye agrees.
#
# Stock is deliberately absent from the subjects below. Promising to go and
# check stock is a `FUTURE_STOCK_CHECK` violation that `grounding_output`
# removes on purpose, and a guard that adds a sentence the next guard deletes
# is worse than no guard.
_DEFERRAL_RE = re.compile(
    r"\b(?:still\s+)?needs?\s+(?:to\s+be\s+)?confirm(?:ed|ation)\b"
    r"|\bneeds?\s+confirming\b"
    r"|\b(?:remains?|are|is)\s+(?:still\s+)?unconfirmed\b"
    r"|\bnot\s+(?:yet\s+)?confirmed\b"
    r"|\bto\s+be\s+confirmed\b"
    r"|يحتاج\s+إلى\s+تأكيد"
    r"|غير\s+مؤكد",
    re.IGNORECASE,
)
_COMMITMENT_RE = re.compile(
    r"\b(?:i|we)(?:'ll|\s+will)\s+(?:confirm|check|verify|find\s+out)\b"
    r"|\b(?:come|get|revert)\s+back\s+to\s+you\b"
    r"|\b(?:i|we)(?:'ll|\s+will)\s+(?:update|let)\s+you\b"
    r"|سأؤكد|سأعود\s+إليك",
    re.IGNORECASE,
)
# Ordered: the first subject the deferral actually names is the one committed to.
_DEFERRED_SUBJECTS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\bassembl|\binstall|التركيب", re.IGNORECASE),
        "assembly",
        "التركيب",
    ),
    (
        re.compile(
            r"\bdeliver|\blead\s*time|\btimeline|التسليم",
            re.IGNORECASE,
        ),
        "the delivery timing",
        "موعد التسليم",
    ),
    (
        re.compile(r"\bwarrant|الضمان", re.IGNORECASE),
        "the warranty terms",
        "شروط الضمان",
    ),
    (
        re.compile(r"\bpayment|\bterms\b|الدفع", re.IGNORECASE),
        "the payment terms",
        "شروط الدفع",
    ),
)


def commit_to_what_you_deferred(text: str, *, language: str) -> str:
    """Say who will find out, or do not raise it at all.

    Reads only the reply's own words: it fires on a deferral this text states,
    and names a subject this text names. Nothing here consults what Noor
    believes she already did.

    Deliberately silent when the only thing deferred is stock. That one has an
    answer already -- the inventory result -- and promising to chase it is a
    grounding violation by design.
    """

    body = text.rstrip()
    if not body or _COMMITMENT_RE.search(body):
        return text
    deferral = _DEFERRAL_RE.search(body)
    if not deferral:
        return text

    start, end = _sentence_bounds(body, deferral.start())
    sentence = body[start:end]
    for pattern, english, arabic in _DEFERRED_SUBJECTS:
        if not pattern.search(sentence):
            continue
        if is_arabic_customer_language(language):
            commitment = f"سأؤكد {arabic} مع فريقنا وأعود إليك."
        else:
            commitment = f"I'll confirm {english} with our team and come back to you."
        # Straight after the deferral, not at the end of the reply. A promise
        # that arrives two questions later reads as an afterthought, and the
        # customer's eye stops at the first question anyway.
        return f"{body[:end].rstrip()} {commitment}{body[end:]}"
    return text


def _sentence_bounds(text: str, index: int) -> tuple[int, int]:
    """The sentence containing `index`, as offsets into `text`."""

    cursor = 0
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        start = text.index(sentence, cursor) if sentence else cursor
        end = start + len(sentence)
        if start <= index <= end:
            return start, end
        cursor = end
    return 0, len(text)


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
