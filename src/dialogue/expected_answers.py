from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.dialogue.state import DialogueState, ExpectedAnswerFrame, ExpectedSlot


class ExpectedAnswerMatch(BaseModel):
    matched: bool = False
    frame_id: str | None = None
    confidence: str = "none"
    filled_slots: dict[str, Any] = Field(default_factory=dict)
    fulfilled: bool = False
    missing_required_slots: list[str] = Field(default_factory=list)
    route: str = "legacy_fallback"
    interruption: bool = False
    ambiguous_frame_ids: list[str] = Field(default_factory=list)
    blocker: str | None = None


def match_expected_answer(
    state: DialogueState,
    text: str,
    now: datetime | None = None,
) -> ExpectedAnswerMatch:
    normalized = _normalize_text(text)
    if not normalized:
        return ExpectedAnswerMatch()

    blocker = _hard_blocker(normalized)
    if blocker:
        return ExpectedAnswerMatch(blocker=blocker)

    active_frames = _active_frames(state, now)
    if not active_frames:
        return ExpectedAnswerMatch()

    if _is_terse_ordinal_reference(normalized):
        ordinal_frames = [
            frame for frame in active_frames if _frame_accepts_ordinal(frame)
        ]
        if len(ordinal_frames) > 1:
            return ExpectedAnswerMatch(
                confidence="ambiguous",
                route="expected_answer_clarify",
                ambiguous_frame_ids=[frame.frame_id for frame in ordinal_frames],
            )
        ordinal = _ordinal_from_text(normalized)
        if ordinal is not None and ordinal_frames:
            ordinal_match = _match_ordinal_frame(ordinal_frames[0], ordinal)
            if ordinal_match.matched:
                return ordinal_match

    candidates = [
        candidate
        for candidate in (_match_frame(frame, normalized) for frame in active_frames)
        if candidate.matched
    ]
    if len(candidates) > 1:
        top_confidence = candidates[0].confidence
        ambiguous_frame_ids = [
            candidate.frame_id
            for candidate in candidates
            if candidate.confidence == top_confidence and candidate.frame_id
        ]
        if len(ambiguous_frame_ids) > 1:
            return ExpectedAnswerMatch(
                confidence="ambiguous",
                route="expected_answer_clarify",
                ambiguous_frame_ids=ambiguous_frame_ids,
            )
    if candidates:
        return candidates[0]

    if _is_bounded_service_interruption(normalized):
        return ExpectedAnswerMatch(interruption=True)

    return ExpectedAnswerMatch()


def _active_frames(
    state: DialogueState,
    now: datetime | None,
) -> list[ExpectedAnswerFrame]:
    frames = [
        frame
        for frame in state.expected_answer_frames
        if frame.status == "active" and not _frame_is_expired(frame, now)
    ]
    return sorted(frames, key=lambda frame: frame.priority, reverse=True)


def _match_frame(
    frame: ExpectedAnswerFrame,
    normalized_text: str,
) -> ExpectedAnswerMatch:
    filled_slots: dict[str, Any] = {}
    confidence_scores: list[int] = []

    for expected_slot in frame.expected_slots:
        slot_match = _match_slot(expected_slot, normalized_text)
        if not slot_match:
            continue
        value, score = slot_match
        filled_slots[expected_slot.slot] = value
        confidence_scores.append(score)

    if not filled_slots:
        return ExpectedAnswerMatch()

    score = max(confidence_scores)
    missing_required_slots = _missing_required_slots(frame, filled_slots)
    return ExpectedAnswerMatch(
        matched=True,
        frame_id=frame.frame_id,
        confidence="high" if score >= 2 else "medium",
        filled_slots=filled_slots,
        fulfilled=not missing_required_slots,
        missing_required_slots=missing_required_slots,
        route=_route_for_frame(frame),
    )


def _match_ordinal_frame(
    frame: ExpectedAnswerFrame,
    ordinal: int,
) -> ExpectedAnswerMatch:
    source_ref = _source_ref_for_ordinal(frame, ordinal)
    if not source_ref:
        return ExpectedAnswerMatch()
    raw_source_value = source_ref.get("value")
    if not isinstance(raw_source_value, str) or not raw_source_value.strip():
        return ExpectedAnswerMatch()

    filled_slots: dict[str, Any] = {}
    for expected_slot in frame.expected_slots:
        canonical_value = _slot_value_for_source_ref(expected_slot, raw_source_value)
        if canonical_value is not None:
            filled_slots[expected_slot.slot] = canonical_value

    if not filled_slots:
        return ExpectedAnswerMatch()

    missing_required_slots = _missing_required_slots(frame, filled_slots)
    return ExpectedAnswerMatch(
        matched=True,
        frame_id=frame.frame_id,
        confidence="high",
        filled_slots=filled_slots,
        fulfilled=not missing_required_slots,
        missing_required_slots=missing_required_slots,
        route=_route_for_frame(frame),
    )


def _source_ref_for_ordinal(
    frame: ExpectedAnswerFrame,
    ordinal: int,
) -> dict[str, Any] | None:
    for source_ref in frame.source_refs:
        raw_ordinal = source_ref.get("ordinal")
        if isinstance(raw_ordinal, int):
            source_ordinal = raw_ordinal
        elif isinstance(raw_ordinal, str) and raw_ordinal.strip():
            try:
                source_ordinal = int(raw_ordinal)
            except ValueError:
                continue
        else:
            continue
        if source_ordinal == ordinal:
            return source_ref
    index = ordinal - 1
    if 0 <= index < len(frame.source_refs):
        return frame.source_refs[index]
    return None


def _slot_value_for_source_ref(
    expected_slot: ExpectedSlot,
    source_value: str,
) -> str | None:
    normalized_source = _normalize_text(source_value)
    for value in expected_slot.accepted_values:
        if _contains_phrase(normalized_source, value):
            return value
    for value, aliases in expected_slot.aliases.items():
        if _contains_phrase(normalized_source, value):
            return value
        if any(_contains_phrase(normalized_source, alias) for alias in aliases):
            return value
    return None


def _missing_required_slots(
    frame: ExpectedAnswerFrame,
    filled_slots: dict[str, Any],
) -> list[str]:
    return [
        expected_slot.slot
        for expected_slot in frame.expected_slots
        if expected_slot.required and expected_slot.slot not in filled_slots
    ]


def _match_slot(
    expected_slot: ExpectedSlot,
    normalized_text: str,
) -> tuple[str, int] | None:
    matches: list[tuple[str, int]] = []
    for value in expected_slot.accepted_values:
        normalized_value = _normalize_text(value)
        if normalized_value and _contains_phrase(normalized_text, normalized_value):
            matches.append((value, 2))

    for value, aliases in expected_slot.aliases.items():
        normalized_value = _normalize_text(value)
        if normalized_value and _contains_phrase(normalized_text, normalized_value):
            matches.append((value, 2))
        for alias in aliases:
            normalized_alias = _normalize_text(alias)
            if normalized_alias and _contains_phrase(normalized_text, normalized_alias):
                matches.append((value, 2))

    if not matches:
        return None
    matches.sort(key=lambda item: item[1], reverse=True)
    return matches[0]


def _route_for_frame(frame: ExpectedAnswerFrame) -> str:
    if frame.question_kind == "product_preference":
        return "product_preference_answer"
    return f"{frame.question_kind}_answer"


def _hard_blocker(normalized_text: str) -> str | None:
    blockers = [
        (
            "human_request",
            (
                "human",
                "person",
                "representative",
                "agent",
                "manager",
                "supervisor",
                "lilia",
            ),
        ),
        ("complaint", ("complaint", "complain", "unhappy", "dissatisfied")),
        (
            "complaint",
            ("complaints", "complains"),
        ),
        (
            "refund",
            (
                "refund",
                "refunds",
                "return",
                "returns",
                "exchange",
                "exchanges",
                "money back",
            ),
        ),
        (
            "discount",
            (
                "discount",
                "discounts",
                "special price",
                "better price",
                "cheaper",
                "price reduction",
            ),
        ),
        (
            "payment_terms",
            (
                "payment terms",
                "payment term",
                "credit terms",
                "credit term",
                "credit",
                "net 30",
                "net30",
                "installment",
                "installments",
                "pay later",
            ),
        ),
        ("warranty", ("warranty", "warranties", "guarantee", "guarantees")),
    ]
    for blocker, terms in blockers:
        if any(_contains_phrase(normalized_text, term) for term in terms):
            return blocker
    return None


def _is_bounded_service_interruption(normalized_text: str) -> bool:
    if "?" not in normalized_text and not normalized_text.startswith(("can ", "do ")):
        return False
    service_terms = (
        "delivery",
        "deliver",
        "shipping",
        "ship",
        "installation",
        "install",
        "assembly",
        "assemble",
        "arranged",
        "arrange",
    )
    return any(_contains_phrase(normalized_text, term) for term in service_terms)


def _is_terse_ordinal_reference(normalized_text: str) -> bool:
    ordinal_terms = (
        "second",
        "2nd",
        "number 2",
        "option 2",
        "the 2",
        "first",
        "1st",
        "number 1",
        "option 1",
        "the 1",
    )
    if len(normalized_text.split()) > 5:
        return False
    return any(_contains_phrase(normalized_text, term) for term in ordinal_terms)


def _ordinal_from_text(normalized_text: str) -> int | None:
    first_terms = ("first", "1st", "number 1", "option 1", "the 1")
    second_terms = ("second", "2nd", "number 2", "option 2", "the 2")
    if any(_contains_phrase(normalized_text, term) for term in first_terms):
        return 1
    if any(_contains_phrase(normalized_text, term) for term in second_terms):
        return 2
    return None


def _frame_accepts_ordinal(frame: ExpectedAnswerFrame) -> bool:
    if len(frame.source_refs) >= 2:
        return True
    return any("ordinal" in source_ref for source_ref in frame.source_refs)


def _frame_is_expired(frame: ExpectedAnswerFrame, now: datetime | None) -> bool:
    if (
        frame.max_customer_turns is not None
        and frame.turns_seen > frame.max_customer_turns
    ):
        return True
    expires_at = _parse_datetime(frame.expires_at)
    if not expires_at:
        return False
    current = now or datetime.now(tz=expires_at.tzinfo or UTC)
    if expires_at.tzinfo and current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    if current.tzinfo and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=current.tzinfo)
    return current >= expires_at


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_phrase) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[^\w\s?]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
