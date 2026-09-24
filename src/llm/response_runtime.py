"""Response transport types and reply construction helpers."""

from __future__ import annotations

import inspect
import re
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from src.dialogue.order_state import QuoteConsent
from src.llm.response_policy import (
    AskKind,
    RenderedReply,
    ReplyGuardFlag,
    ReplyPolicyState,
)
from src.services.runtime_execution_evidence import RuntimeToolTrace

if TYPE_CHECKING:
    from src.llm.repair_judge import RepairJudgeTrace


@dataclass
class LLMResponse:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    cost: float | None
    model: str
    usage_provenance: Literal["provider_reported", "deterministic_static"] = (
        "provider_reported"
    )
    text_provenance: Literal[
        "model", "model_repaired", "deterministic_replacement", "deterministic_static"
    ] = "model"
    deferred_product_media: tuple[ProductMediaPayload, ...] = ()
    tool_traces: tuple[RuntimeToolTrace, ...] = ()
    repair_flags: tuple[ReplyGuardFlag, ...] = ()
    repair_policy_state: ReplyPolicyState | None = None
    repair_trace: RepairJudgeTrace | None = None
    emitted_asks: frozenset[AskKind] = frozenset()


@dataclass(frozen=True)
class CustomerFactsRun:
    context_text: str | None = None
    past_order_response: str | None = None


@asynccontextmanager
async def _customer_facts_write_scope(db: Any) -> AsyncIterator[None]:
    """Isolate optional memory writes so failures do not poison legacy handling."""

    begin_nested = getattr(db, "begin_nested", None)
    if not callable(begin_nested):
        yield
        return

    transaction = begin_nested()
    # SQLAlchemy AsyncSessionTransaction is both awaitable and an async context
    # manager. Enter it before considering coroutine-only test doubles.
    if hasattr(transaction, "__aenter__") and hasattr(transaction, "__aexit__"):
        async with transaction:
            yield
        return

    if inspect.isawaitable(transaction):
        close = getattr(transaction, "close", None)
        if callable(close):
            close()
        yield
        return

    yield


@dataclass(frozen=True)
class ProductMediaPayload:
    url: str
    caption: str
    product_key: str
    zoho_item_id: str | None = None
    reference_tokens: tuple[str, ...] = ()
    # Inbound message id of an explicit "send it again" turn; None for the
    # conversation's first send of this product image.
    resend_turn_id: str | None = None


def dedupe_product_media(
    items: Iterable[ProductMediaPayload],
) -> tuple[ProductMediaPayload, ...]:
    """One image per product per turn, first occurrence kept, order preserved.

    Two searches in one turn can queue the same row twice (replay 2026-09-23,
    scenario C turn 1); the customer should not receive the same picture twice.
    """
    seen: set[str] = set()
    unique: list[ProductMediaPayload] = []
    for item in items:
        key = str(item.product_key or item.url).strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)


def _response_from_rendered_reply(
    rendered: RenderedReply,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    cost: float | None,
    model: str,
    usage_provenance: Literal["provider_reported", "deterministic_static"],
    deferred_product_media: tuple[ProductMediaPayload, ...] = (),
    tool_traces: tuple[RuntimeToolTrace, ...] = (),
) -> LLMResponse:
    """Build the transport response only from text that passed the policy."""

    return LLMResponse(
        text=rendered.text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        model=model,
        usage_provenance=usage_provenance,
        text_provenance=rendered.provenance,
        deferred_product_media=deferred_product_media,
        tool_traces=tool_traces,
        repair_flags=rendered.flags,
        repair_policy_state=rendered.policy_state,
        emitted_asks=rendered.emitted_asks,
    )


_PRODUCT_REFERENCE_VARIANT_WORDS = frozenset(
    {
        "beige",
        "black",
        "blue",
        "brown",
        "green",
        "grey",
        "gray",
        "new",
        "orange",
        "red",
        "walnut",
        "white",
        "yellow",
    }
)


_PRODUCT_REFERENCE_NUMBER_WORDS = {
    "one": "1",
    "single": "1",
    "two": "2",
    "double": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "twelve": "12",
}
_PRODUCT_REFERENCE_STOP_WORDS = frozenset(
    {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
)
_REPLY_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CAPTION_PRICE_RE = re.compile(r"[—–-]\s*(\d[\d,]*(?:\.\d+)?)\s*[A-Za-z]{3}\s*$")

ProductMediaReferenceStrength = Literal["full", "model"]


def _normalized_product_reference(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _has_digit(word: str) -> bool:
    return any(char.isdigit() for char in word)


def _product_model_reference(raw_reference: str) -> tuple[str, ...]:
    """Return the stable model reference of a catalog name, e.g. ``novo 2400``.

    The model code is the trailing run of upper-case tokens of ``name_en``
    ("4 Person Face to Face Table SKYLAND NOVO 2400" -> "SKYLAND NOVO 2400"),
    cut to the series word before the first digit-bearing token plus the rest
    of the code ("novo 2400", "luma 9719 4", "ch 145 m"). Colour/variant words
    are transparent. Names without such a code have no model reference.
    """

    run: list[str] = []
    for token in reversed(raw_reference.split()):
        normalized = _normalized_product_reference(token)
        if not normalized:
            continue
        if normalized in _PRODUCT_REFERENCE_VARIANT_WORDS:
            continue
        if any(char.islower() for char in token):
            break
        run[:0] = normalized.split()

    for index, word in enumerate(run):
        if _has_digit(word):
            if index == 0 or _has_digit(run[index - 1]):
                return ()
            return tuple(run[index - 1 :])
    return ()


# Catalog names carry English colour words while an Arabic reply names the
# colour in Arabic, so both are folded onto one English colour before a reply
# is compared with a catalog name. Masculine, feminine and plural forms are
# listed; the article and attached prepositions are stripped first.
_ARABIC_COLOUR_WORDS = {
    "أسود": "black",
    "اسود": "black",
    "سوداء": "black",
    "سود": "black",
    "أبيض": "white",
    "ابيض": "white",
    "بيضاء": "white",
    "بيض": "white",
    "بني": "brown",
    "بنية": "brown",
    "بنيه": "brown",
    "رمادي": "grey",
    "رمادية": "grey",
    "رماديه": "grey",
    "أزرق": "blue",
    "ازرق": "blue",
    "زرقاء": "blue",
    "أحمر": "red",
    "احمر": "red",
    "حمراء": "red",
    "أخضر": "green",
    "اخضر": "green",
    "خضراء": "green",
    "أصفر": "yellow",
    "اصفر": "yellow",
    "صفراء": "yellow",
    "برتقالي": "orange",
    "برتقالية": "orange",
    "بيج": "beige",
    "جوزي": "walnut",
    "الجوز": "walnut",
}
_COLOUR_WORD_ALIASES = {"gray": "grey"}
_ARABIC_ATTACHED_PREFIXES = ("وبال", "بال", "وال", "لل", "ال", "و", "ب")


def _canonical_colour_word(word: str) -> str | None:
    if word in _COLOUR_WORD_ALIASES:
        return _COLOUR_WORD_ALIASES[word]
    if word in _ARABIC_COLOUR_WORDS:
        return _ARABIC_COLOUR_WORDS[word]
    for prefix in _ARABIC_ATTACHED_PREFIXES:
        if word.startswith(prefix) and word[len(prefix) :] in _ARABIC_COLOUR_WORDS:
            return _ARABIC_COLOUR_WORDS[word[len(prefix) :]]
    return None


_COLOUR_WORDS = frozenset(
    {
        "beige",
        "black",
        "blue",
        "brown",
        "green",
        "grey",
        "orange",
        "red",
        "walnut",
        "white",
        "yellow",
    }
)


def _colours(words: Iterable[str]) -> set[str]:
    return {
        colour
        for word in words
        if (colour := _canonical_colour_word(word) or word) in _COLOUR_WORDS
    }


def _lines_mentioning(response_text: str, words: Sequence[str]) -> list[str]:
    """Reply lines naming every one of `words`: the bullet a product sits in."""

    return [
        line
        for line in response_text.splitlines()
        if all(word in _product_reference_words(line) for word in words)
    ]


def _names_another_colour(
    reference: str, reference_words: Sequence[str], response_text: str
) -> bool:
    reference_colours = _colours(reference.split())
    if not reference_colours:
        return False
    stated_colours: set[str] = set()
    for line in _lines_mentioning(response_text, reference_words):
        stated_colours |= _colours(_product_reference_words(line))
    return bool(stated_colours) and not stated_colours & reference_colours


def _product_reference_words(value: str) -> list[str]:
    return [
        _canonical_colour_word(word) or _PRODUCT_REFERENCE_NUMBER_WORDS.get(word, word)
        for word in _normalized_product_reference(value).split()
    ]


def _product_media_reference_strength(
    item: ProductMediaPayload,
    response_text: str,
) -> ProductMediaReferenceStrength | None:
    normalized_response = _normalized_product_reference(response_text)
    response_words = set(normalized_response.split())
    padded_response = f" {normalized_response} "
    model_match = False
    for raw_reference in item.reference_tokens:
        reference = _normalized_product_reference(raw_reference)
        if not reference:
            continue
        if reference in normalized_response:
            return "full"

        reference_words = [
            word
            for word in reference.split()
            if word not in _PRODUCT_REFERENCE_VARIANT_WORDS
        ]
        if (
            len(reference_words) >= 2
            and any(_has_digit(word) for word in reference_words)
            and all(word in response_words for word in reference_words)
        ):
            if _names_another_colour(reference, reference_words, response_text):
                # "CH 490 V" named as brown is not the black sibling; leave it
                # to the sibling rules instead of calling it a full match.
                model_match = True
                continue
            return "full"

        model_reference = _product_model_reference(raw_reference)
        if model_reference and f" {' '.join(model_reference)} " in padded_response:
            model_match = True

    return "model" if model_match else None


def _product_media_is_referenced(
    item: ProductMediaPayload,
    response_text: str,
) -> bool:
    if not item.reference_tokens:
        return True
    return _product_media_reference_strength(item, response_text) is not None


def _product_media_model_key(item: ProductMediaPayload) -> tuple[str, ...]:
    for raw_reference in item.reference_tokens:
        model_reference = _product_model_reference(raw_reference)
        if model_reference:
            return model_reference
    return ()


def _product_media_caption_price(item: ProductMediaPayload) -> float | None:
    match = _CAPTION_PRICE_RE.search(item.caption)
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _reply_numbers(response_text: str) -> set[float]:
    numbers: set[float] = set()
    for raw in _REPLY_NUMBER_RE.findall(response_text):
        try:
            numbers.add(round(float(raw.replace(",", "")), 2))
        except ValueError:
            continue
    return numbers


def _product_media_descriptor_score(
    item: ProductMediaPayload,
    model_key: tuple[str, ...],
    response_words: set[str],
) -> int:
    name = item.reference_tokens[0] if item.reference_tokens else ""
    descriptors = {
        word
        for word in _product_reference_words(name)
        if word not in model_key and word not in _PRODUCT_REFERENCE_STOP_WORDS
    }
    return len(descriptors & response_words)


def _disambiguate_model_siblings(
    candidates: list[ProductMediaPayload],
    *,
    model_key: tuple[str, ...],
    has_full_sibling: bool,
    response_text: str,
    full_sibling_prices: frozenset[float] = frozenset(),
) -> list[ProductMediaPayload]:
    # A price shared with a sibling the reply names in full is that sibling's
    # price, not evidence for this one.
    reply_numbers = _reply_numbers(response_text) - full_sibling_prices
    priced = [
        item
        for item in candidates
        if (price := _product_media_caption_price(item)) is not None
        and round(price, 2) in reply_numbers
    ]
    response_words = set(_product_reference_words(response_text))
    if priced:
        if len(priced) == 1:
            return priced
        # Read the descriptors from the bullet that names this model, so a
        # colour belonging to another product in the reply does not count.
        model_lines = _lines_mentioning(response_text, model_key)
        if model_lines:
            response_words = {
                word for line in model_lines for word in _product_reference_words(line)
            }
        # Colour siblings often share a price ("CH 490 V" black and brown both
        # AED 909); the price then says nothing, and the reply's colour decides.
        scored_priced = [
            (_product_media_descriptor_score(item, model_key, response_words), item)
            for item in priced
        ]
        best_priced = max(score for score, _item in scored_priced)
        if best_priced == 0:
            return priced
        return [item for score, item in scored_priced if score == best_priced]
    if has_full_sibling:
        # The model code in the reply is already explained by a sibling named
        # in full; a bare code is not evidence for the other siblings.
        return []

    scored = [
        (_product_media_descriptor_score(item, model_key, response_words), item)
        for item in candidates
    ]
    best = max(score for score, _item in scored)
    if best == 0:
        # Nothing in the reply tells the siblings apart: keep the
        # highest-ranked search result rather than every sibling.
        return [candidates[0]]
    return [item for score, item in scored if score == best]


def _referenced_product_media(
    items: list[ProductMediaPayload] | tuple[ProductMediaPayload, ...],
    response_text: str,
) -> tuple[ProductMediaPayload, ...]:
    """Keep pending product media the final reply actually offers.

    A reply may name a product by its full catalog name or only by its stable
    model reference ("SKYLAND NOVO 2400"). Several catalog products can share
    one model code (a workstation, a meeting table and a liner table all named
    NOVO 2400), so items matched only by the model reference are kept only
    when they are the sole pending item with that code, or when the reply's
    prices or descriptive words single them out among the siblings.
    """

    strengths: list[ProductMediaReferenceStrength | None] = [
        "full"
        if not item.reference_tokens
        else _product_media_reference_strength(item, response_text)
        for item in items
    ]
    model_keys = [_product_media_model_key(item) for item in items]
    sibling_counts: dict[tuple[str, ...], int] = {}
    for key in model_keys:
        if key:
            sibling_counts[key] = sibling_counts.get(key, 0) + 1

    kept_model_only: set[int] = set()
    groups: dict[tuple[str, ...], list[int]] = {}
    for index, strength in enumerate(strengths):
        if strength != "model":
            continue
        key = model_keys[index]
        if sibling_counts.get(key, 0) <= 1:
            kept_model_only.add(index)
        else:
            groups.setdefault(key, []).append(index)

    for key, indexes in groups.items():
        full_siblings = [
            items[index]
            for index, other_key in enumerate(model_keys)
            if other_key == key and strengths[index] == "full"
        ]
        chosen = _disambiguate_model_siblings(
            [items[index] for index in indexes],
            model_key=key,
            has_full_sibling=bool(full_siblings),
            response_text=response_text,
            full_sibling_prices=frozenset(
                round(price, 2)
                for item in full_siblings
                if (price := _product_media_caption_price(item)) is not None
            ),
        )
        chosen_ids = {id(item) for item in chosen}
        kept_model_only.update(
            index for index in indexes if id(items[index]) in chosen_ids
        )

    return tuple(
        item
        for index, item in enumerate(items)
        if strengths[index] == "full" or index in kept_model_only
    )


@dataclass(frozen=True)
class ExactQuoteCandidate:
    quantity: int
    item_candidate: str
    sku: str | None


@dataclass(frozen=True)
class PurchaseSelectionItem:
    quantity: int
    item_candidate: str
    sku: str
    stated_unit_price: float | None = None
    stated_currency: str | None = None


@dataclass(frozen=True)
class PurchaseSelection:
    items: tuple[PurchaseSelectionItem, ...]
    order_runtime_trace: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OrderRuntimePurchaseSelection:
    selection: PurchaseSelection | None
    block_legacy: bool = False


@dataclass(frozen=True)
class ResolvedPurchaseSelectionItem:
    requested: PurchaseSelectionItem
    product: Any
    availability: int | None
    unit_price: float | None
    currency: str
    availability_source: Literal["zoho", "catalog", "unconfirmed"]
    source_caption: str | None = None


@dataclass(frozen=True)
class PurchaseSelectionResolution:
    resolved: tuple[ResolvedPurchaseSelectionItem, ...]
    unresolved: tuple[PurchaseSelectionItem, ...]


@dataclass(frozen=True)
class SalesOpportunityRequest:
    amount: float | None
    currency: str | None
    quote_consent: QuoteConsent
    decision_horizon_days: int | None = None
    decision_horizon_hours: int | None = None


@dataclass(frozen=True)
class SalesOpportunityWriteResult:
    verified: bool
    deal_id: str | None = None
    stage: str | None = None
    reused: bool = False
    error: str | None = None


@dataclass(frozen=True)
class PendingReferenceRoute:
    selection: PurchaseSelection | None = None
    clear_pending_reference_quantity: bool = False
    clear_pending_question_frame: bool = False


@dataclass(frozen=True)
class CommercialPriceDecision:
    unit_price: float
    currency: str
    source: Literal["catalog", "zoho", "unavailable"]
    catalog_price: float | None
    zoho_rate: float | None
