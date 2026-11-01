from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from src.dialogue.catalog_refs import fold_catalog_homoglyphs
from src.dialogue.count_words import (
    COUNT_PATTERN,
    count_value,
    head_count,
    parse_count_word,
    strip_head_counts,
)
from src.llm.catalog_families import (
    CATALOG_PRODUCT_FAMILIES,
    catalog_text_families,
    contains_catalog_term,
)
from src.llm.money import BUDGET_AED_CURRENCY_PATTERN

# "generic" is a needs-only request ("office furniture for four people"): it
# names no product, brand, model or finish, so there is no exact item whose
# absence could be confirmed, and the results are options for the need.
ProductMatch = Literal["exact", "generic", "nearby", "missing"]

_TOKEN_RE = re.compile(r"[a-z0-9']+")

_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "across",
        "all",
        "an",
        "and",
        "are",
        "at",
        "can",
        "do",
        "for",
        "have",
        "how",
        "i",
        "in",
        "is",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "please",
        "tell",
        "the",
        "their",
        "there",
        "they",
        "to",
        "we",
        "what",
        "when",
        "where",
        "with",
        "you",
        "your",
    }
)
_LOCATION_TERMS = (
    "abu dhabi",
    "dubai",
    "dubai marina",
    "sharjah",
    "ajman",
    "uae",
    "ras al khaimah",
    "fujairah",
)
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "delivery": (
        "delivery",
        "deliver",
        "delivered",
        "shipping",
        "ship",
        "lead time",
        "timeline",
        "deadline",
        "timeframe",
        "توصيل",
        "تسليم",
    ),
    "installation": (
        "installation",
        "install",
        "installed",
        "setup",
        "assembly",
        "logistics",
        "تركيب",
    ),
    "warranty": ("warranty", "guarantee", "guaranty", "ضمان"),
    "returns": (
        "return",
        "refund",
        "exchange",
        "cancel",
        "returns",
        "refunds",
        "إرجاع",
        "استرجاع",
    ),
    "payment": (
        "payment",
        "pay",
        "terms",
        "deferred",
        "credit",
        "invoice",
        "installment",
        "net 30",
        "net 60",
        "دفع",
        "السداد",
        "أقساط",
    ),
    # "office" is in almost every message an office-furniture customer sends,
    # and "location" is usually a delivery location. Both used to route a
    # customer to the showroom address: on 2026-08-09 "for a small office, 4
    # people" and "Leila, im the office manager" were both answered with a
    # Google Maps link. The topic now needs a term that is actually about
    # visiting us.
    "showroom": (
        "showroom",
        "branch",
        "store",
        "your office",
        "visit you",
        "come and see",
        "come see",
        "where are you located",
        "your location",
        "معرض",
    ),
    "company": (
        "company",
        "about treejar",
        "who are you",
        "service area",
        "capabilities",
    ),
}
_NEARBY_EQUIVALENTS = {
    "accessory": {"cabinet", "pedestal", "storage"},
    "accessories": {"cabinet", "pedestal", "storage"},
    "pod": {"booth"},
    "pods": {"booth", "booths"},
    "booth": {"pod", "pods"},
    "booths": {"pod", "pods"},
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(_normalize(text))
        if token not in _STOPWORDS and len(token) > 1
    }


def _query_topics(query: str) -> tuple[str, ...]:
    normalized = _normalize(query)
    topics = [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return tuple(topics)


def _entry_topics(entry_text: str) -> set[str]:
    normalized = _normalize(entry_text)
    return {
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


_WORKSTATION_MATCH_TERMS = frozenset(
    {"desk", "desks", "workstation", "workstations", "bench", "benches"}
)
_PRIVACY_MATCH_TERMS = frozenset(
    {
        "private",
        "privacy",
        "panel",
        "panels",
        "divider",
        "dividers",
        "screen",
        "screens",
        "enclosed",
    }
)
_STRUCTURED_ATTRIBUTE_VALUE_RE = re.compile(
    r"\b(?:brand|family|line|model|series|finish|colou?r)\s*[:=-]?\s*"
    r"(?P<after>[a-z][a-z0-9-]{1,30})\b|"
    r"\b(?P<before>[a-z][a-z0-9-]{1,30})\s+(?:finish|colou?r)\b|"
    r"\bin\s+(?P<modifier>[a-z][a-z0-9-]{1,30})\b",
    re.IGNORECASE,
)
_STRUCTURED_MODEL_IDENTIFIER_RE = re.compile(
    r"(?<![a-z0-9])(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)"
    r"[a-z0-9]+(?:-[a-z0-9]+)+(?![a-z0-9])",
    re.IGNORECASE,
)
_STRUCTURED_UPPER_IDENTIFIER_RE = re.compile(
    r"(?<![a-z0-9])[A-Z][A-Z0-9]{2,}(?![a-z0-9-])"
)
_STRUCTURED_DISCRIMINATOR_EXCLUSIONS = frozenset(
    {"aed", "dhs", "sku", "stock", "privacy", "private", "panel", "panels"}
)


def _capacity_value(text: str) -> int | None:
    return head_count(_normalize(text))


def _is_plain_location_modifier(query: str, match: re.Match[str]) -> bool:
    if not match.group("modifier"):
        return False
    modifier = query[match.start("modifier") :]
    for place in sorted(_LOCATION_TERMS, key=len, reverse=True):
        location = re.match(
            r"\s+".join(re.escape(part) for part in place.split()) + r"(?![\w-])",
            modifier,
            re.IGNORECASE,
        )
        if location is not None:
            # A city name can also be an explicitly named finish/brand. Use
            # the longest known place so `Dubai Marina color` cannot fall
            # back to a shorter, apparently unqualified `Dubai` modifier.
            return (
                re.match(
                    r"\s+(?:finish|colou?r|brand|family|line|model|series)\b",
                    modifier[location.end() :],
                    re.IGNORECASE,
                )
                is None
            )
    return False


def _explicit_structured_discriminators(query: str) -> set[str]:
    raw_values = {
        value.casefold()
        for match in _STRUCTURED_ATTRIBUTE_VALUE_RE.finditer(query)
        if (value := next((group for group in match.groups() if group), None))
        and not _is_plain_location_modifier(query, match)
    }
    values = {token for raw_value in raw_values for token in _tokenize(raw_value)}
    return values - _STRUCTURED_DISCRIMINATOR_EXCLUSIONS


def _explicit_structured_identifiers(text: str) -> set[str]:
    identifiers = {
        match.group(0).casefold()
        for match in _STRUCTURED_MODEL_IDENTIFIER_RE.finditer(text)
    }
    identifiers.update(
        match.group(0).casefold()
        for match in _STRUCTURED_UPPER_IDENTIFIER_RE.finditer(text)
    )
    return identifiers - _STRUCTURED_DISCRIMINATOR_EXCLUSIONS


def _matches_structured_workstation_constraints(
    query: str,
    candidate: str,
) -> bool:
    query_tokens = _tokenize(query)
    if not (
        query_tokens & _WORKSTATION_MATCH_TERMS and query_tokens & _PRIVACY_MATCH_TERMS
    ):
        return False
    requested_capacity = _capacity_value(query)
    if requested_capacity is None:
        return False

    candidate_tokens = _tokenize(candidate)
    discriminators = _explicit_structured_discriminators(query)
    identifiers = _explicit_structured_identifiers(query)
    return bool(
        candidate_tokens & _WORKSTATION_MATCH_TERMS
        and candidate_tokens & _PRIVACY_MATCH_TERMS
        and _capacity_value(candidate) == requested_capacity
        and discriminators.issubset(candidate_tokens)
        and identifiers.issubset(_explicit_structured_identifiers(candidate))
    )


# Words a search query carries about the request itself rather than about the
# product. A model-written query such as "Compare SKYLAND LUMA 9719-4 and NOVO
# 2400 setups for privacy and current price" must not need a catalog row that
# literally says "compare", "current" or "price" before it counts as the item.
_PRODUCT_MATCH_FILLER_TERMS = frozenset(
    {
        "affordable",
        "alternative",
        "alternatives",
        "around",
        "availability",
        "available",
        "below",
        "best",
        "between",
        "both",
        "budget",
        "catalog",
        "catalogue",
        "cheap",
        "cheaper",
        "check",
        "closest",
        "compare",
        "comparing",
        "comparison",
        "configuration",
        "confirm",
        "cost",
        "current",
        "currently",
        "detail",
        "details",
        "difference",
        "differences",
        "each",
        "exact",
        "exactly",
        "find",
        "have",
        "info",
        "information",
        "item",
        "items",
        "latest",
        "list",
        "looking",
        "model",
        "need",
        "office",
        "option",
        "options",
        "price",
        "prices",
        "pricing",
        "product",
        "products",
        "recommend",
        "recommendation",
        "recommendations",
        "setup",
        "setups",
        "show",
        "sku",
        "stock",
        "suggest",
        "suitable",
        "treejar",
        "under",
        "versus",
        "vs",
        "want",
        "what",
        "which",
        "within",
    }
)
# Words that describe a customer's need rather than a specific product: a
# request made only of these (plus filler and seat counts) names no exact item.
_PRODUCT_NEED_TERMS = frozenset(
    {
        "abu",
        "ajman",
        "arrangement",
        "comfortable",
        "dedicated",
        "dhabi",
        "divider",
        "dividers",
        "dubai",
        "employee",
        "employees",
        "enclosed",
        "ergonomic",
        "fit",
        "furnish",
        "furnishing",
        "furniture",
        "individual",
        "mesh",
        "modern",
        "new",
        "panel",
        "panels",
        "people",
        "person",
        "persons",
        "privacy",
        "private",
        "screen",
        "screens",
        "seating",
        "sharjah",
        "solution",
        "solutions",
        "space",
        "staff",
        "team",
        "uae",
        "work",
        "workspace",
        "workspaces",
    }
)
# Finish and colour words. A named model is only the requested item when every
# finish the customer named is on that row.
_PRODUCT_FINISH_TERMS = frozenset(
    {
        "anthracite",
        "ash",
        "beige",
        "black",
        "blue",
        "brown",
        "cherry",
        "chrome",
        "cream",
        "gray",
        "green",
        "grey",
        "maple",
        "oak",
        "orange",
        "pink",
        "red",
        "silver",
        "sonoma",
        "teak",
        "walnut",
        "wenge",
        "white",
        "yellow",
    }
)
_COMPOUND_FINISH_PATTERN = (
    rf"(?:{'|'.join(sorted(_PRODUCT_FINISH_TERMS))})\s+"
    r"[a-z][a-z0-9-]+(?:\s+finish)?"
)
_NAMED_FINISH_LIST_RE = re.compile(
    rf"(?P<finishes>{_COMPOUND_FINISH_PATTERN}"
    rf"(?:\s+and\s+{_COMPOUND_FINISH_PATTERN})+)\b",
    re.IGNORECASE,
)
_VARIANT_QUERY_FILLER_TERMS = frozenset(
    {"photo", "photos", "picture", "pictures", "image", "images", "finish", "finishes"}
)
_MODEL_CODE_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_DIMENSION_CODE_RE = re.compile(r"^\d+(?:[x*]\d+)+$")
_EXPLICIT_DIMENSION_RE = re.compile(r"\d+(?:\s*[x*]\s*\d+)+")
_MODEL_CODE_WORD_EXCLUSIONS = frozenset(
    {"person", "people", "seat", "seats", "seater", "pcs", "pc", "mm", "cm", "aed"}
)
_NAMED_MODEL_QUANTITY_RE = re.compile(
    rf"(?<![\w-])(?P<count>{COUNT_PATTERN})\s+"
    r"(?P<item>(?:(?!and\b|or\b|for\b)[a-z0-9][a-z0-9-]*\s+){0,6}"
    r"(?:workstations?|desks?|bench(?:es)?|tables?|units?|pieces?))\b",
    re.IGNORECASE,
)
_NAMED_MODEL_QUANTITY_SUFFIX_RE = re.compile(
    r"(?:^|[.;!?\n])\s*"
    r"(?P<item>[^.;!?\n]+?)\bfor\s+(?P<capacity>[^,.;!?\n]+?)"
    r"(?:,\s*|\s+(?:using|with)\s+)"
    rf"(?P<count>{COUNT_PATTERN})\s+"
    r"(?P<unit>workstations|desks|benches|tables|units|pieces)\b"
    r"(?=\s*(?:$|[,.;!?]))",
    re.IGNORECASE,
)


def _fold_model_text(text: str) -> str:
    return " ".join(fold_catalog_homoglyphs(text).casefold().split())


def _candidate_model_references(candidate: str) -> tuple[str, ...]:
    """Model references a catalog row answers to, taken from its name line.

    "Four person workstation SKYLAND LUMA 9719-4" answers to "luma 9719-4" and
    to the distinctive code "9719-4" alone; "MEETING TABLE SKYLAND NOVO 2400"
    answers to "novo 2400" but not to a bare "2400", which reads as a price.
    """
    name_line = _fold_model_text(candidate.split("\n", 1)[0])
    tokens = _MODEL_CODE_TOKEN_RE.findall(name_line)
    references: list[str] = []
    for index, token in enumerate(tokens):
        if not any(char.isdigit() for char in token) or len(token) < 3:
            continue
        if _DIMENSION_CODE_RE.match(token):
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if following in _MODEL_CODE_WORD_EXCLUSIONS:
            continue
        distinctive = len(token) >= 5 and (
            "-" in token or any(char.isalpha() for char in token)
        )
        if distinctive:
            references.append(token)
        previous = tokens[index - 1] if index > 0 else ""
        if previous.isalpha() and len(previous) >= 2:
            references.append(f"{previous} {token}")
    return tuple(dict.fromkeys(references))


def _query_names_model_reference(folded_query: str, reference: str) -> bool:
    pattern = r"[\s-]*".join(re.escape(part) for part in reference.split())
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", folded_query) is not None


def _query_model_references(query: str) -> tuple[str, ...]:
    prepared = _EXPLICIT_DIMENSION_RE.sub(
        " ", _MONEY_AMOUNT_RE.sub(" ", strip_head_counts(_fold_model_text(query)))
    )
    excluded = (
        _PRODUCT_MATCH_FILLER_TERMS
        | _PRODUCT_NEED_TERMS
        | _PRODUCT_FINISH_TERMS
        | _STOPWORDS
        | {"quantity", "units", "pieces", "width", "height", "length", "depth"}
    )
    return tuple(
        reference
        for reference in _candidate_model_references(prepared)
        if " " not in reference
        or (
            reference.split()[0] not in excluded
            and parse_count_word(reference.split()[0]) is None
        )
    )


def _references_overlap(first: Sequence[str], second: Sequence[str]) -> bool:
    return any(
        _query_names_model_reference(left, right)
        or _query_names_model_reference(right, left)
        for left in first
        for right in second
    )


def _explicit_product_queries(query: str) -> tuple[str, ...] | None:
    """Split only punctuation boundaries introducing a distinct model code.

    Finish conjunctions and attributes without a new model remain attached to
    their product. Unseparated comparisons retain their existing reading.
    """
    separators = list(re.finditer(r"[,;.!?\n]\s*(?:and\s+)?", query, re.IGNORECASE))
    starts = [0]
    ends: list[int] = []
    for index, separator in enumerate(separators):
        head_end = (
            separators[index + 1].start() if index + 1 < len(separators) else len(query)
        )
        before = _query_model_references(query[starts[-1] : separator.start()])
        after = _query_model_references(query[separator.end() : head_end])
        if before and after and not _references_overlap(before, after):
            ends.append(separator.start())
            starts.append(separator.end())
    if len(starts) < 2:
        return None
    return tuple(
        query[start:end].strip()
        for start, end in zip(starts, [*ends, len(query)], strict=True)
    )


def _customer_request_for_product_query(
    query: str, customer_request: str | None
) -> str | None:
    if customer_request is None:
        return None
    parts = _explicit_product_queries(customer_request)
    if parts is None:
        return customer_request
    references = _query_model_references(query)
    matching = [
        part
        for part in parts
        if _references_overlap(references, _query_model_references(part))
    ]
    return matching[0] if len(matching) == 1 else customer_request


def _candidate_matches_product_constraints(
    query: str, candidate: str, sku: str | None
) -> bool:
    folded_query = _fold_model_text(query)
    name = _fold_model_text(candidate.split("\n", 1)[0])
    references = [*_candidate_model_references(candidate)]
    if sku:
        references.append(" ".join(_MODEL_CODE_TOKEN_RE.findall(_fold_model_text(sku))))
    requested_references = _query_model_references(query)
    if not requested_references or not all(
        _references_overlap([reference], references)
        for reference in requested_references
    ):
        return False
    type_query = strip_head_counts(folded_query)
    primary_name = name.split(",", 1)[0]
    category = candidate.split("\n")[-1] if len(candidate.split("\n")) >= 3 else ""
    identity_type = _fold_model_text(f"{category}\n{sku or ''}")

    def matches_type(family: str, term: str) -> bool:
        if contains_catalog_term(primary_name, term):
            return True
        # A face-to-face table may be a workstation by its catalog category
        # or SKU. Its physical name must still belong to workspace, and an
        # explicitly coffee/meeting table is not promoted to a workstation.
        return (
            family == "workspace"
            and "workspace" in catalog_text_families(primary_name)
            and not re.search(r"\b(?:coffee|meeting)\s+tables?\b", primary_name)
            and contains_catalog_term(identity_type, term)
        )

    if any(
        contains_catalog_term(type_query, term) and not matches_type(family, term)
        for family, terms in CATALOG_PRODUCT_FAMILIES
        for term in terms
    ) or any(
        not re.search(rf"\b{kind}\s+tables?\b", primary_name)
        for kind in re.findall(r"\b(coffee|meeting)\s+tables?\b", type_query)
    ):
        return False

    def dimensions(text: str) -> set[str]:
        return {
            re.sub(r"\s+", "", value).replace("*", "x")
            for value in _EXPLICIT_DIMENSION_RE.findall(text)
        }

    if not dimensions(folded_query).issubset(dimensions(name)):
        return False
    if any(
        not re.search(rf"\b{shape}\b", primary_name)
        for shape in re.findall(r"\b(round|square|oval|rectangular)\b", type_query)
    ):
        return False
    return not (
        _capacity_value(folded_query) is not None and _capacity_value(candidate) is None
    )


def _has_explicit_item_quantity(text: str, references: Sequence[str]) -> bool:
    # A numeric model suffix in `NOVO 240 workstation` is an identifier, not
    # 240 requested units. Remove only literal references to this catalog row.
    without_references = text
    for reference in sorted(references, key=len, reverse=True):
        pattern = r"[\s-]*".join(re.escape(part) for part in reference.split())
        without_references = re.sub(
            rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", " model ", without_references
        )
    return _NAMED_MODEL_QUANTITY_RE.search(without_references) is not None


def _matches_aggregate_model_capacity(
    query: str,
    references: Sequence[str],
    requested_capacity: int,
    candidate_capacity: int,
) -> bool:
    """Multiple units of this model may serve a stated aggregate head count."""
    folded_query = _fold_model_text(query)
    for match in _NAMED_MODEL_QUANTITY_RE.finditer(folded_query):
        quantity = count_value(match.group("count"))
        if quantity is None or quantity < 2:
            continue
        if not any(
            _query_names_model_reference(match.group("item"), reference)
            for reference in references
        ):
            continue
        # A capacity before the product noun ("two eight-person LUMA ...")
        # describes each unit, even when an aggregate need follows it.
        if _capacity_value(folded_query[: match.end()]) is not None:
            continue
        tail = re.split(r"[.;!?\n]", folded_query[match.end() :], maxsplit=1)[0]
        if (
            not re.search(r"\bfor\b", tail)
            or re.search(r"\b(?:and|or|each|per)\b", tail)
            or _has_explicit_item_quantity(tail, references)
        ):
            continue
        if (
            _capacity_value(tail) == requested_capacity
            and quantity * candidate_capacity == requested_capacity
        ):
            return True
    return _matches_suffix_aggregate_model_capacity(
        folded_query, references, requested_capacity, candidate_capacity
    )


def _matches_suffix_aggregate_model_capacity(
    folded_query: str,
    references: Sequence[str],
    requested_capacity: int,
    candidate_capacity: int,
) -> bool:
    """Bind `MODEL for N people, Q units` or `using Q units` to this model."""
    for match in _NAMED_MODEL_QUANTITY_SUFFIX_RE.finditer(folded_query):
        quantity = count_value(match.group("count"))
        if quantity is None or quantity < 2:
            continue
        item = match.group("item")
        capacity = match.group("capacity")
        stripped_capacity = strip_head_counts(capacity, replacement="\x00")
        if (
            _capacity_value(item) is not None
            or _has_explicit_item_quantity(item, references)
            or re.search(r"\b(?:and|or|each|per|plus)\b|[&/]", item)
            or stripped_capacity.count("\x00") != 1
            or _tokenize(stripped_capacity)
            or _capacity_value(capacity) != requested_capacity
            or quantity * candidate_capacity != requested_capacity
        ):
            continue
        finish_attributes = [part.strip() for part in item.split(",")[1:]]
        if any(
            _tokenize(attribute) - _PRODUCT_FINISH_TERMS - {"finish", "color", "colour"}
            or not (_tokenize(attribute) & _PRODUCT_FINISH_TERMS)
            for attribute in finish_attributes
            if attribute
        ):
            continue
        item_references = _candidate_model_references(item)
        if not item_references or not all(
            any(
                _query_names_model_reference(ref, candidate_ref)
                for candidate_ref in references
            )
            for ref in item_references
        ):
            continue
        unit = match.group("unit")
        singular_unit = "bench" if unit == "benches" else unit.removesuffix("s")
        if unit not in {"units", "pieces"} and not re.search(
            rf"\b(?:{re.escape(singular_unit)}|{re.escape(unit)})\b", item
        ):
            continue
        # Check the whole remaining request: a later sentence may change the
        # quantity or model. A trailing budget is harmless request context.
        tail = folded_query[match.end() :]
        if _tokenize(_MONEY_AMOUNT_RE.sub(" ", tail)) - _PRODUCT_MATCH_FILLER_TERMS:
            continue
        return True
    return False


def _model_reference_attributes_agree(query: str, candidate: str) -> bool:
    query_tokens = _tokenize(_fold_model_text(query))
    candidate_tokens = _tokenize(_fold_model_text(candidate))
    return (query_tokens & _PRODUCT_FINISH_TERMS).issubset(
        candidate_tokens
    ) and _explicit_structured_discriminators(query).issubset(candidate_tokens)


def _query_allows_aggregate_model_capacity(
    query: str, references: Sequence[str]
) -> bool:
    folded_query = _fold_model_text(query)
    if re.search(r"\b(?:each|per)\b", folded_query):
        return False
    if _has_explicit_item_quantity(folded_query, references):
        # An explicit count, including `..., two units`, must stand on its own;
        # the literal customer request cannot override a conflicting query.
        return False
    # A shortened query may retain "MODEL for eight people" while dropping
    # the unit count. "Eight-person MODEL" still states per-unit capacity.
    return any(
        _capacity_value(prefix := folded_query[: match.start()]) is None
        and any(_query_names_model_reference(prefix, ref) for ref in references)
        for match in re.finditer(r"\bfor\b", folded_query)
    )


def _model_reference_details_agree(
    query: str,
    candidate: str,
    references: Sequence[str],
    *,
    customer_request: str | None = None,
) -> bool:
    """A named model is the item only if the named finish and size agree too."""
    if not _model_reference_attributes_agree(query, candidate):
        return False
    requested_capacity = _capacity_value(query)
    candidate_capacity = _capacity_value(candidate)
    return (
        requested_capacity is None
        or candidate_capacity is None
        or requested_capacity == candidate_capacity
        or _matches_aggregate_model_capacity(
            query, references, requested_capacity, candidate_capacity
        )
        or (
            customer_request is not None
            and _model_reference_attributes_agree(customer_request, candidate)
            and _query_allows_aggregate_model_capacity(query, references)
            and _matches_aggregate_model_capacity(
                customer_request, references, requested_capacity, candidate_capacity
            )
        )
    )


def _matches_named_model_reference(
    query: str,
    candidate: str,
    sku: str | None = None,
    *,
    customer_request: str | None = None,
) -> bool:
    """Whether the query names this row by model reference or by SKU.

    The SKU takes part only here, never in the word-overlap reading: its
    fragments ("POD-1", "OF-HAI-...") are codes, not product words.
    """
    folded_query = _fold_model_text(query)
    references = list(_candidate_model_references(candidate))
    folded_sku = _fold_model_text(sku or "")
    if len(folded_sku) >= 4 and any(char.isdigit() for char in folded_sku):
        references.append(" ".join(_MODEL_CODE_TOKEN_RE.findall(folded_sku)))
    details_text = f"{candidate}\n{sku or ''}"
    return any(
        _query_names_model_reference(folded_query, reference)
        for reference in references
        if reference
    ) and _model_reference_details_agree(
        query, details_text, references, customer_request=customer_request
    )


def _matches_named_model_finish_variants(
    query: str, candidates: Sequence[str], skus: Sequence[str | None]
) -> bool | None:
    """Prove each named finish on matching variants of one catalog product.

    Return None for queries outside the explicit compound-finish list syntax.
    Two ordinary colours may describe one bicolour item, so that existing
    single-row reading stays unchanged.
    """
    folded_query = _fold_model_text(query)
    finish_list = _NAMED_FINISH_LIST_RE.search(folded_query)
    if finish_list is None:
        return None
    variants = tuple(
        dict.fromkeys(
            re.sub(r"\s+finish$", "", part)
            for part in re.split(r"\s+and\s+", finish_list.group("finishes"))
        )
    )
    if len(variants) < 2 or any(len(variant.split()) != 2 for variant in variants):
        return None
    core_query = (
        folded_query[: finish_list.start("finishes")]
        + folded_query[finish_list.end("finishes") :]
    )
    requested_table_types = re.findall(r"\b(coffee|meeting)\s+tables?\b", core_query)
    groups: dict[tuple[frozenset[str], int | None], set[str]] = {}
    requested_capacity = _capacity_value(folded_query)
    for candidate, sku in zip(candidates, skus, strict=True):
        capacity = _capacity_value(candidate)
        if requested_capacity is not None and requested_capacity != capacity:
            continue
        name_line = _fold_model_text(candidate.split("\n", 1)[0])
        if any(
            not re.search(rf"\b{kind}\s+tables?\b", name_line.split(",", 1)[0])
            for kind in requested_table_types
        ):
            continue
        references = _candidate_model_references(candidate)
        without_references = core_query
        for reference in references:
            pattern = r"[\s-]*".join(re.escape(part) for part in reference.split())
            without_references = re.sub(
                rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", " ", without_references
            )
        core_terms = (
            _tokenize(_MONEY_AMOUNT_RE.sub(" ", strip_head_counts(without_references)))
            - _PRODUCT_MATCH_FILLER_TERMS
            - _VARIANT_QUERY_FILLER_TERMS
        )
        for variant in variants:
            finish_pattern = rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])"
            if (
                re.search(finish_pattern, f"{name_line}\n{_fold_model_text(sku or '')}")
                is None
            ):
                continue
            variant_query = (
                folded_query[: finish_list.start("finishes")]
                + variant
                + folded_query[finish_list.end("finishes") :]
            )
            if not _matches_named_model_reference(variant_query, candidate, sku):
                continue
            base_terms = frozenset(_tokenize(re.sub(finish_pattern, " ", name_line)))
            if not all(_term_variants(term) & base_terms for term in core_terms):
                continue
            groups.setdefault((base_terms, capacity), set()).add(variant)
    return any(set(variants).issubset(found) for found in groups.values())


_MONEY_AMOUNT_RE = re.compile(
    rf"(?:\b(?:{BUDGET_AED_CURRENCY_PATTERN}|under|below|within|max(?:imum)?"
    r"|budget|up\s+to)\s*)\d[\d,.]*(?:\s*k)?\b"
    rf"|\b\d[\d,.]*\s*(?:{BUDGET_AED_CURRENCY_PATTERN})\b",
    re.IGNORECASE,
)

_GENERIC_QUANTITY_PREFIX_WORDS = frozenset(
    {
        "about",
        "add",
        "adding",
        "also",
        "and",
        "around",
        "at",
        "between",
        "buy",
        "buying",
        "compare",
        "comparing",
        "considering",
        "find",
        "for",
        "from",
        "get",
        "getting",
        "give",
        "have",
        "in",
        "include",
        "including",
        "least",
        "like",
        "looking",
        "need",
        "needing",
        "needs",
        "of",
        "on",
        "or",
        "order",
        "ordering",
        "plus",
        "prefer",
        "quote",
        "quoting",
        "recommend",
        "require",
        "requires",
        "requiring",
        "search",
        "show",
        "suggest",
        "supply",
        "take",
        "to",
        "total",
        "up",
        "want",
        "wanting",
        "wants",
        "with",
        "نحتاج",
        "احتاج",
        "أحتاج",
        "اريد",
        "أريد",
        "عندنا",
        "في",
        "من",
        "و",
        "او",
        "أو",
    }
)
_GENERIC_QUANTITY_MODIFIER_TERMS = (
    _PRODUCT_NEED_TERMS
    | _PRODUCT_MATCH_FILLER_TERMS
    | frozenset(
        {
            "acoustic",
            "adjustable",
            "arm",
            "armrest",
            "armrests",
            "arms",
            "back",
            "basic",
            "big",
            "children",
            "compact",
            "computer",
            "conference",
            "dining",
            "executive",
            "fabric",
            "glass",
            "good",
            "high",
            "high-back",
            "home",
            "kids",
            "large",
            "leather",
            "living",
            "lounge",
            "low",
            "low-back",
            "medium",
            "meeting",
            "metal",
            "mid",
            "mid-back",
            "mobile",
            "nice",
            "open",
            "operative",
            "padded",
            "quality",
            "reception",
            "shared",
            "simple",
            "small",
            "standard",
            "standing",
            "station",
            "stations",
            "steel",
            "storage",
            "study",
            "swivel",
            "task",
            "upholstered",
            "visitor",
            "waiting",
            "wooden",
        }
    )
)
_GENERIC_QUANTITY_PRODUCT_NOUNS = frozenset(
    {
        "accessory",
        "accessories",
        "bed",
        "beds",
        "bench",
        "benches",
        "bookcase",
        "bookcases",
        "bookshelf",
        "bookshelves",
        "booth",
        "booths",
        "cabinet",
        "cabinets",
        "chair",
        "chairs",
        "desk",
        "desks",
        "drawer",
        "drawers",
        "furniture",
        "item",
        "items",
        "locker",
        "lockers",
        "mattress",
        "mattresses",
        "option",
        "options",
        "pedestal",
        "pedestals",
        "piece",
        "pieces",
        "pod",
        "pods",
        "seat",
        "seating",
        "seats",
        "set",
        "sets",
        "shelf",
        "shelves",
        "sofa",
        "sofas",
        "station",
        "stations",
        "stool",
        "stools",
        "storage",
        "table",
        "tables",
        "unit",
        "units",
        "wardrobe",
        "wardrobes",
        "workstation",
        "workstations",
        "workspace",
        "workspaces",
        "أثاث",
        "اثاث",
        "تخزين",
        "خزائن",
        "خزانة",
        "طاولات",
        "طاولة",
        "كبسولة",
        "كراسي",
        "كرسي",
        "محطات",
        "محطة",
        "مقصورة",
        "مكاتب",
        "مكتب",
    }
)
_GENERIC_MODIFIER_PATTERN = "|".join(
    re.escape(term)
    for term in sorted(_GENERIC_QUANTITY_MODIFIER_TERMS, key=len, reverse=True)
)
_GENERIC_PRODUCT_NOUN_PATTERN = "|".join(
    re.escape(term)
    for term in sorted(_GENERIC_QUANTITY_PRODUCT_NOUNS, key=len, reverse=True)
)
_GENERIC_ITEM_QUANTITY_RE = re.compile(
    r"(?<![\w\-x*.])(?P<qty>\d{1,3})(?![\w\-x*.])"
    r"(?:\s*(?:x|×))?\s+"
    rf"(?P<rest>(?:(?:{_GENERIC_MODIFIER_PATTERN})\s+){{0,4}}"
    rf"(?:{_GENERIC_PRODUCT_NOUN_PATTERN}))(?!\w)",
    re.IGNORECASE | re.UNICODE,
)


def _is_standalone_generic_quantity_match(text: str, match: re.Match[str]) -> bool:
    prefix = text[: match.start()].rstrip()
    if not prefix or prefix[-1] in ",.;:!?()\n/":
        return True
    prev_match = re.search(r"([\w-]+)$", prefix, flags=re.UNICODE)
    if prev_match is None:
        return True
    return prev_match.group(1).casefold() in _GENERIC_QUANTITY_PREFIX_WORDS


def _generic_item_quantity_tokens(text: str) -> set[str]:
    prepared = strip_head_counts(text)
    return {
        match.group("qty")
        for match in _GENERIC_ITEM_QUANTITY_RE.finditer(prepared)
        if _is_standalone_generic_quantity_match(prepared, match)
    }


def _strip_generic_item_quantities(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        if _is_standalone_generic_quantity_match(text, match):
            return f" {match.group('rest')}"
        return match.group(0)

    return _GENERIC_ITEM_QUANTITY_RE.sub(_replace, text)


def query_names_specific_item(query: str) -> bool:
    """Whether the query names a code, brand, finish or model number."""
    without_amounts = _MONEY_AMOUNT_RE.sub(
        " ", _strip_generic_item_quantities(strip_head_counts(query))
    )
    named = (
        (
            _explicit_structured_identifiers(query)
            | _explicit_structured_discriminators(query)
        )
        - _PRODUCT_NEED_TERMS
        - _PRODUCT_MATCH_FILLER_TERMS
    )
    return bool(named) or any(char.isdigit() for char in without_amounts)


def _term_variants(term: str) -> set[str]:
    variants = {term}
    if term.endswith("s") and len(term) > 3:
        variants.add(term[:-1])
    else:
        variants.add(f"{term}s")
    return variants


def _is_generic_need_request(
    query: str,
    candidate_tokens: Sequence[set[str]],
    candidate_families_hint: Sequence[str] = (),
) -> bool:
    """Whether the query only states a need that the candidates speak to.

    A request naming no product code, brand, finish or other discriminator has
    no exact item to confirm. It still has to be *about* these candidates, and
    what decides that is the product family (tj-uz6j, replay 2026-09-23):

    - a product-type word from the catalog family vocabulary ("desks",
      "workstations", "cabinets") is covered when a returned row carries that
      word or any other type of the same family, so "desks/workstations"
      answered by a four-person workstation is the need, not an alternative;
    - a type declared a distinct nearby item in `_NEARBY_EQUIVALENTS`
      ("pods" vs "booths", "accessories" vs pedestals) is covered only by its
      own word, because the family there spans items the customer tells apart;
    - any other word ("lighting", an unknown brand in lower case) must occur on
      at least one returned row, otherwise the honest reading stays "nearby"
      or "missing".
    """
    if query_names_specific_item(query):
        return False
    need_text = _MONEY_AMOUNT_RE.sub(" ", strip_head_counts(_normalize(query)))
    terms = _tokenize(need_text) - _PRODUCT_MATCH_FILLER_TERMS
    if not terms:
        return False
    if terms & _PRODUCT_FINISH_TERMS:
        return False
    # A head count ("a team of six", "twenty people") states the need, like a
    # digit does; head-count phrases are stripped above, and any count word
    # left over is still a count, never an unmet product word.
    open_terms = {
        term
        for term in terms
        if term not in _PRODUCT_NEED_TERMS
        and not term.isdigit()
        and parse_count_word(term) is None
    }
    candidate_union: set[str] = set().union(*candidate_tokens)
    candidate_families = set(candidate_families_hint)

    def _covered(term: str) -> bool:
        if _term_variants(term) & candidate_union:
            return True
        if term in _NEARBY_EQUIVALENTS:
            return False
        term_families = catalog_text_families(term)
        return bool(term_families) and set(term_families).issubset(candidate_families)

    if not all(_covered(term) for term in open_terms):
        return False
    return bool(open_terms) or bool(terms & _PRODUCT_NEED_TERMS)


def classify_product_match(
    query: str,
    candidates: Sequence[str],
    *,
    candidate_skus: Sequence[str | None] | None = None,
    customer_request: str | None = None,
) -> ProductMatch:
    if not candidates:
        return "missing"
    skus: Sequence[str | None] = (
        candidate_skus
        if candidate_skus is not None and len(candidate_skus) == len(candidates)
        else [None] * len(candidates)
    )

    product_queries = _explicit_product_queries(query)
    if product_queries is not None:
        matches: list[ProductMatch] = []
        for product_query in product_queries:
            applicable = [
                (candidate, sku)
                for candidate, sku in zip(candidates, skus, strict=True)
                if _candidate_matches_product_constraints(product_query, candidate, sku)
            ]
            matches.append(
                classify_product_match(
                    product_query,
                    [candidate for candidate, _ in applicable],
                    candidate_skus=[sku for _, sku in applicable],
                    customer_request=_customer_request_for_product_query(
                        product_query, customer_request
                    ),
                )
            )
        if all(match == "exact" for match in matches):
            return "exact"
        return "missing" if all(match == "missing" for match in matches) else "nearby"

    variant_match = _matches_named_model_finish_variants(query, candidates, skus)
    if variant_match:
        return "exact"

    if variant_match is None and any(
        _matches_structured_workstation_constraints(query, candidate)
        for candidate in candidates
    ):
        return "exact"

    if variant_match is None and any(
        _matches_named_model_reference(
            query, candidate, sku, customer_request=customer_request
        )
        for candidate, sku in zip(candidates, skus, strict=True)
    ):
        return "exact"

    normalized_query = _normalize(query)
    candidate_tokens = [_tokenize(candidate) for candidate in candidates]
    query_tokens = {
        token
        for token in _tokenize(normalized_query)
        if token not in {"tell", "about", "your", "show", "what", "have"}
    }

    exact_terms = {
        token for token in query_tokens if token not in _PRODUCT_MATCH_FILLER_TERMS
    } | _generic_item_quantity_tokens(normalized_query)

    if (
        variant_match is None
        and exact_terms
        and any(
            all(
                any(variant in candidate for variant in _term_variants(term))
                for term in exact_terms
            )
            for candidate in candidate_tokens
        )
    ):
        return "exact"

    candidate_families = {
        family
        for candidate in candidates
        for family in catalog_text_families(candidate)
    }
    if _is_generic_need_request(query, candidate_tokens, tuple(candidate_families)):
        return "generic"

    overlap_terms = set(exact_terms)
    for term in exact_terms:
        overlap_terms.update(_term_variants(term))
        overlap_terms.update(_NEARBY_EQUIVALENTS.get(term, set()))

    if any(candidate & overlap_terms for candidate in candidate_tokens):
        return "nearby"

    return "missing"


def is_requested_product_candidate(
    query: str,
    candidate: str,
    *,
    candidate_sku: str | None = None,
    customer_request: str | None = None,
) -> bool:
    """Whether a row matches its own request, without claiming whole coverage.

    Callers must establish complete search coverage separately before using
    this membership proof to choose exact-result media.
    """
    product_queries = _explicit_product_queries(query)
    for product_query in product_queries or (query,):
        folded_query = _fold_model_text(product_query)
        finish_list = _NAMED_FINISH_LIST_RE.search(folded_query)
        if (product_queries is not None or finish_list is not None) and not (
            _candidate_matches_product_constraints(
                product_query, candidate, candidate_sku
            )
        ):
            continue
        scoped_customer_request = _customer_request_for_product_query(
            product_query, customer_request
        )
        if finish_list is None:
            if (
                classify_product_match(
                    product_query,
                    [candidate],
                    candidate_skus=[candidate_sku],
                    customer_request=scoped_customer_request,
                )
                == "exact"
            ):
                return True
            continue
        for part in re.split(r"\s+and\s+", finish_list.group("finishes")):
            variant = re.sub(r"\s+finish$", "", part)
            name = _fold_model_text(candidate.split("\n", 1)[0])
            identity = f"{name}\n{_fold_model_text(candidate_sku or '')}"
            if not re.search(
                rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])", identity
            ):
                continue
            variant_query = (
                folded_query[: finish_list.start("finishes")]
                + variant
                + folded_query[finish_list.end("finishes") :]
            )
            if (
                classify_product_match(
                    variant_query,
                    [candidate],
                    candidate_skus=[candidate_sku],
                    customer_request=scoped_customer_request,
                )
                == "exact"
            ):
                return True
    return False
