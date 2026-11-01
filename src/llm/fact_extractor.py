"""Customer contact and delivery-address helpers for turn validation."""

from __future__ import annotations

import re

from src.llm.pii import EMAIL_PATTERN, PHONE_PATTERN

_ADDRESS_LABEL_PATTERN = re.compile(
    r"\b(?:delivery\s+address|(?<!email\s)(?<!billing\s)address|"
    r"delivered\s+to|deliver\s+to|delivery\s+to|with\s+delivery\s+to|"
    r"ship\s+to|shipped\s+to|shipping\s+to|send\s+to)\b"
    r"\s*(?:is|:|-)?\s*",
    re.IGNORECASE,
)
_ADDRESS_DETAIL_BOUNDARY_PATTERN = re.compile(
    r"(?:[,;/]|\n|\.\s+)\s*"
    r"(?=(?:email|e-mail|phone|mobile|whatsapp|tel|full\s+name|my\s+name|"
    r"name|customer(?:\s+name)?|company(?:\s+name)?|account|organization|"
    r"organisation|individual|private\s+customer|corporate|budget|color|"
    r"colour|assembly|i\s+am|i'm|we\s+are|i\s+need|we\s+need|need|want|"
    r"please|proceed|can|could|would|will|do|does|did|what|which|where|"
    r"when|how|is|are|was|were|may)\b|"
    rf"{EMAIL_PATTERN.pattern}|\+\d)",
    re.IGNORECASE,
)
_ADDRESS_SEGMENT_PATTERN = re.compile(r"[^,;\n/]+")
_ADDRESS_TERM_PATTERN = re.compile(
    r"\b(?:street|st|road|rd|avenue|ave|villa|office|building|tower|suite|"
    r"unit|floor|apartment|apt|plot|warehouse|zone)\b",
    re.IGNORECASE,
)
_ADDRESS_DISTRICT_PATTERN = re.compile(
    r"\b(?:business\s+bay|dubai\s+marina|jlt|difc)\b",
    re.IGNORECASE,
)
_DETAIL_SEGMENT_PATTERN = re.compile(
    r"^(?:email|e-mail|phone|mobile|whatsapp|tel|full\s+name|my\s+name|"
    r"name|customer(?:\s+name)?|company(?:\s+name)?|account|organization|"
    r"organisation|individual|private\s+customer|corporate|budget|color|"
    r"colour|assembly)\b",
    re.IGNORECASE,
)
_GENERIC_SPACED_SKU_PATTERN = re.compile(r"\b[A-Z]{1,4}\s*[- ]\s*\d{2,8}\b")
_PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN = re.compile(
    r"\b(?:need|needs|want|wants|would\s+like|looking\s+for|quote|quotation|"
    r"chair|chairs|desk|desks|table|tables|workstation|workstations|sku|"
    r"assembly|installation)\b",
    re.IGNORECASE,
)


def is_customer_phone_detail(text: str, match: re.Match[str]) -> bool:
    """Return whether a broad phone-pattern match is customer contact data."""

    raw_phone = match.group(0).strip()
    if raw_phone.startswith("+"):
        return True
    prefix = text[max(0, match.start() - 40) : match.start()].casefold()
    return bool(
        re.search(
            r"(?:phone|mobile|tel|whatsapp)\s*[:：=-]?\s*$",
            prefix,
        )
    )


def extract_delivery_address(text: str) -> str | None:
    """Extract one specific delivery address without adjacent customer details."""

    candidate = _delivery_address_candidate(text)
    return candidate[0] if candidate else None


def _delivery_address_candidate(text: str) -> tuple[str, str, bool] | None:
    for label_match in _ADDRESS_LABEL_PATTERN.finditer(text):
        if is_question_clause(text, label_match.start()):
            continue
        raw_value = _address_before_next_detail(text[label_match.end() :])
        if not _looks_like_address(raw_value):
            continue
        evidence_end = label_match.end() + len(raw_value)
        evidence = text[label_match.start() : evidence_end].strip()
        return raw_value, evidence, True

    segments = list(_ADDRESS_SEGMENT_PATTERN.finditer(text))
    for index, segment_match in enumerate(segments):
        segment = segment_match.group(0).strip()
        embedded_label = _ADDRESS_LABEL_PATTERN.search(segment)
        if embedded_label and is_question_clause(
            text,
            segment_match.start() + embedded_label.start(),
        ):
            continue
        next_segment = (
            segments[index + 1].group(0).strip() if index + 1 < len(segments) else None
        )
        if not _is_address_start_segment(segment, next_segment):
            continue

        start = (
            segment_match.start()
            + len(segment_match.group(0))
            - len(segment_match.group(0).lstrip())
        )
        end = segment_match.end()
        for following in segments[index + 1 :]:
            following_value = following.group(0).strip()
            if _is_adjacent_customer_detail(text, following, following_value):
                break
            end = following.end()

        raw_value = text[start:end].strip(" \t\r\n,;/").rstrip(".")
        if _looks_like_address(raw_value):
            return raw_value, raw_value, False
    return None


def is_question_clause(text: str, offset: int) -> bool:
    """Return whether the sentence before ``offset`` starts as a question."""

    offset = max(0, min(offset, len(text)))
    sentence_starts = [0]
    for boundary in ("\n", ". ", "!", "?"):
        position = text.rfind(boundary, 0, offset)
        if position >= 0:
            sentence_starts.append(position + len(boundary))
    prefix = text[max(sentence_starts) : offset].strip()
    return bool(
        re.match(
            r"(?:(?:can|could|would|do|does|did|what|which|where|when|how|"
            r"is|are|was|were)\b|(?:will|may)\s+"
            r"(?:i|you|we|they|he|she|it|there|the|this|that|our|your|delivery)\b)",
            prefix,
            re.IGNORECASE,
        )
    )


def _address_before_next_detail(tail: str) -> str:
    boundary = _ADDRESS_DETAIL_BOUNDARY_PATTERN.search(tail)
    raw_value = tail[: boundary.start()] if boundary else tail
    return raw_value.strip(" \t\r\n,;/").rstrip(".")


def _is_address_start_segment(segment: str, next_segment: str | None) -> bool:
    if not segment or "?" in segment:
        return False
    if _ADDRESS_DISTRICT_PATTERN.search(segment):
        return True
    if _ADDRESS_TERM_PATTERN.search(segment) and re.search(r"\d", segment):
        return True
    if re.search(r"\b\d+[A-Za-z]?\s+[A-Za-z]", segment):
        return True
    return bool(
        re.fullmatch(r"\d+[A-Za-z]?", segment)
        and next_segment
        and _ADDRESS_TERM_PATTERN.search(next_segment)
    )


def _is_adjacent_customer_detail(
    text: str,
    match: re.Match[str],
    value: str,
) -> bool:
    if not value:
        return False
    if EMAIL_PATTERN.search(value) or _DETAIL_SEGMENT_PATTERN.search(value):
        return True
    return any(
        is_customer_phone_detail(text, phone_match)
        for phone_match in PHONE_PATTERN.finditer(
            text,
            match.start(),
            match.end(),
        )
    )


def _looks_like_address(value: str) -> bool:
    if not value or "?" in value:
        return False
    if is_question_clause(value, len(value)):
        return False
    lowered = value.lower()
    if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
        return False
    if _GENERIC_SPACED_SKU_PATTERN.search(value):
        return False
    if _PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN.search(value):
        return False
    normalized = re.sub(r"[\W_]+", " ", lowered).strip()
    if normalized in {
        "abu dhabi",
        "ajman",
        "dubai",
        "emirates",
        "sharjah",
        "uae",
        "united arab emirates",
    }:
        return False
    return bool(
        re.search(r"\b\d+[A-Za-z]?\s+[A-Za-z]", value)
        or (_ADDRESS_TERM_PATTERN.search(value) and re.search(r"\d", value))
        or _ADDRESS_DISTRICT_PATTERN.search(value)
    )


def is_specific_delivery_address(address: str | None) -> bool:
    """Return whether an address is more specific than a city or country."""

    value = address.strip() if isinstance(address, str) else ""
    if not value:
        return False
    if "?" in value or not re.search(r"[^\W\d_]", value):
        return False
    normalized = re.sub(r"[\W_]+", " ", value.casefold()).strip()
    generic_addresses = {
        "uae",
        "u a e",
        "united arab emirates",
        "emirates",
        "dubai",
        "abu dhabi",
        "sharjah",
        "ajman",
        "ras al khaimah",
        "fujairah",
        "umm al quwain",
    }
    if normalized in generic_addresses:
        return False
    tokens = [token for token in normalized.split() if token]
    return len(tokens) >= 2 or bool(re.search(r"\d", value))
