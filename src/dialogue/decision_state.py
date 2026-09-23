"""Closed customer decisions, rendered as authoritative turn state.

tj-uz6j.3 / tj-uz6j.7. The model-first turn sees the customer's recorded
selection and quotation consent only as "untrusted historical workflow data",
and nothing records what the assistant's own last question proposed. A model
that follows its stage rules and search contracts literally therefore re-lists
alternatives after the customer has chosen, re-asks priorities the choice
already answered, re-opens the variant on a quantity change, and reads a bare
"yes" as something other than the proposal it answered.

This module owns one mechanism for all of those shapes:

* the state it reads is the existing durable state -- the validated selection
  written by ``record_customer_requirements``, the canonical quote workflow and
  customer details -- plus one new slot, ``DialogueState.last_proposal``, the
  closing question of the last reply that was actually sent;
* it classifies only the *form* of the current customer message (a short
  assent or decline, a message typed in the wrong keyboard layout), never its
  subject; what the assent means is read from the recorded proposal;
* it returns directives the prompt renders as closed decisions, which switch
  the turn from options mode to proceed mode.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from src.dialogue.claim_contract import RetrievedRow
from src.dialogue.order_state import QuoteConsent, quote_workflow_from_metadata
from src.dialogue.state import (
    AssistantProposal,
    DialogueState,
    ProposalItem,
)

MAX_PROPOSAL_QUESTION_CHARS = 400
MAX_PROPOSAL_ITEMS = 6
_MAX_SHORT_REPLY_WORDS = 8

ShortReplyKind = Literal["assent", "decline"]


@dataclass(frozen=True, slots=True)
class ShortReply:
    """The form of a customer message that answers a yes/no proposal."""

    kind: ShortReplyKind
    # Nothing but the answer ("yes", "sure", "of course", "keep it").
    bare: bool
    # What follows the leading answer ("LUMA would be perfect"), if anything.
    remainder: str = ""
    # The QWERTY reading when the message was typed in another layout.
    layout_reading: str | None = None


# --- Keyboard layout ---------------------------------------------------------

# Standard Russian ЙЦУКЕН and Arabic PC layouts, key for key onto US QWERTY.
# "ыгку" is "sure" typed with the Russian layout still active.
_CYRILLIC_TO_QWERTY = dict(
    zip(
        "йцукенгшщзхъфывапролджэячсмитьбюё",
        "qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
        strict=True,
    )
)
_ARABIC_TO_QWERTY = dict(
    zip(
        "ضصثقفغعهخحجدشسيبلاتنمكطئءؤرىةوزظذ",
        "qwertyuiop[]asdfghjkl;'zxcvnm,./`",
        strict=True,
    )
)
_CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)


def _transliterate(text: str, table: Mapping[str, str]) -> str:
    return "".join(table.get(char, char) for char in text.casefold())


MAX_LAYOUT_READING_CHARS = 60


_CYRILLIC_RUN_RE = re.compile(r"[а-яё]+", re.IGNORECASE)


def keyboard_layout_reading(text: str) -> tuple[str, str] | None:
    """Return ``(layout, qwerty_reading)`` for a message typed in another layout.

    Cyrillic is read word by word, so a batch such as "ыгку" + "sure" reads as
    "sure sure": Treejar serves English and Arabic, so Cyrillic in this channel
    is far more often a layout slip than Russian. Arabic is a real customer
    language, so an all-Arabic message is offered only when its QWERTY reading
    is itself a recognised short answer.
    """

    stripped = text.strip()
    # Short messages only: the reading is quoted into a directive, and a long
    # one is a real message in its own script far more often than a slip.
    if not stripped or len(stripped) > MAX_LAYOUT_READING_CHARS:
        return None
    if _CYRILLIC_RE.search(stripped) and not _ARABIC_RE.search(stripped):
        reading = _CYRILLIC_RUN_RE.sub(
            lambda match: _transliterate(match.group(0), _CYRILLIC_TO_QWERTY),
            stripped,
        )
        return ("Russian", reading) if _LATIN_RE.search(reading) else None
    if (
        _ARABIC_RE.search(stripped)
        and not _CYRILLIC_RE.search(stripped)
        and not _LATIN_RE.search(stripped)
    ):
        reading = _transliterate(stripped.replace("لا", "b"), _ARABIC_TO_QWERTY)
        if _classify_normalized(_normalize(reading)) is not None:
            return ("Arabic", reading)
    return None


# --- Short answers -----------------------------------------------------------

_ASSENT_PHRASES = (
    "yes",
    "yeah",
    "yea",
    "yep",
    "yup",
    "ya",
    "y",
    "sure",
    "ok",
    "okay",
    "k",
    "fine",
    "alright",
    "all right",
    "of course",
    "certainly",
    "absolutely",
    "definitely",
    "indeed",
    "go ahead",
    "proceed",
    "do it",
    "do that",
    "go for it",
    "lets do it",
    "let s do it",
    "sounds good",
    "sounds great",
    "looks good",
    "perfect",
    "great",
    "good",
    "agreed",
    "agree",
    "deal",
    "correct",
    "right",
    "exactly",
    "confirmed",
    "confirm",
    "approved",
    "approve",
    "works",
    "that works",
    "why not",
    "keep it",
    "keep that",
    "keep this",
    "keep them",
    "that one",
    "this one",
    "نعم",
    "ايوه",
    "أيوه",
    "اي",
    "أكيد",
    "اكيد",
    "بالتأكيد",
    "تمام",
    "موافق",
    "موافقة",
    "حسنا",
    "حسنًا",
    "طيب",
    "ماشي",
    "تابع",
    "يلا",
)
_DECLINE_PHRASES = (
    "no",
    "nope",
    "nah",
    "not now",
    "not yet",
    "no thanks",
    "no thank you",
    "لا",
    "ليس الآن",
)
# Politeness around an answer, never an answer by itself.
_FILLER_PHRASES = (
    "please",
    "pls",
    "plz",
    "thanks",
    "thank you",
    "thx",
    "then",
    "sir",
    "madam",
    "noor",
    "من فضلك",
    "لو سمحت",
    "شكرا",
)


def _phrase_tokens(phrases: Iterable[str]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sorted(
            {tuple(_normalize(phrase).split()) for phrase in phrases},
            key=len,
            reverse=True,
        )
    )


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


# Only these may open a longer message ("yes, LUMA would be perfect"); the
# rest count only on their own, so "good morning" or "right, and delivery"
# is never read as acceptance.
_LEADING_ASSENT_PHRASES = (
    "yes",
    "yeah",
    "yep",
    "yup",
    "sure",
    "ok",
    "okay",
    "of course",
    "certainly",
    "absolutely",
    "definitely",
    "agreed",
    "نعم",
    "أكيد",
    "اكيد",
    "تمام",
    "موافق",
)

_ASSENT_TOKENS = _phrase_tokens(_ASSENT_PHRASES)
_LEADING_ASSENT_TOKENS = _phrase_tokens(_LEADING_ASSENT_PHRASES)
_DECLINE_TOKENS = _phrase_tokens(_DECLINE_PHRASES)
_FILLER_TOKENS = _phrase_tokens(_FILLER_PHRASES)


def _match_at(
    words: list[str], index: int, phrases: tuple[tuple[str, ...], ...]
) -> int:
    for phrase in phrases:
        if tuple(words[index : index + len(phrase)]) == phrase:
            return len(phrase)
    return 0


def _classify_normalized(normalized: str) -> tuple[ShortReplyKind, bool, int] | None:
    """Return ``(kind, bare, consumed_words)`` for a normalized message."""

    words = normalized.split()
    if not words:
        return None
    index = 0
    kind: ShortReplyKind | None = None
    while index < len(words):
        filler = _match_at(words, index, _FILLER_TOKENS)
        if filler:
            index += filler
            continue
        # Decline first: "no thanks" must not read as filler after "no".
        decline = _match_at(words, index, _DECLINE_TOKENS)
        assent = _match_at(words, index, _ASSENT_TOKENS)
        if decline and decline >= assent:
            if kind == "assent":
                return None
            kind = "decline"
            index += decline
            continue
        if assent:
            if kind == "decline":
                return None
            kind = "assent"
            index += assent
            continue
        break
    if kind is None:
        return None
    bare = index >= len(words)
    if bare:
        if len(words) > _MAX_SHORT_REPLY_WORDS:
            return None
        return kind, bare, index
    # A longer message is an answer only when it opens with an unambiguous one.
    start = 0
    while start < index and _match_at(words, start, _FILLER_TOKENS):
        start += _match_at(words, start, _FILLER_TOKENS)
    opener = _LEADING_ASSENT_TOKENS if kind == "assent" else _DECLINE_TOKENS
    if not _match_at(words, start, opener):
        return None
    return kind, bare, index


def classify_short_reply(text: str) -> ShortReply | None:
    """Is this message, in form, an answer to a yes/no proposal?

    Reads the form only: a leading assent or decline, optionally followed by
    more content. What it accepts is decided by the recorded proposal, never
    by the wording here.
    """

    layout = keyboard_layout_reading(text)
    candidates = [text]
    if layout is not None:
        candidates.append(layout[1])
    for index, candidate in enumerate(candidates):
        normalized = _normalize(candidate)
        classified = _classify_normalized(normalized)
        if classified is None:
            continue
        kind, bare, consumed = classified
        if not bare and ("?" in candidate or "؟" in candidate):
            # "ok, and what about delivery?" asks; it does not answer.
            return None
        remainder = " ".join(normalized.split()[consumed:]) if not bare else ""
        if remainder:
            # Keep the customer's own wording for the remainder.
            remainder = _original_remainder(candidate, consumed) or remainder
        return ShortReply(
            kind=kind,
            bare=bare,
            remainder=remainder,
            layout_reading=layout[1] if index == 1 and layout is not None else None,
        )
    return None


def _original_remainder(text: str, consumed_words: int) -> str:
    tokens = re.findall(r"\w+", unicodedata.normalize("NFKC", text))
    if consumed_words >= len(tokens):
        return ""
    # Words are counted on the normalized text; apostrophes split the same way.
    anchor = tokens[consumed_words]
    position = 0
    for token in tokens[:consumed_words]:
        position = text.find(token, position) + len(token)
    start = text.find(anchor, position)
    if start < 0:
        return ""
    return text[start:].strip(" ,.;:!-")


# --- The last proposal -------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+|\n+")
_MARKUP_CHARS = "•-*_~> \t"
_MAX_SIGN_OFF_CHARS = 80


def closing_question(reply_text: str) -> str | None:
    """The question the reply closes on, if it closes on one.

    Only the last sentence counts, or the one before a short sign-off: a
    question in the middle of a reply that goes on to other matters is not
    what a following "yes" answers.
    """

    sentences = [
        cleaned
        for raw in _SENTENCE_SPLIT_RE.split(reply_text.strip())
        if (cleaned := raw.strip(_MARKUP_CHARS))
    ]
    if not sentences:
        return None
    candidates = [sentences[-1]]
    if len(sentences) >= 2 and len(sentences[-1]) <= _MAX_SIGN_OFF_CHARS:
        candidates.append(sentences[-2])
    for sentence in candidates:
        if sentence.endswith(("?", "؟")):
            question = sentence.lstrip("0123456789. ").strip()
            return question[:MAX_PROPOSAL_QUESTION_CHARS] or None
    return None


def _reference_words(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _model_code(name: str) -> str | None:
    """``"4 Person Face to Face Table SKYLAND NOVO 2400"`` -> ``"novo 2400"``."""

    words = _reference_words(name).split()
    for index in range(len(words) - 1, 0, -1):
        if any(char.isdigit() for char in words[index]):
            start = index
            while start > 0 and any(char.isdigit() for char in words[start - 1]):
                start -= 1
            if start == 0:
                return None
            return " ".join(words[start - 1 : index + 1])
    return None


def referenced_catalog_items(
    reply_text: str,
    rows: Mapping[str, RetrievedRow],
) -> list[ProposalItem]:
    """Catalog rows this turn retrieved that the reply names.

    A row is named by its SKU, its full catalog name, or its model code
    ("SKYLAND NOVO 2400", "LUMA 9719-4"). Siblings sharing a model code are
    told apart by a price the reply states, when it states one.
    """

    padded = f" {_reference_words(reply_text)} "
    reply_numbers = {
        raw.replace(",", "") for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", reply_text)
    }
    exact: list[tuple[int, ProposalItem]] = []
    by_code: dict[str, list[tuple[int, ProposalItem]]] = {}
    for sku, row in rows.items():
        name = str(row.fields.get("name") or "").strip() or None
        price = str(row.fields.get("price") or "").strip() or None
        item = ProposalItem(sku=sku, name=name, unit_price=price)
        for reference in (sku, name or ""):
            words = _reference_words(reference)
            if words and f" {words} " in padded:
                exact.append((padded.find(f" {words} "), item))
                break
        else:
            code = _model_code(name or "")
            if code and f" {code} " in padded:
                by_code.setdefault(code, []).append((padded.find(f" {code} "), item))

    found = list(exact)
    exact_codes = {_model_code(item.name or "") for _, item in exact}
    for code, siblings in by_code.items():
        priced = [
            entry
            for entry in siblings
            if entry[1].unit_price and _price_text(entry[1].unit_price) in reply_numbers
        ]
        if priced:
            found.extend(priced)
        elif code not in exact_codes:
            found.extend(siblings)
    found.sort(key=lambda entry: entry[0])
    seen: set[str] = set()
    items: list[ProposalItem] = []
    for _position, item in found:
        if item.sku in seen:
            continue
        seen.add(item.sku)
        items.append(item)
    return items[:MAX_PROPOSAL_ITEMS]


def _series_word(name: str | None) -> str | None:
    code = _model_code(name or "")
    return code.split()[0] if code else None


def proposal_items(
    question: str,
    reply_text: str,
    rows: Mapping[str, RetrievedRow],
) -> list[ProposalItem]:
    """The rows the closing question proposes.

    Rows the question itself names win. A question that only points back
    ("Shall I carry it forward?", "these three workstations") proposes what the
    reply named, narrowed to the series the question mentions when it
    mentions one ("Shall I carry LUMA forward?").
    """

    named_in_question = referenced_catalog_items(question, rows)
    if named_in_question:
        return named_in_question
    named_in_reply = referenced_catalog_items(reply_text, rows)
    question_words = set(_reference_words(question).split())
    in_series = [
        item
        for item in named_in_reply
        if (series := _series_word(item.name)) and series in question_words
    ]
    return in_series or named_in_reply


def _price_text(value: str) -> str:
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return value
    return f"{number:g}" if number != int(number) else str(int(number))


def record_assistant_proposal(
    metadata: Mapping[str, Any] | None,
    reply_text: str,
    rows: Mapping[str, RetrievedRow] | None = None,
    *,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Return metadata with ``last_proposal`` set from the reply actually sent.

    A reply that does not close on a question clears the slot: after it, a
    "yes" no longer answers the older question.
    """

    state = DialogueState.load(dict(metadata or {}))
    question = closing_question(reply_text)
    proposal: AssistantProposal | None = None
    if question:
        # A follow-up question often names items from an earlier turn ("these
        # three workstations") without searching again; the rows the previous
        # proposal carried stay resolvable, and this turn's rows win.
        known_rows: dict[str, RetrievedRow] = {}
        if state.last_proposal is not None:
            for item in state.last_proposal.items:
                fields = {
                    key: value
                    for key, value in (("name", item.name), ("price", item.unit_price))
                    if value
                }
                known_rows[item.sku] = RetrievedRow(sku=item.sku, fields=fields)
        known_rows.update(rows or {})
        items = proposal_items(question, reply_text, known_rows)
        proposal = AssistantProposal(
            question=question,
            items=items,
            asked_at=(now or datetime.datetime.now(datetime.UTC)).isoformat(),
        )
    if proposal is None and state.last_proposal is None:
        return dict(metadata or {})
    state = state.model_copy(update={"last_proposal": proposal}, deep=True)
    return state.to_metadata(dict(metadata or {}))


def clear_assistant_proposal(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop the recorded proposal, e.g. when its reply was never delivered."""

    state = DialogueState.load(dict(metadata or {}))
    if state.last_proposal is None:
        return dict(metadata or {})
    state = state.model_copy(update={"last_proposal": None}, deep=True)
    return state.to_metadata(dict(metadata or {}))


# --- Directives --------------------------------------------------------------


def _quoted(value: str) -> str:
    """One line, no quote marks: a value rendered inside a directive stays data."""

    return " ".join(re.sub(r"[\"`<>\[\]{}]", " ", value).split())


def _item_label(
    item: Mapping[str, Any] | ProposalItem, names: Mapping[str, str]
) -> str:
    if isinstance(item, ProposalItem):
        sku, quantity, name = item.sku, None, item.name
    else:
        sku = str(item.get("sku") or "")
        raw_quantity = item.get("quantity")
        quantity = raw_quantity if isinstance(raw_quantity, int) else None
        name = str(item.get("name") or "") or names.get(sku)
    label = f"{name} (SKU {sku})" if name and name != sku else f"SKU {sku}"
    return f"{quantity} x {label}" if quantity else label


def _missing_quote_details(
    metadata: Mapping[str, Any], state: DialogueState
) -> list[str]:
    details = metadata.get("quote_customer_details")
    details = details if isinstance(details, Mapping) else {}

    def known(*keys: str) -> bool:
        return any(str(details.get(key) or "").strip() for key in keys)

    missing: list[str] = []
    if not (known("name") or state.slots.customer_name):
        missing.append("customer name")
    if not (
        known("company", "customer_type")
        or state.slots.company
        or state.slots.customer_type
    ):
        missing.append("company name or individual status")
    if not (known("address") or state.slots.delivery_address):
        missing.append("specific delivery address")
    if not known("email"):
        missing.append("customer email")
    return missing


def decision_state_directives(
    conversation: Any,
    *,
    customer_text: str,
    missing_quote_details: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Directives the durable decision state earns on this turn.

    Deterministic over typed state and the form of the current message. The
    selection and consent they state were written by validated tools, so they
    are presented as settled facts, not as untrusted history.

    `missing_quote_details` is the quotation gate's own list of missing
    required details. The runtime passes it so the details the model asks for
    are exactly the ones `create_quotation` will refuse without; the local
    reading is only a fallback for callers without the gate.
    """

    metadata = getattr(conversation, "metadata_", None)
    metadata = metadata if isinstance(metadata, Mapping) else {}
    state = DialogueState.from_conversation(conversation)
    workflow = quote_workflow_from_metadata(metadata)
    proposal = state.last_proposal
    names = (
        {item.sku: item.name for item in proposal.items if item.name}
        if proposal
        else {}
    )
    directives: list[str] = []

    selected = [
        item
        for item in state.slots.selected_items
        if isinstance(item, Mapping) and str(item.get("sku") or "").strip()
    ]
    if selected and not state.slots.quote_sent:
        labels = "; ".join(_item_label(item, names) for item in selected)
        if workflow.consent is QuoteConsent.GRANTED:
            missing = (
                list(missing_quote_details)
                if missing_quote_details is not None
                else _missing_quote_details(metadata, state)
            )
            next_step = (
                "the quotation is agreed: ask for all of the missing details "
                "together in one sentence -- "
                + "; ".join(missing)
                + " -- then call create_quotation"
                if missing
                else "the quotation is agreed and its details are known: confirm "
                "stock with get_stock if needed and call create_quotation now"
            )
        elif workflow.consent in {QuoteConsent.DECLINED, QuoteConsent.DEFERRED}:
            next_step = (
                "the customer has put the quotation on hold: answer what they ask "
                "about the chosen items and agree the next step, without offering "
                "alternatives"
            )
        else:
            next_step = "offer to prepare the quotation for exactly this selection"
        directives.append(
            "CLOSED DECISION -- the customer has chosen: "
            f"{labels}. The comparison is over. Do not present, price or compare "
            "the other options again, and do not re-ask a preference (priority, "
            "layout, style, size) that this choice already settled, unless the "
            "customer asks for alternatives, names a different product, or "
            "rejects the choice. Stage rules and search results that say to "
            "present options do not reopen it: use a search only to confirm "
            "facts about the chosen items. Restate price or stock only when the "
            "customer asks, when a figure changed, or in the quotation summary. "
            f"Next step: {next_step}."
        )
        if len(selected) == 1:
            sku = str(selected[0].get("sku"))
            directives.append(
                "A quantity the customer now gives without naming a different "
                "product or variant applies to the chosen line: call "
                f"record_customer_requirements with SKU {sku} and the new "
                "quantity, confirm it, and continue. Do not ask which variant "
                "or layout they mean."
            )
        else:
            directives.append(
                "If the customer gives a bare quantity that could belong to more "
                "than one chosen line, ask which line it is for -- that is the "
                "only question it earns."
            )
    elif workflow.consent is QuoteConsent.GRANTED and not state.slots.quote_sent:
        directives.append(
            "The customer has already agreed to a quotation. Do not ask again "
            "whether they want one; settle the items and quantities and collect "
            "only the missing details."
        )

    reply = classify_short_reply(customer_text)
    layout = keyboard_layout_reading(customer_text)
    if layout is not None and (reply is None or reply.layout_reading is not None):
        layout_name, reading = layout
        certainty = "was typed" if reply is not None else "may have been typed"
        closing = (
            "Read it as that."
            if reply is not None
            else "If that reading makes sense in context, answer it."
        )
        directives.append(
            f"The current message {certainty} with the {layout_name} keyboard "
            "layout still active; on an English keyboard it reads "
            f'"{_quoted(reading)}". {closing}'
        )

    if reply is not None and proposal is not None:
        item_text = (
            " Items your message named: "
            + "; ".join(_item_label(item, {}) for item in proposal.items)
            + "."
            if proposal.items
            else ""
        )
        if reply.kind == "assent":
            # The remainder is the customer's own text; it stays in the user
            # turn and is never copied into a directive.
            refinement = (
                " The rest of the current message adjusts that proposal; apply "
                "it to the same items unless it names others."
                if reply.remainder
                else ""
            )
            directives.append(
                "The customer's current message is a yes to your last question: "
                f'"{_quoted(proposal.question)}".{item_text} It accepts exactly what that '
                "question proposed -- the same item, variant and quantity you "
                f"put to them, nothing else.{refinement} Act on it in this reply: "
                "a quotation offer means record consent with record_customer_intent "
                "and continue the quotation; a proposed item, quantity or option "
                "means record exactly that with record_customer_requirements. Do "
                "not ask them to confirm it again, do not reinterpret it as a "
                "different quantity or variant, and do not list the options again."
            )
        else:
            directives.append(
                "The customer's current message is a no to your last question: "
                f'"{_quoted(proposal.question)}". Do not repeat that proposal; keep what '
                "is already decided and ask what they would prefer instead."
            )
    return tuple(directives)


def closed_selection_skus(conversation: Any) -> tuple[str, ...]:
    """SKUs of the customer's recorded, not yet quoted selection.

    For tool contracts that must switch from options mode to proceed mode
    once the customer has chosen (search_products, get_stock).
    """

    state = DialogueState.from_conversation(conversation)
    if state.slots.quote_sent:
        return ()
    return tuple(
        str(item.get("sku")).strip()
        for item in state.slots.selected_items
        if isinstance(item, Mapping) and str(item.get("sku") or "").strip()
    )
