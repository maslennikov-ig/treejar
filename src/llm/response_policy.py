"""Shared response-policy composition helpers."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Literal

from src.llm.closed_question_guard import apply_closed_question_guard
from src.llm.grounding_output import (
    GroundingOutputResult,
    classify_grounding_output,
    repair_grounding_output,
)
from src.llm.opening_guard import apply_opening_guard, opening_replacement_covers
from src.llm.sales_turn_guard import (
    carry_the_company_question,
    collapse_question_form,
    commit_to_what_you_deferred,
    refuse_to_chase_the_name,
)
from src.services.customer_language import is_arabic_customer_language

logger = logging.getLogger(__name__)

ReplyProvenance = Literal[
    "model",
    "model_repaired",
    "deterministic_replacement",
    "deterministic_static",
]


@dataclass(frozen=True, slots=True)
class ReplyPolicyState:
    """Explicit state consumed by the customer-facing text policy."""

    language: str
    is_first_turn: bool = False
    customer_name: str | None = None
    anchor_line: str | None = None
    company: str | None = None
    customer_type: str | None = None
    delivery_address: str | None = None
    previous_assistant_turns: tuple[str, ...] = ()
    owes_company_question: bool = False
    quote_consent_granted: bool = False
    inventory_confirmed: bool = False
    grounded_amounts: tuple[object, ...] | None = None
    required_tool_disclosure: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedReply:
    """Customer text after the single response-policy chain."""

    text: str
    provenance: ReplyProvenance
    grounding: GroundingOutputResult
    flags: tuple[ReplyGuardFlag, ...] = ()


class GuardMode(StrEnum):
    """Whether a deterministic guard covers or merely detects a removal."""

    REPLACING = "replacing"
    REMOVING = "removing"


ReplacementCoverage = Callable[[str, str], bool]


@dataclass(frozen=True, slots=True)
class GuardDeclaration:
    """The customer-text effect a guard is allowed to have."""

    name: str
    mode: GuardMode
    reason: str
    replacement_covers: ReplacementCoverage | None = None


@dataclass(frozen=True, slots=True)
class ReplyGuardFlag:
    """A deterministic question for the repair judge, never a verdict."""

    guard_name: str
    reason: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GuardApplication:
    """Guard output before any temporary replay-compatibility bridge."""

    text: str
    candidate: str
    flags: tuple[ReplyGuardFlag, ...] = ()


def apply_first_turn_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
    anchor_line: str | None,
) -> str:
    """Apply the existing opening guard from explicit turn state."""

    return apply_opening_guard(
        text,
        language=language,
        is_first_turn=is_first_turn,
        customer_name=customer_name,
        anchor_line=anchor_line,
    )


def apply_selling_turn_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    previous_assistant_turns: Sequence[str],
    customer_name: str | None,
    owes_company_question: bool,
) -> str:
    """Apply the selling-turn guards in their established order."""

    if is_first_turn or not text.strip():
        return text

    guarded = collapse_question_form(text)
    guarded = refuse_to_chase_the_name(
        guarded,
        previous_assistant_turns=previous_assistant_turns,
        customer_name=customer_name,
    )
    if owes_company_question:
        guarded = carry_the_company_question(guarded, language=language)
    return guarded


def repair_closed_questions(
    text: str,
    *,
    language: str,
    customer_name: str | None,
    company: str | None,
    customer_type: str | None,
    delivery_address: str | None,
) -> str:
    """Repair questions for values already present in explicit state."""

    result = apply_closed_question_guard(
        text,
        language=language,
        customer_name=customer_name,
        company=company,
        customer_type=customer_type,
        delivery_address=delivery_address,
    )
    return result.text if result.repaired else text


def _last_assistant_message(recent_history: Sequence[str] | None) -> str:
    for entry in reversed(recent_history or ()):
        if entry.startswith("assistant: "):
            return entry.removeprefix("assistant: ").strip()
    return ""


def last_assistant_asked_quote_customer_details(
    recent_history: Sequence[str] | None,
    *,
    quote_context_active: bool = False,
) -> bool:
    """Whether the latest assistant turn requests quotation customer details."""

    last_assistant = " ".join(
        _last_assistant_message(recent_history).casefold().split()
    )
    if not last_assistant:
        return False
    text_has_quote_context = bool(
        re.search(
            r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b",
            last_assistant,
        )
        or re.search(
            r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
            last_assistant,
        )
    )
    if not quote_context_active and not text_has_quote_context:
        return False

    english_field = (
        r"(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)"
    )
    english_field_value = (
        rf"(?:(?:your|the)\s+)?{english_field}"
        r"(?=\s*(?:[(),;:/?!.]|\d{1,2}[.)]|$|\band\b|\bor\b|\bfor\b|"
        r"\bto\b|\bbefore\b|\bso\b))"
    )
    english_field_prefix = r"\s*(?:[:,-]\s*)?(?:\d{1,2}[.)]\s*)?"
    english_requests = (
        rf"\b(?:please\s+)?(?:share|provide|send){english_field_prefix}"
        rf"{english_field_value}",
        rf"\b(?:can|could|may)\s+i\s+(?:get|have)\s+{english_field_value}",
        rf"\b(?:can|could|may)\s+you\s+(?:share|provide|send)"
        rf"{english_field_prefix}{english_field_value}",
        rf"\bwhat(?:'s|\s+is)\s+(?:your|the)\s+{english_field_value}",
        rf"\bplease\s+let\s+me\s+know\s+{english_field_value}",
        rf"\b(?:please\s+)?confirm\s+{english_field_value}",
        rf"\b(?:i|we)(?:'ll)?\s+(?:just\s+)?need{english_field_prefix}"
        rf"{english_field_value}",
        r"\b(?:please\s+)?confirm\s+you\s+are\s+buying\s+as\s+an\s+individual\b",
    )
    if any(re.search(pattern, last_assistant) for pattern in english_requests):
        return True

    arabic_field = (
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)"
    )
    arabic_field_value = (
        rf"{arabic_field}"
        r"(?=\s*(?:[،؛,:.?؟!]|$|و|أو|لإعداد|قبل))"
    )
    return bool(
        re.search(
            rf"(?:يرجى\s+(?:مشاركة|تزويد)|"
            rf"هل\s+يمكنك\s+(?:مشاركة|تزويد|إرسال)|"
            rf"(?:من\s+فضلك\s+)?(?:شارك|زودني|أرسل)|(?:أحتاج|نحتاج))"
            rf"\s*[:،-]?\s*{arabic_field_value}",
            last_assistant,
        )
    )


def guard_premature_quote_detail_collection(
    text: str,
    *,
    language: str,
    quote_consent_granted: bool,
) -> str:
    """Replace pre-consent detail collection with the quotation opt-in."""

    if quote_consent_granted:
        return text
    if not last_assistant_asked_quote_customer_details(
        [f"assistant: {text}"],
        quote_context_active=True,
    ):
        return text

    prefix = _premature_quote_request_prefix(text)
    offer = (
        "هل ترغب أن أجهز عرض سعر رسمي؟"
        if is_arabic_customer_language(language)
        else "Would you like me to prepare a formal quotation?"
    )
    return f"{prefix}\n\n{offer}" if prefix else offer


def _premature_quote_request_prefix(text: str) -> str:
    """Text before the quote-detail request that a replacement must retain."""

    quote_match = re.search(
        r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b|"
        r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
        text,
        flags=re.IGNORECASE,
    )
    detail_match = re.search(
        r"\b(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)\b|"
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)",
        text,
        flags=re.IGNORECASE,
    )
    anchors = [
        match.start() for match in (quote_match, detail_match) if match is not None
    ]
    request_start = min(anchors) if anchors else 0
    sentence_starts = [0]
    for separator in ("\n", ". ", "? ", "! "):
        boundary = text.rfind(separator, 0, request_start)
        if boundary >= 0:
            sentence_starts.append(boundary + len(separator))
    return text[: max(sentence_starts)].rstrip()


def _normalized_words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", str(text or "").casefold(), flags=re.UNICODE))


def _words_appear_in_order(required: Sequence[str], available: Sequence[str]) -> bool:
    cursor = iter(available)
    return all(any(word == candidate for candidate in cursor) for word in required)


def _closed_question_replacement_covers(_before: str, after: str) -> bool:
    normalized = " ".join(after.casefold().split())
    english = "i already have" in normalized and (
        "continue with your request" in normalized or "please share" in normalized
    )
    arabic = (
        "لدي" in normalized
        and "بالفعل" in normalized
        and ("سأتابع طلبك" in normalized or "يرجى مشاركة" in normalized)
    )
    return english or arabic


def _premature_quote_replacement_covers(before: str, after: str) -> bool:
    has_opt_in = (
        "Would you like me to prepare a formal quotation?" in after
        or "هل ترغب أن أجهز عرض سعر رسمي؟" in after
    )
    prefix_words = _normalized_words(_premature_quote_request_prefix(before))
    return has_opt_in and _words_appear_in_order(prefix_words, _normalized_words(after))


def _additive_replacement_covers(before: str, after: str) -> bool:
    return _words_appear_in_order(_normalized_words(before), _normalized_words(after))


RESPONSE_GUARD_DECLARATIONS: dict[str, GuardDeclaration] = {
    "closed_question": GuardDeclaration(
        name="closed_question",
        mode=GuardMode.REPLACING,
        reason="Replaces a standalone known-slot question with acknowledgement and the next action.",
        replacement_covers=_closed_question_replacement_covers,
    ),
    "premature_quote_details": GuardDeclaration(
        name="premature_quote_details",
        mode=GuardMode.REPLACING,
        reason="Keeps the answer and replaces pre-consent data collection with quotation opt-in.",
        replacement_covers=_premature_quote_replacement_covers,
    ),
    "first_turn_opening": GuardDeclaration(
        name="first_turn_opening",
        mode=GuardMode.REPLACING,
        reason="Deduplicates greeting and identity only after the canonical identity and capability replace them.",
        replacement_covers=opening_replacement_covers,
    ),
    "selling_turn": GuardDeclaration(
        name="selling_turn",
        mode=GuardMode.REMOVING,
        reason="May drop trailing or repeated questions without writing equivalent text.",
    ),
    "deferred_commitment": GuardDeclaration(
        name="deferred_commitment",
        mode=GuardMode.REPLACING,
        reason="Only inserts a named follow-up commitment and preserves the original reply.",
        replacement_covers=_additive_replacement_covers,
    ),
    "grounding_output": GuardDeclaration(
        name="grounding_output",
        mode=GuardMode.REMOVING,
        reason="May drop unsupported sentences without replacing their content.",
    ),
}


def _has_meaningful_reply(text: str) -> bool:
    return any(character.isalnum() for character in text)


def apply_guard_with_reply_bound(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
) -> str:
    candidate = guard(text)
    if _has_meaningful_reply(text) and not _has_meaningful_reply(candidate):
        logger.error(
            "Response guard removed the reply: guard=%s before_chars=%d after_chars=%d",
            guard_name,
            len(text),
            len(candidate),
        )
        return text
    return candidate


def apply_declared_guard(
    text: str,
    *,
    declaration: GuardDeclaration,
    guard: Callable[[str], str],
    flagged: bool | None = None,
    flag_details: tuple[str, ...] = (),
) -> GuardApplication:
    """Apply one declaration without letting a removing guard edit the reply."""

    candidate = guard(text)
    detected = candidate != text if flagged is None else flagged
    if declaration.mode is GuardMode.REMOVING:
        if not detected:
            return GuardApplication(text=text, candidate=candidate)
        return GuardApplication(
            text=text,
            candidate=candidate,
            flags=(
                ReplyGuardFlag(
                    guard_name=declaration.name,
                    reason="removing_guard_triggered",
                    details=flag_details,
                ),
            ),
        )

    if candidate == text:
        return GuardApplication(text=text, candidate=candidate)
    covers = declaration.replacement_covers
    if covers is not None and covers(text, candidate):
        return GuardApplication(text=candidate, candidate=candidate)

    logger.error(
        "Response guard replacement lacked coverage: guard=%s before_chars=%d "
        "after_chars=%d",
        declaration.name,
        len(text),
        len(candidate),
    )
    return GuardApplication(
        text=text,
        candidate=candidate,
        flags=(
            ReplyGuardFlag(
                guard_name=declaration.name,
                reason="replacement_coverage_failed",
                details=flag_details,
            ),
        ),
    )


def apply_legacy_removing_candidate(
    application: GuardApplication,
    *,
    declaration: GuardDeclaration,
) -> str:
    """Preserve pre-judge output only for the behavior-neutral `.2` replay."""

    if declaration.mode is not GuardMode.REMOVING or not application.flags:
        return application.text
    return apply_guard_with_reply_bound(
        application.text,
        guard_name=f"{declaration.name}_legacy_candidate",
        guard=lambda _current: application.candidate,
    )


def _render_declared_guard(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
    flagged: bool | None = None,
    flag_details: tuple[str, ...] = (),
) -> tuple[str, tuple[ReplyGuardFlag, ...]]:
    declaration = RESPONSE_GUARD_DECLARATIONS[guard_name]
    application = apply_declared_guard(
        text,
        declaration=declaration,
        guard=guard,
        flagged=flagged,
        flag_details=flag_details,
    )
    if declaration.mode is GuardMode.REMOVING:
        rendered = apply_legacy_removing_candidate(
            application,
            declaration=declaration,
        )
    else:
        rendered = application.text
    return rendered, application.flags


def append_required_tool_disclosure(text: str, disclosure: str | None) -> str:
    """Append a required disclosure once, using normalized comparison."""

    normalized_disclosure = " ".join(str(disclosure or "").casefold().split())
    normalized_text = " ".join(text.casefold().split())
    if not normalized_disclosure or normalized_disclosure in normalized_text:
        return text
    return f"{text.rstrip()}\n\n{disclosure}"


def render_reply(
    text: str,
    *,
    state: ReplyPolicyState,
    provenance: ReplyProvenance,
) -> RenderedReply:
    """Apply the one customer-facing text policy, independent of provenance."""

    raised_flags: list[ReplyGuardFlag] = []
    rendered, flags = _render_declared_guard(
        text,
        guard_name="closed_question",
        guard=partial(
            repair_closed_questions,
            language=state.language,
            customer_name=state.customer_name,
            company=state.company,
            customer_type=state.customer_type,
            delivery_address=state.delivery_address,
        ),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="premature_quote_details",
        guard=partial(
            guard_premature_quote_detail_collection,
            language=state.language,
            quote_consent_granted=state.quote_consent_granted,
        ),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="first_turn_opening",
        guard=partial(
            apply_first_turn_opening_guard,
            language=state.language,
            is_first_turn=state.is_first_turn,
            customer_name=state.customer_name,
            anchor_line=state.anchor_line,
        ),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="selling_turn",
        guard=partial(
            apply_selling_turn_guard,
            language=state.language,
            is_first_turn=state.is_first_turn,
            previous_assistant_turns=state.previous_assistant_turns,
            customer_name=state.customer_name,
            owes_company_question=state.owes_company_question,
        ),
        flag_details=("deterministic_guard_would_remove_content",),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="deferred_commitment",
        guard=partial(commit_to_what_you_deferred, language=state.language),
    )
    raised_flags.extend(flags)
    violations = classify_grounding_output(
        rendered,
        inventory_confirmed=state.inventory_confirmed,
        grounded_amounts=state.grounded_amounts,
    )
    grounding = repair_grounding_output(
        rendered,
        language=state.language,
        violations=violations,
        inventory_confirmed=state.inventory_confirmed,
        grounded_amounts=state.grounded_amounts,
    )
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="grounding_output",
        guard=lambda _current: grounding.text,
        flagged=bool(violations),
        flag_details=tuple(violation.value for violation in violations),
    )
    raised_flags.extend(flags)
    rendered = apply_guard_with_reply_bound(
        rendered,
        guard_name="tool_disclosures",
        guard=partial(
            append_required_tool_disclosure,
            disclosure=state.required_tool_disclosure,
        ),
    )
    return RenderedReply(
        text=rendered,
        provenance=provenance,
        grounding=grounding,
        flags=tuple(raised_flags),
    )
